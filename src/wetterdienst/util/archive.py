# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Unpack what a provider sends compressed, with a ceiling on what comes out of it (GH-3340).

A compressed body of a few kilobytes can unpack to gigabytes, and every file here is read whole into
memory. Each function takes the ``limit`` of the bytes it may hand back, and raises a `DownloadError`
naming the file when what it unpacks is more. The ``limit`` is set by the provider, at a few times the
largest file it serves; `MAX_UNPACKED_BYTES` is for the one that has no figure of its own.
"""

from __future__ import annotations

import bz2
import gzip
import zipfile
from typing import IO, TYPE_CHECKING, Protocol, Self

from fsspec.implementations.tar import TarFileSystem
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import DownloadError
from wetterdienst.util.network import _megabytes, _without_url_secrets

if TYPE_CHECKING:
    import tarfile
    from io import BytesIO

    from wetterdienst.util.network import File

#: What a single file may unpack to when the provider has no figure of its own: 1 GiB, which is far above
#: the unpacked size of the files measured (DWD observation zips about 100 MB, a year of Météo-France SYNOP
#: 37 MB). Météo-France climate files are larger and set their own.
MAX_UNPACKED_BYTES = 1024**3

#: How much is unpacked at a time, so that the memory held is the chunk and not the ceiling
_CHUNK = 1024 * 1024


def ceiling(limit: int | None) -> int:
    """Give the ceiling to hold an unpacking to: the given one, else `MAX_UNPACKED_BYTES` as it is when asked."""
    return MAX_UNPACKED_BYTES if limit is None else limit


def too_large(url: str, limit: int) -> DownloadError:
    """Say that the file at ``url`` unpacks to more than ``limit`` bytes."""
    return DownloadError(_without_url_secrets(url), f"the file unpacks to more than the {_megabytes(limit)} allowed")


class _Readable(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...


def _read_chunked(stream: _Readable, limit: int, *, size: int | None = None) -> tuple[bytes, bool]:
    """Read up to ``size`` bytes (to the end if None) in chunks, and say whether more than ``limit`` came out."""
    chunks = []
    total = 0
    while size is None or total < size:
        chunk = stream.read(_CHUNK if size is None else min(_CHUNK, size - total))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            return b"", True
        chunks.append(chunk)
    return b"".join(chunks), False


def read_unpacked(stream: _Readable, *, url: str, limit: int | None = None) -> bytes:
    """Read an unpacking stream (a `GzipFile`, a `BZ2File`, a member of an archive) to its end, up to ``limit``.

    In chunks: the stream is asked for a megabyte at a time, as asking for the ceiling in one go makes
    some of them reserve all of it before they read a byte.
    """
    limit = ceiling(limit)
    data, exceeded = _read_chunked(stream, limit)
    if exceeded:
        raise too_large(url, limit)
    return data


def _body(file: File) -> BytesIO:
    if isinstance(file.content, Exception):
        raise file.content
    return file.content


def gunzip(file: File, *, limit: int | None = None) -> bytes:
    """Unpack a gzip file, the errors of `gzip.GzipFile` as they are."""
    with gzip.GzipFile(fileobj=_body(file), mode="rb") as stream:
        return read_unpacked(stream, url=file.url, limit=limit)


def bunzip2(content: bytes, *, url: str, limit: int | None = None) -> bytes:
    """Unpack bz2 bytes, with the errors of `bz2.decompress` as they are: `ValueError` for a stream cut short."""
    limit = ceiling(limit)
    chunks: list[bytes] = []
    size = 0
    data = content
    while data:
        decompressor = bz2.BZ2Decompressor()
        try:
            piece = decompressor.decompress(data, max_length=_CHUNK)
        except OSError:
            if chunks:  # what follows the last stream is not read, as `bz2.decompress` does not
                break
            raise
        while True:
            size += len(piece)
            if size > limit:
                raise too_large(url, limit)
            chunks.append(piece)
            if decompressor.eof:
                break
            if decompressor.needs_input:
                msg = "Compressed data ended before the end-of-stream marker was reached"
                raise ValueError(msg)
            piece = decompressor.decompress(b"", max_length=_CHUNK)
        data = decompressor.unused_data
    return b"".join(chunks)


def _check_total(sizes: list[int], *, url: str, limit: int | None) -> None:
    limit = ceiling(limit)
    if sum(sizes) > limit:
        raise too_large(url, limit)


def check_zip(archive: zipfile.ZipFile, *, url: str, limit: int | None = None) -> zipfile.ZipFile:
    """Refuse a zip archive that is not stored or deflated, or whose members claim more than ``limit`` in all.

    `zipfile` reads a member no further than the size it claims, but it unpacks first and cuts after: a
    bzip2 or LZMA member is unpacked whole whatever is asked of it, so those are refused (the providers
    send deflate), and a deflated member has to be read in chunks (`read_unpacked`, `open_zip`).
    """
    for info in archive.infolist():
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise DownloadError(_without_url_secrets(url), "the archive is compressed in a way that is not read")
    _check_total([info.file_size for info in archive.infolist()], url=url, limit=limit)
    return archive


class _ChunkedMember:
    """A member of a zip archive that is unpacked a megabyte at a time, however much `read` is asked for."""

    def __init__(self, member: IO[bytes]) -> None:
        self._member = member

    def read(self, size: int | None = -1) -> bytes:
        if size is not None and 0 <= size <= _CHUNK:
            return self._member.read(size)
        return _read_chunked(self._member, 1 << 62, size=None if size is None or size < 0 else size)[0]

    def __getattr__(self, name: str) -> object:
        return getattr(self._member, name)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._member.close()


class BoundedZipFileSystem(ZipFileSystem):
    """A `ZipFileSystem` whose members are unpacked in chunks, so that a read holds a chunk and not the claim."""

    def _open(
        self,
        path: str,
        mode: str = "rb",
        block_size: int | None = None,
        autocommit: bool = True,  # noqa: FBT001, FBT002
        cache_options: dict | None = None,
        **kwargs,  # noqa: ANN003
    ) -> _ChunkedMember:
        return _ChunkedMember(super()._open(path, mode, block_size, autocommit, cache_options, **kwargs))


def open_zip(file: File, *, limit: int | None = None) -> ZipFileSystem:
    """Open a zip archive as a filesystem, refusing one whose members claim to unpack to more than ``limit``."""
    zfs = BoundedZipFileSystem(_body(file), mode="r")
    check_zip(zfs.zip, url=file.url, limit=limit)
    return zfs


def open_tar(
    content: IO[bytes], *, url: str, limit: int | None = None, compression: str | None = None
) -> TarFileSystem:
    """Open a tar archive as a filesystem, refusing one with links or with more than ``limit`` bytes in all.

    A link is read as the file it points to, so an archive of many links to one member would unpack to many
    times its size; the archives served here hold none.
    """
    tfs = TarFileSystem(content, compression=compression)
    members: list[tarfile.TarInfo] = tfs.tar.getmembers()
    if any(member.islnk() or member.issym() for member in members):
        raise DownloadError(_without_url_secrets(url), "the archive holds links, which are not read")
    _check_total([member.size for member in members if member.isfile()], url=url, limit=limit)
    return tfs

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
from typing import IO, TYPE_CHECKING, Protocol

from fsspec.implementations.tar import TarFileSystem
from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import DownloadError
from wetterdienst.util.network import _megabytes, _without_url_secrets

if TYPE_CHECKING:
    import tarfile
    import zipfile
    from io import BytesIO

    from wetterdienst.util.network import File

#: What a single file may unpack to when the provider has no figure of its own: 1 GiB, which is ten times
#: the largest unpacked file of a table the providers serve (a month-bucket of Météo-France, about
#: 100 MB) and holds in memory whole.
MAX_UNPACKED_BYTES = 1024**3


def ceiling(limit: int | None) -> int:
    """Give the ceiling to hold an unpacking to: the given one, else `MAX_UNPACKED_BYTES` as it is when asked."""
    return MAX_UNPACKED_BYTES if limit is None else limit


def too_large(url: str, limit: int) -> DownloadError:
    """Say that the file at ``url`` unpacks to more than ``limit`` bytes."""
    return DownloadError(_without_url_secrets(url), f"the file unpacks to more than the {_megabytes(limit)} allowed")


class _Readable(Protocol):
    def read(self, size: int = ..., /) -> bytes: ...


def read_unpacked(stream: _Readable, *, url: str, limit: int | None = None) -> bytes:
    """Read an unpacking stream (a `GzipFile`, a `BZ2File`, a member of an archive) to its end, up to ``limit``."""
    limit = ceiling(limit)
    data = stream.read(limit + 1)
    if len(data) > limit:
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
            chunk = decompressor.decompress(data, max_length=limit - size + 1)
        except OSError:
            if chunks:  # what follows the last stream is not read, as `bz2.decompress` does not
                break
            raise
        size += len(chunk)
        if size > limit:
            raise too_large(url, limit)
        chunks.append(chunk)
        if not decompressor.eof:
            msg = "Compressed data ended before the end-of-stream marker was reached"
            raise ValueError(msg)
        data = decompressor.unused_data
    return b"".join(chunks)


def _check_total(sizes: list[int], *, url: str, limit: int | None) -> None:
    limit = ceiling(limit)
    if sum(sizes) > limit:
        raise too_large(url, limit)


def check_zip(archive: zipfile.ZipFile, *, url: str, limit: int | None = None) -> zipfile.ZipFile:
    """Refuse a zip archive whose members claim to unpack to more than ``limit`` bytes in all, and return it.

    The size a member claims is what `zipfile` reads it to and no further, so what is read of an archive
    that has passed is bounded by it. A member that holds more than it claims does not read to its end.
    """
    _check_total([info.file_size for info in archive.infolist()], url=url, limit=limit)
    return archive


def open_zip(file: File, *, limit: int | None = None) -> ZipFileSystem:
    """Open a zip archive as a filesystem, refusing one whose members claim to unpack to more than ``limit``."""
    zfs = ZipFileSystem(_body(file), mode="r")
    check_zip(zfs.zip, url=file.url, limit=limit)
    return zfs


def open_tar(
    content: IO[bytes], *, url: str, limit: int | None = None, compression: str | None = None
) -> TarFileSystem:
    """Open a tar archive as a filesystem, refusing one whose members hold more than ``limit`` bytes in all."""
    tfs = TarFileSystem(content, compression=compression)
    members: list[tarfile.TarInfo] = tfs.tar.getmembers()
    _check_total([member.size for member in members if member.isfile()], url=url, limit=limit)
    return tfs

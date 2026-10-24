# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A compressed body of a few kilobytes does not unpack to more than the ceiling it is held to (GH-3340)."""

from __future__ import annotations

import bz2
import gzip
import tarfile
import zipfile
from io import BytesIO

import pytest

from wetterdienst.exceptions import DownloadError
from wetterdienst.util.archive import MAX_UNPACKED_BYTES, bunzip2, gunzip, open_tar, open_zip, read_unpacked
from wetterdienst.util.network import File

URL = "https://example.invalid/data/file.bin?token=SECRET"
#: the size of what the archives below unpack to, and the ceiling they are held to
SIZE = 2_000_000
LIMIT = 100_000
ZEROS = bytes(SIZE)


def _file(content: bytes) -> File:
    return File(url=URL, content=BytesIO(content), status=200)


def _zip(**members: bytes) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _tar(**members: bytes) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
    return buffer.getvalue()


def _refused(raised: pytest.ExceptionInfo[DownloadError]) -> None:
    """Check that the error names the file without its query, and says nothing of how the bomb was made."""
    assert raised.value.url == "https://example.invalid/data/file.bin"
    assert str(raised.value) == (
        "Failed to download https://example.invalid/data/file.bin: the file unpacks to more than the 0.09537 MB allowed"
    )
    assert "SECRET" not in str(raised.value)


def test_the_default_ceiling_is_a_gibibyte() -> None:
    """Ten times the largest table a provider serves unpacked, and held in memory whole."""
    assert MAX_UNPACKED_BYTES == 1024**3


def test_a_bz2_body_that_unpacks_past_the_ceiling_is_refused() -> None:
    """1 KB of bz2 is 2 MB here; the ceiling is hit while unpacking, not after."""
    packed = bz2.compress(ZEROS)
    assert len(packed) < 1000
    with pytest.raises(DownloadError) as raised:
        bunzip2(packed, url=URL, limit=LIMIT)
    _refused(raised)


def test_a_bz2_body_inside_the_ceiling_is_unpacked_as_bz2_decompress_does() -> None:
    """Exactly the ceiling is inside it; several streams are unpacked to the end; trailing bytes are not read."""
    one = bz2.compress(b"a" * 100)
    assert bunzip2(one, url=URL, limit=100) == b"a" * 100
    assert bunzip2(one + bz2.compress(b"b" * 50), url=URL, limit=150) == bz2.decompress(one) + b"b" * 50
    assert bunzip2(one + b"garbage", url=URL, limit=100) == b"a" * 100
    assert bunzip2(b"", url=URL, limit=100) == b""
    with pytest.raises(DownloadError):
        bunzip2(one + bz2.compress(b"b"), url=URL, limit=100)


def test_a_bz2_body_that_is_no_bz2_fails_as_it_did() -> None:
    """The errors swsmos catches to answer a body it cannot read are the errors of `bz2.decompress`."""
    packed = bz2.compress(b"a" * 1000)
    with pytest.raises(ValueError, match="end-of-stream"):
        bunzip2(packed[:-10], url=URL, limit=LIMIT)
    with pytest.raises(OSError, match="Invalid data stream"):
        bunzip2(b"not bz2 at all", url=URL, limit=LIMIT)


def test_a_gzip_body_that_unpacks_past_the_ceiling_is_refused() -> None:
    """The same for gzip."""
    packed = gzip.compress(ZEROS)
    assert len(packed) < 10_000
    with pytest.raises(DownloadError) as raised:
        gunzip(_file(packed), limit=LIMIT)
    _refused(raised)
    assert gunzip(_file(gzip.compress(b"abc")), limit=3) == b"abc"


def test_a_gzip_body_that_is_no_gzip_fails_as_it_did() -> None:
    """`BadGzipFile` is an `OSError`, as it was."""
    with pytest.raises(OSError, match="Not a gzipped file"):
        gunzip(_file(b"not gzip at all"), limit=LIMIT)


def test_a_failed_download_is_not_unpacked() -> None:
    """The failure a download stored is what is raised, as it is for a caller that reads `file.content`."""
    failure = ConnectionError("down")
    with pytest.raises(ConnectionError):
        gunzip(File(url=URL, content=failure, status=500), limit=LIMIT)


def test_a_stream_is_read_to_the_ceiling_and_no_further() -> None:
    """What `read_unpacked` hands back is at most the ceiling, whichever stream it is asked of."""
    assert read_unpacked(BytesIO(b"x" * 10), url=URL, limit=10) == b"x" * 10
    with pytest.raises(DownloadError):
        read_unpacked(BytesIO(b"x" * 11), url=URL, limit=10)


def test_a_zip_archive_that_unpacks_past_the_ceiling_is_refused_before_a_member_is_read() -> None:
    """The members claim their sizes in the archive's directory, and the sum of them is checked when it is opened."""
    packed = _zip(**{"produkt_a.txt": ZEROS})
    assert len(packed) < 10_000
    with pytest.raises(DownloadError) as raised:
        open_zip(_file(packed), limit=LIMIT)
    _refused(raised)


def test_a_zip_archive_of_many_members_is_held_to_the_sum() -> None:
    """Each member is small and the archive is not: the ceiling is for the archive, which is read whole."""
    packed = _zip(**{f"m{i}.txt": bytes(LIMIT // 4) for i in range(8)})
    with pytest.raises(DownloadError):
        open_zip(_file(packed), limit=LIMIT)
    zfs = open_zip(_file(packed), limit=LIMIT * 4)
    assert len(zfs.glob("*.txt")) == 8


def test_a_zip_member_that_holds_more_than_it_claims_is_not_read_past_its_claim() -> None:
    """The size in the directory is the ceiling of what `zipfile` reads of a member, so a lie in it cannot inflate."""
    packed = bytearray(_zip(**{"a.txt": ZEROS}))
    claimed = (LIMIT // 2).to_bytes(4, "little")
    true_size = SIZE.to_bytes(4, "little")
    # the uncompressed size, in the local header of the member and in its entry of the directory
    for offset in (packed.find(b"PK\x03\x04") + 22, packed.find(b"PK\x01\x02") + 24):
        assert bytes(packed[offset : offset + 4]) == true_size
        packed[offset : offset + 4] = claimed
    zfs = open_zip(_file(bytes(packed)), limit=LIMIT)
    with pytest.raises(zipfile.BadZipFile):
        zfs.open("a.txt").read()


def test_a_zip_archive_that_is_none_is_a_bad_zip_file_as_it_was() -> None:
    """`BadZipFile` is what the callers catch to say an archive is corrupted."""
    with pytest.raises(zipfile.BadZipFile):
        open_zip(_file(b"not a zip"), limit=LIMIT)


def test_a_tar_archive_that_holds_more_than_the_ceiling_is_refused() -> None:
    """The sizes of its members are in their headers."""
    packed = _tar(**{"a.bin": ZEROS})
    with pytest.raises(DownloadError) as raised:
        open_tar(BytesIO(packed), url=URL, limit=LIMIT)
    _refused(raised)
    tfs = open_tar(BytesIO(_tar(**{"a.bin": b"abc", "b.bin": b"def"})), url=URL, limit=6)
    assert sorted(tfs.glob("*")) == ["a.bin", "b.bin"]


def test_a_tar_archive_that_is_none_is_a_read_error_as_it_was() -> None:
    """The radar callers fall back to a plain gzip on `tarfile.ReadError`."""
    with pytest.raises(tarfile.ReadError):
        open_tar(BytesIO(b"x" * 2000), url=URL, limit=LIMIT)

"""WebP: remove chunks EXIF/XMP e corrige as flags do VP8X.

O container e RIFF. Retirar um chunk exige dois ajustes contabeis: o tamanho
declarado no cabecalho RIFF e, quando existe VP8X, o bit de feature que anuncia
aquele chunk -- um leitor que ve o bit de EXIF ligado sem chunk EXIF trata o
arquivo como corrompido.
"""

from __future__ import annotations

import struct

from ..report import RemovedItem, ScrubReport

RIFF = b"RIFF"
WEBP = b"WEBP"

# Bits de feature do VP8X, no primeiro byte do payload.
_FLAG_ICC = 0x20
_FLAG_EXIF = 0x08
_FLAG_XMP = 0x04

_METADATA_CHUNKS = {
    b"EXIF": ("EXIF", _FLAG_EXIF),
    b"XMP ": ("XMP", _FLAG_XMP),
}
_ICC_CHUNK = b"ICCP"


def matches(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == RIFF and data[8:12] == WEBP


def scrub(data: bytes, *, keep_icc: bool = True) -> tuple[bytes, ScrubReport]:
    report = ScrubReport(fmt="WebP", size_before=len(data), size_after=0)

    declared = struct.unpack("<I", data[4:8])[0]
    end = min(len(data), 8 + declared)
    if len(data) > end:
        report.removed.append(
            RemovedItem("trailer", len(data) - end, "bytes apos o fim declarado do RIFF")
        )

    kept: list[bytes] = []
    cleared_flags = 0
    vp8x_index: int | None = None
    offset = 12

    while offset + 8 <= end:
        fourcc = data[offset : offset + 4]
        (size,) = struct.unpack("<I", data[offset + 4 : offset + 8])
        padded = size + (size & 1)  # chunks RIFF sao alinhados em 2 bytes
        total = 8 + padded
        if offset + total > end:
            total = end - offset

        if fourcc in _METADATA_CHUNKS:
            label, flag = _METADATA_CHUNKS[fourcc]
            cleared_flags |= flag
            report.removed.append(RemovedItem(fourcc.decode("latin-1"), total, label))
        elif fourcc == _ICC_CHUNK and not keep_icc:
            cleared_flags |= _FLAG_ICC
            report.removed.append(RemovedItem("ICCP", total, "perfil ICC"))
        else:
            if fourcc == _ICC_CHUNK:
                report.kept_icc = True
            if fourcc == b"VP8X":
                vp8x_index = len(kept)
            kept.append(data[offset : offset + total])

        offset += total

    if vp8x_index is not None and cleared_flags:
        chunk = bytearray(kept[vp8x_index])
        chunk[8] &= ~cleared_flags & 0xFF
        kept[vp8x_index] = bytes(chunk)

    body = b"".join(kept)
    out = RIFF + struct.pack("<I", 4 + len(body)) + WEBP + body
    report.size_after = len(out)
    return out, report

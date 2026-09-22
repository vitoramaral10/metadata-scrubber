"""JPEG: descarta segmentos APPn e comentarios.

Os metadados de um JPEG vivem todos em segmentos de marcador antes do primeiro
SOS -- EXIF em APP1, XMP em APP1, IPTC em APP13, C2PA em APP11 (JUMBF). Os
dados comprimidos ficam depois do SOS e nao sao tocados aqui, entao a limpeza e
sem perda: nenhuma recompressao, nenhum bloco DCT reescrito.
"""

from __future__ import annotations

from ..report import RemovedItem, ScrubReport

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"

_APP0, _APP15 = 0xE0, 0xEF
_SOS, _COM = 0xDA, 0xFE

# Segmentos sem payload: o marcador e o segmento inteiro.
_STANDALONE = {0x01} | set(range(0xD0, 0xDA))

_APPN_DETAIL = {
    0xE1: "EXIF ou XMP",
    0xE2: "perfil ICC ou MPF",
    0xE3: "Meta / Stim",
    0xEB: "Content Credentials (C2PA/JUMBF)",
    0xED: "Photoshop IRB / IPTC",
    0xEE: "Adobe DCT",
    0xEF: "APP15",
}


def matches(data: bytes) -> bool:
    return data.startswith(SOI)


def _app_payload_kind(marker: int, payload: bytes) -> str:
    """Identifica o segmento pelo identificador ASCII que abre o payload."""
    head = payload[:16]
    if marker == 0xE0:
        if head.startswith(b"JFIF\x00"):
            return "jfif"
        if head.startswith(b"JFXX\x00"):
            return "jfif"
    if marker == 0xE2 and head.startswith(b"ICC_PROFILE\x00"):
        return "icc"
    if marker == 0xEE and head.startswith(b"Adobe"):
        return "adobe"
    return "meta"


def scrub(data: bytes, *, keep_icc: bool = True) -> tuple[bytes, ScrubReport]:
    report = ScrubReport(fmt="JPEG", size_before=len(data), size_after=0)
    out = bytearray(SOI)
    offset = 2

    while offset + 1 < len(data):
        if data[offset] != 0xFF:
            # Fora de sincronia: nao da para garantir a estrutura daqui para a
            # frente, entao copiamos o resto sem interpretar.
            out += data[offset:]
            offset = len(data)
            break

        marker = data[offset + 1]
        if marker in (0xFF, 0x00):  # preenchimento
            out += data[offset : offset + 1]
            offset += 1
            continue
        if marker in _STANDALONE:
            out += data[offset : offset + 2]
            offset += 2
            continue

        if offset + 4 > len(data):
            break
        seg_len = int.from_bytes(data[offset + 2 : offset + 4], "big")
        total = 2 + seg_len
        payload = data[offset + 4 : offset + total]

        if marker == _SOS:
            # A partir daqui e dado comprimido ate o EOI; copiado literalmente.
            tail = data[offset:]
            end = tail.rfind(EOI)
            if end == -1:
                out += tail
            else:
                out += tail[: end + 2]
                if len(tail) > end + 2:
                    report.removed.append(
                        RemovedItem(
                            "trailer",
                            len(tail) - end - 2,
                            "bytes apos o EOI",
                        )
                    )
            offset = len(data)
            break

        drop = False
        detail = ""
        if marker == _COM:
            drop, detail = True, "comentario"
        elif _APP0 <= marker <= _APP15:
            kind = _app_payload_kind(marker, payload)
            if kind == "jfif":
                drop = False
            elif kind == "adobe":
                drop = False  # define a transformacao de cor; remover quebra CMYK
            elif kind == "icc":
                drop = not keep_icc
                detail = "perfil ICC"
                report.kept_icc = report.kept_icc or keep_icc
            else:
                drop = True
                detail = _APPN_DETAIL.get(marker, f"APP{marker - _APP0}")

        if drop:
            report.removed.append(
                RemovedItem(f"APP{marker - _APP0}" if marker != _COM else "COM", total, detail)
            )
        else:
            out += data[offset : offset + total]
        offset += total

    report.size_after = len(out)
    return bytes(out), report

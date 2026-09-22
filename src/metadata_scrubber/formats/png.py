"""PNG: allowlist de chunks.

O formato e uma sequencia de chunks [len][type][data][crc]. Como cada chunk e
autocontido e carrega o proprio CRC, da para descartar os auxiliares copiando
os bytes dos demais sem tocar em IDAT -- o pixel sai identico ao que entrou.
"""

from __future__ import annotations

import struct

from ..report import RemovedItem, ScrubReport

SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Chunks que participam da renderizacao. Tudo fora desta lista vai embora,
# inclusive tipos desconhecidos: o default e remover, nao preservar.
RENDERING_CHUNKS = frozenset(
    {
        b"IHDR",  # cabecalho
        b"PLTE",  # paleta
        b"IDAT",  # pixel
        b"IEND",  # fim
        b"tRNS",  # transparencia
        b"bKGD",  # cor de fundo
        b"gAMA",  # gama
        b"cHRM",  # cromaticidade
        b"sRGB",  # intencao de renderizacao
        b"sBIT",  # bits significativos
        b"hIST",  # histograma da paleta
        b"pHYs",  # densidade fisica
        b"cICP",  # primarias/transferencia (HDR)
        b"mDCv",  # metadata de masterizacao HDR
        b"cLLi",  # luminancia de conteudo HDR
        b"acTL",  # APNG: controle de animacao
        b"fcTL",  # APNG: controle de frame
        b"fdAT",  # APNG: dados de frame
    }
)

ICC_CHUNK = b"iCCP"

# O que cada chunk descartado costuma carregar, para o relatorio.
_DETAIL = {
    b"caBX": "Content Credentials (C2PA/JUMBF)",
    b"eXIf": "EXIF",
    b"tEXt": "texto (latin-1)",
    b"zTXt": "texto comprimido",
    b"iTXt": "texto UTF-8 (normalmente XMP)",
    b"tIME": "data da ultima modificacao",
    b"sPLT": "paleta sugerida",
    b"iCCP": "perfil ICC",
    b"dSIG": "assinatura digital",
    b"eXIT": "EXIF (variante nao padronizada)",
}


def matches(data: bytes) -> bool:
    return data.startswith(SIGNATURE)


def scrub(data: bytes, *, keep_icc: bool = True) -> tuple[bytes, ScrubReport]:
    report = ScrubReport(fmt="PNG", size_before=len(data), size_after=0)
    allowed = set(RENDERING_CHUNKS)
    if keep_icc:
        allowed.add(ICC_CHUNK)

    out = bytearray(SIGNATURE)
    offset = len(SIGNATURE)

    while offset + 8 <= len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        ctype = data[offset + 4 : offset + 8]
        total = 12 + length
        if offset + total > len(data):
            # Chunk truncado: o arquivo acaba aqui, e o resto e lixo.
            report.removed.append(
                RemovedItem("trailer", len(data) - offset, "bytes apos o ultimo chunk valido")
            )
            break

        if ctype in allowed:
            out += data[offset : offset + total]
        else:
            report.removed.append(
                RemovedItem(
                    ctype.decode("latin-1"),
                    total,
                    _DETAIL.get(ctype, "chunk auxiliar"),
                )
            )

        offset += total
        if ctype == b"IEND":
            if offset < len(data):
                report.removed.append(
                    RemovedItem("trailer", len(data) - offset, "bytes apos o IEND")
                )
            break

    report.size_after = len(out)
    report.kept_icc = keep_icc and ICC_CHUNK in {data[o + 4 : o + 8] for o in _chunk_offsets(data)}
    return bytes(out), report


def _chunk_offsets(data: bytes) -> list[int]:
    offsets: list[int] = []
    offset = len(SIGNATURE)
    while offset + 8 <= len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        if offset + 12 + length > len(data):
            break
        offsets.append(offset)
        if data[offset + 4 : offset + 8] == b"IEND":
            break
        offset += 12 + length
    return offsets

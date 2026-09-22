"""GIF: remove blocos de comentario, texto e extensoes de aplicacao.

O unico bloco de aplicacao preservado e o NETSCAPE2.0, que carrega a contagem
de loop -- descarta-lo faria a animacao rodar uma vez so.
"""

from __future__ import annotations

from ..report import RemovedItem, ScrubReport, UnsupportedFormat

_HEADERS = (b"GIF87a", b"GIF89a")
_EXTENSION, _IMAGE, _TRAILER = 0x21, 0x2C, 0x3B
_GRAPHIC_CONTROL, _COMMENT, _PLAIN_TEXT, _APPLICATION = 0xF9, 0xFE, 0x01, 0xFF

_LOOP_EXTENSION = b"NETSCAPE2.0"


def matches(data: bytes) -> bool:
    return data.startswith(_HEADERS)


def _read_sub_blocks(data: bytes, offset: int) -> int:
    """Devolve o offset logo apos o terminador da cadeia de sub-blocos."""
    while offset < len(data):
        size = data[offset]
        offset += 1
        if size == 0:
            return offset
        offset += size
    return offset


def scrub(data: bytes, *, keep_icc: bool = True) -> tuple[bytes, ScrubReport]:
    report = ScrubReport(fmt="GIF", size_before=len(data), size_after=0)
    if len(data) < 13:
        raise UnsupportedFormat("GIF truncado antes do descritor de tela")

    offset = 13
    flags = data[10]
    if flags & 0x80:  # tabela global de cores
        offset += 3 * (2 ** ((flags & 0x07) + 1))
    if offset > len(data):
        raise UnsupportedFormat("GIF truncado na tabela global de cores")

    out = bytearray(data[:offset])

    while offset < len(data):
        marker = data[offset]

        if marker == _TRAILER:
            out.append(_TRAILER)
            offset += 1
            if offset < len(data):
                report.removed.append(
                    RemovedItem("trailer", len(data) - offset, "bytes apos o fim do GIF")
                )
            break

        if marker == _EXTENSION:
            label = data[offset + 1] if offset + 1 < len(data) else 0
            start = offset
            offset = _read_sub_blocks(data, offset + 2)
            block = data[start:offset]

            # GCE carrega timing e transparencia; NETSCAPE2.0, a contagem de loop.
            is_loop = label == _APPLICATION and _LOOP_EXTENSION in block[:22]
            if label == _GRAPHIC_CONTROL or is_loop:
                out += block
            elif label == _COMMENT:
                report.removed.append(RemovedItem("Comment", len(block), "comentario"))
            elif label == _PLAIN_TEXT:
                report.removed.append(RemovedItem("PlainText", len(block), "texto sobreposto"))
            elif label == _APPLICATION:
                name = bytes(block[3:14]).decode("latin-1", "replace").strip("\x00")
                report.removed.append(RemovedItem("Application", len(block), f"extensao {name!r}"))
            else:
                report.removed.append(
                    RemovedItem(f"Extension 0x{label:02X}", len(block), "extensao desconhecida")
                )
            continue

        if marker == _IMAGE:
            start = offset
            offset += 10
            if offset > len(data):
                break
            local = data[start + 9]
            if local & 0x80:  # tabela local de cores
                offset += 3 * (2 ** ((local & 0x07) + 1))
            offset += 1  # codigo LZW minimo
            offset = _read_sub_blocks(data, offset)
            out += data[start:offset]
            continue

        # Byte inesperado: para de interpretar e preserva o que sobrou.
        out += data[offset:]
        break

    report.size_after = len(out)
    return bytes(out), report

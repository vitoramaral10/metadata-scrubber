"""Ponto de entrada da limpeza: escolhe o parser pela assinatura do arquivo."""

from __future__ import annotations

from .formats import gif, jpeg, png, webp
from .report import ScrubReport, UnsupportedFormat

# A ordem nao importa: as assinaturas sao mutuamente exclusivas.
_PARSERS = (png, jpeg, webp, gif)

SUPPORTED = ("PNG", "JPEG", "WebP", "GIF")


def scrub_bytes(data: bytes, *, keep_icc: bool = True) -> tuple[bytes, ScrubReport]:
    """Devolve o arquivo limpo e o relatorio do que saiu.

    A identificacao e por assinatura, nunca por extensao: um `.png` que na
    verdade e JPEG seria remontado com o parser errado e sairia corrompido.
    """
    if not data:
        raise UnsupportedFormat("arquivo vazio")

    for parser in _PARSERS:
        if parser.matches(data):
            return parser.scrub(data, keep_icc=keep_icc)

    raise UnsupportedFormat(
        f"formato nao reconhecido pela assinatura; suportados: {', '.join(SUPPORTED)}"
    )

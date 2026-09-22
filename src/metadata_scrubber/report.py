"""Estruturas de relatorio compartilhadas pelos parsers de formato."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RemovedItem:
    """Um bloco de metadado retirado do arquivo."""

    kind: str
    """Rotulo do container: nome do chunk PNG, marcador JPEG, fourcc WebP."""

    size: int
    """Bytes ocupados pelo bloco inteiro, cabecalho incluido."""

    detail: str = ""
    """O que o bloco carregava, quando da para identificar."""


@dataclass
class ScrubReport:
    """Resultado de uma limpeza."""

    fmt: str
    size_before: int
    size_after: int
    removed: list[RemovedItem] = field(default_factory=list)
    kept_icc: bool = False

    @property
    def bytes_removed(self) -> int:
        return self.size_before - self.size_after

    @property
    def is_clean(self) -> bool:
        """True quando o arquivo de entrada ja nao tinha metadado nenhum."""
        return not self.removed


class UnsupportedFormat(ValueError):
    """O arquivo nao e um dos formatos que sabemos desmontar com seguranca."""

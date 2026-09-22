"""Interface Gradio do metadata-scrubber."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import gradio as gr

from .report import ScrubReport, UnsupportedFormat
from .scrub import SUPPORTED, scrub_bytes

MAX_FILES = int(os.getenv("SCRUBBER_MAX_FILES", "20"))
MAX_FILE_SIZE = os.getenv("SCRUBBER_MAX_FILE_SIZE", "25mb")
WORK_DIR = Path(os.getenv("SCRUBBER_WORK_DIR", tempfile.gettempdir()))

DESCRIPTION = """
Remove metadados de imagem — **EXIF, XMP, IPTC, comentários e Content
Credentials (C2PA)** — sem recodificar a imagem. Os dados de pixel saem byte a
byte idênticos aos que entraram; o que muda é só o que o arquivo conta sobre si.

Formatos: **PNG · JPEG · WebP · GIF**. Nada é gravado em disco permanente: os
arquivos vivem em memória durante o processamento e o diretório de trabalho é
efêmero.
"""


def _output_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix
    return f"{stem}-limpo{suffix}"


def _row(name: str, report: ScrubReport) -> list[str]:
    if report.is_clean:
        status = "já estava limpo"
    else:
        kinds = ", ".join(
            f"{item.kind} ({item.detail})" if item.detail else item.kind for item in report.removed
        )
        status = kinds
    return [
        name,
        report.fmt,
        f"{report.size_before:,}".replace(",", "."),
        f"{report.size_after:,}".replace(",", "."),
        f"-{report.bytes_removed:,}".replace(",", "."),
        status,
    ]


def process(paths: list[str] | None, keep_icc: bool) -> tuple[list[str], list[list[str]], str]:
    if not paths:
        return [], [], "Nenhum arquivo enviado."
    if len(paths) > MAX_FILES:
        raise gr.Error(f"Máximo de {MAX_FILES} arquivos por vez.")

    workdir = Path(tempfile.mkdtemp(prefix="scrub-", dir=WORK_DIR))
    outputs: list[str] = []
    rows: list[list[str]] = []
    total_removed = 0
    failures: list[str] = []

    for path in paths:
        source = Path(path)
        try:
            cleaned, report = scrub_bytes(source.read_bytes(), keep_icc=keep_icc)
        except UnsupportedFormat as exc:
            failures.append(f"`{source.name}`: {exc}")
            continue

        destination = workdir / _output_name(source.name)
        destination.write_bytes(cleaned)
        outputs.append(str(destination))
        rows.append(_row(source.name, report))
        total_removed += report.bytes_removed

    summary = []
    if outputs:
        summary.append(
            f"**{len(outputs)} arquivo(s) processado(s)** — "
            f"{total_removed:,} bytes de metadado removidos.".replace(",", ".")
        )
    if failures:
        summary.append("**Não processados:**\n\n" + "\n".join(f"- {f}" for f in failures))
    if not outputs and not failures:
        summary.append("Nada a fazer.")

    return outputs, rows, "\n\n".join(summary)


def build() -> gr.Blocks:
    with gr.Blocks(title="metadata-scrubber", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# metadata-scrubber")
        gr.Markdown(DESCRIPTION)

        with gr.Row():
            with gr.Column(scale=1):
                files = gr.File(
                    label=f"Imagens (até {MAX_FILES}, {MAX_FILE_SIZE} cada)",
                    file_count="multiple",
                    file_types=[".png", ".jpg", ".jpeg", ".webp", ".gif"],
                    type="filepath",
                )
                keep_icc = gr.Checkbox(
                    label="Preservar perfil de cor (ICC)",
                    value=True,
                    info=(
                        "Mantém a fidelidade de cor. Desmarque para remover também o "
                        "perfil ICC, que em alguns arquivos carrega o nome do "
                        "dispositivo ou do software que o gerou."
                    ),
                )
                run = gr.Button("Limpar metadados", variant="primary")

            with gr.Column(scale=1):
                outputs = gr.File(label="Arquivos limpos", file_count="multiple")
                summary = gr.Markdown()

        table = gr.Dataframe(
            headers=["Arquivo", "Formato", "Antes (B)", "Depois (B)", "Delta", "Removido"],
            label="O que saiu de cada arquivo",
            wrap=True,
            interactive=False,
        )

        gr.Markdown(
            f"Formatos suportados: {', '.join(SUPPORTED)}. A identificação é feita "
            "pela assinatura do arquivo, não pela extensão."
        )

        run.click(process, inputs=[files, keep_icc], outputs=[outputs, table, summary])

    return demo


def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    demo = build().queue(default_concurrency_limit=2, max_size=20)
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        max_file_size=MAX_FILE_SIZE,
        show_api=False,
        ssr_mode=False,
        analytics_enabled=False,
        quiet=False,
    )


if __name__ == "__main__":
    main()

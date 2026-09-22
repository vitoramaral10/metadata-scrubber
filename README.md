# metadata-scrubber

Remove metadados de imagem — EXIF, XMP, IPTC, comentários e **Content
Credentials (C2PA)** — sem recodificar a imagem.

A diferença em relação a abrir e salvar de novo num editor: aqui os dados de
pixel não são tocados. A ferramenta desmonta o container (chunks PNG, segmentos
JPEG, chunks RIFF, blocos GIF), descarta os blocos de metadado e remonta o
arquivo com os bytes originais dos dados comprimidos. Sai byte a byte idêntico
no que importa para a imagem, e sem nada do que ela contava sobre si.

**Formatos:** PNG · JPEG · WebP · GIF

## Como funciona, por formato

| Formato | O que sai | Cuidado tomado |
|---|---|---|
| PNG | `tEXt`, `zTXt`, `iTXt` (XMP), `eXIf`, `caBX` (C2PA), `tIME`, `dSIG`, tipos desconhecidos e trailer após o `IEND` | Allowlist: só chunks de renderização ficam. APNG (`acTL`/`fcTL`/`fdAT`) e metadados HDR (`cICP`/`mDCv`/`cLLi`) preservados |
| JPEG | `APP1` (EXIF/XMP), `APP2` não-ICC, `APP11` (JUMBF/C2PA), `APP13` (IPTC), demais `APPn`, `COM` e trailer após o `EOI` | `APP0` JFIF e `APP14` Adobe ficam — remover o Adobe quebra a transformação de cor em CMYK. Dados após o `SOS` copiados literalmente, então progressivo sobrevive |
| WebP | `EXIF`, `XMP ` | As flags de feature do `VP8X` são corrigidas: bit ligado sem o chunk correspondente faz leitores tratarem o arquivo como corrompido |
| GIF | Comentários, Plain Text e extensões de aplicação | `NETSCAPE2.0` fica — sem ele a animação rodaria uma vez só |

O perfil ICC é preservado por padrão (fidelidade de cor) e removível por opção,
já que em alguns arquivos ele carrega o nome do dispositivo ou do software.

A identificação é pela **assinatura do arquivo**, nunca pela extensão: um JPEG
renomeado para `.png` seria remontado com o parser errado e sairia corrompido.

## Rodar

```bash
uv venv && uv pip install -e ".[dev]"
uv run metadata-scrubber-web     # http://localhost:7860
uv run pytest tests -q
```

## Docker

```bash
docker build -t metadata-scrubber .
docker run --rm -p 7860:7860 \
  --read-only --tmpfs /tmp:size=256m \
  --cap-drop ALL --security-opt no-new-privileges \
  --user 65532:65532 \
  metadata-scrubber
```

Imagens publicadas a cada push na `main`:
`ghcr.io/vitoramaral10/metadata-scrubber:latest`.

## Bloco de compose (homelab atrás do Cloudflare Tunnel)

Cole no compose que já compartilha a rede do `cloudflared`. Sem `ports:` — quem
publica é o túnel, pela rede interna.

```yaml
  metadata-scrubber:
    image: ghcr.io/vitoramaral10/metadata-scrubber:latest
    container_name: metadata-scrubber
    restart: unless-stopped
    user: "65532:65532"
    read_only: true
    tmpfs:
      - /tmp:size=256m,mode=1777
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    pids_limit: 200
    mem_limit: 1g
    cpus: 1.5
    environment:
      SCRUBBER_MAX_FILES: "20"
      SCRUBBER_MAX_FILE_SIZE: "25mb"
    expose:
      - "7860"
```

## Configuração

| Variável | Padrão | Para quê |
|---|---|---|
| `SCRUBBER_MAX_FILES` | `20` | Arquivos por lote |
| `SCRUBBER_MAX_FILE_SIZE` | `25mb` | Limite por arquivo |
| `SCRUBBER_WORK_DIR` | `/tmp/metadata-scrubber` | Diretório efêmero de trabalho |
| `GRADIO_SERVER_PORT` | `7860` | Porta HTTP |

## Limites conhecidos

- Metadados gravados **entre scans** de um JPEG progressivo não são removidos:
  tudo depois do primeiro `SOS` é copiado literalmente para não recomprimir.
  Não é onde EXIF, XMP ou C2PA vivem na prática.
- Marca d'água **visível**, ou sinal embutido nos próprios pixels
  (esteganografia, SynthID e afins), não é afetado — a ferramenta mexe no
  container, não na imagem.
- Formatos fora da lista são recusados com erro explícito, nunca processados
  "na tentativa".

## Licença

MIT.

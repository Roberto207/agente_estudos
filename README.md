# Agente Estudos

Script Python que gera pastas de estudo completas e estruturadas para o **Obsidian** a partir de um prompt com tema, foco e fontes.

Baseado no agente `criar-estudo` do Claude Code — reescrito como script chamável, suportando múltiplos providers de LLM.

## O que ele gera

Dado um tema (ex: *Redes Neurais*), o script produz:

```
~/obsidian/redes_neurais/
├── guia_de_estudos.md          # Ordem de leitura recomendada com checkpoints
├── 1_redes_neurais_fundamentos.canvas
├── 2_redes_neurais_avancado.canvas
├── fundamentos/
│   ├── introducao.md
│   ├── perceptron.md
│   └── funcoes_ativacao.md
├── avancado/
│   ├── backpropagation.md
│   └── otimizadores.md
├── transcripts/                # Resumos das fontes processadas
│   ├── transcript_1.md         # Vídeo YouTube distilado
│   └── artigo_2.md             # Artigo resumido
└── html/                       # Versão browser (Catppuccin Mocha)
    ├── index.html              # Hub de navegação
    ├── fundamentos_introducao.html
    └── ...
```

## Providers de LLM suportados

| Provider | Modelos recomendados | Configuração |
|---|---|---|
| **Anthropic** | claude-opus-4-8, claude-sonnet-4-6 | `ANTHROPIC_API_KEY` |
| **OpenAI** | gpt-4o, gpt-4o-mini | `OPENAI_API_KEY` |
| **Groq** | llama-3.3-70b, mixtral-8x7b | `GROQ_API_KEY` |
| **Ollama** | llama3.2, qwen2.5, mistral | Ollama local |

## Instalação

```bash
git clone https://github.com/<seu-usuario>/agente-estudos.git
cd agente-estudos
pip install -r requirements.txt
```

## Configuração

Escolha **uma** das opções:

### Opção A — config.yaml (recomendado)

```bash
cp config.example.yaml config.yaml
# Edite config.yaml com seu provider e API key preferidos
```

### Opção B — .env

```bash
cp .env.example .env
# Edite .env
```

### Opção C — variáveis de ambiente

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### Setup interativo (assistido)

```bash
python setup.py
```

## Uso

### Via argumentos

```bash
python main.py \
  --tema "Transformers e Atenção" \
  --foco "self-attention, multi-head attention, positional encoding" \
  --didatica "matemático com exemplos em PyTorch" \
  --pasta ~/obsidian/transformers \
  --fonte "https://youtu.be/iDulhoQ2pro" \
  --fonte "https://arxiv.org/abs/1706.03762" \
  --fonte "https://jalammar.github.io/illustrated-transformer/"
```

### Modo interativo

```bash
python main.py --interactive
# ou simplesmente:
python main.py
```

### Sem fontes (só LLM + pesquisa web)

```bash
python main.py \
  --tema "Algoritmos de Ordenação" \
  --foco "quicksort, mergesort, complexidade" \
  --pasta ~/obsidian/algoritmos
```

### Opções completas

```
--tema        -t   Tema principal
--foco        -f   Tópicos específicos (separados por vírgula)
--didatica    -d   Estilo: formal | prático | exemplos do mundo real | matemático
--pasta       -p   Caminho absoluto da pasta destino
--fonte       -s   Fonte (repita para múltiplas)
--config      -c   Caminho alternativo para config.yaml
--interactive -i   Modo interativo
```

## Tipos de fonte aceitos

| Tipo | Exemplos |
|---|---|
| URL YouTube / Vimeo | `https://youtu.be/...` |
| Arquivo de vídeo local | `/home/user/aula.mp4` |
| Artigo / blog / docs | `https://medium.com/...` |
| Paper (arxiv, ACM, IEEE) | `https://arxiv.org/abs/...` |
| Nome de livro / curso | `"Deep Learning Goodfellow"` |

## Transcrição de vídeos locais

Para vídeos locais (`.mp4`, `.mkv`, etc.), configure o provider de transcrição:

```yaml
# config.yaml
transcription:
  provider: groq     # rápido, usa API Whisper do Groq (gratuito no free tier)
  groq_api_key: ""   # deixe vazio para usar groq.api_key
```

Ou localmente (instale `openai-whisper` ou `faster-whisper`):

```yaml
transcription:
  provider: local
  local_model: base  # tiny | base | small | medium | large
```

## Estrutura do projeto

```
agente-estudos/
├── main.py                    # Entry point (CLI)
├── setup.py                   # Wizard de configuração
├── config.example.yaml        # Template de config
├── .env.example               # Template de .env
├── requirements.txt
└── src/
    ├── llm.py                 # Cliente LLM unificado
    ├── pipeline.py            # Orquestrador das 8 fases
    ├── distiller.py           # Processamento de fontes
    ├── tools/
    │   ├── web.py             # WebFetch + DuckDuckGo search
    │   └── video.py           # yt-dlp + Whisper
    └── generators/
        ├── content.py         # Escrita dos .md via LLM
        ├── canvas.py          # Canvas Obsidian
        └── html_gen.py        # HTML Catppuccin Mocha
```

## Dependências

- **Python 3.10+**
- `anthropic` / `openai` — clientes LLM
- `yt-dlp` — download de transcrições YouTube
- `requests` + `beautifulsoup4` — fetching de artigos
- `duckduckgo-search` — pesquisa web sem API key
- `rich` + `typer` — CLI e progress display
- `PyYAML` — leitura de config.yaml
- `python-dotenv` — suporte a .env (opcional)

## Licença

MIT

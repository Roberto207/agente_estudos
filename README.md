# Agente Estudos

Sistema agentico Python que gera pastas de estudo completas e estruturadas para o **Obsidian** a partir de um tema, foco e fontes.

O LLM recebe um conjunto de ferramentas (busca web, download de artigos, transcrição de vídeos, escrita de arquivos) e decide por conta própria como executar a tarefa — sem sequência fixa. Funciona a partir de qualquer terminal, sem dependência de Claude Code ou VSCode.

Suporta Anthropic, OpenAI, Groq e Ollama.

## O que ele gera

Dado um tema (ex: *Redes Neurais*), o sistema produz:

```
~/obsidian/redes_neurais/
├── guia_de_estudos.md          # Ordem de leitura recomendada com checkpoints
├── 1_redes_neurais_fundamentos.canvas
├── 2_redes_neurais_avancado.canvas
├── fundamentos/
│   ├── introducao.md           # Cada .md tem 3 níveis: TL;DR / Resumo / Completo
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
    ├── flashcards.html         # Spaced repetition (SM-2)
    ├── quiz.html               # Quiz de múltipla escolha
    └── ...
```

## Providers de LLM suportados

| Provider | Modelos recomendados | Suporte a tool_use |
|---|---|---|
| **Anthropic** | claude-opus-4-8, claude-sonnet-4-6 | Nativo |
| **OpenAI** | gpt-4o, gpt-4o-mini | Nativo |
| **Groq** | llama-3.3-70b, mixtral-8x7b | Nativo |
| **Ollama** | llama3.2, qwen2.5, mistral | Depende do modelo* |

*Se o modelo Ollama não suportar tool_use, use `--mode pipeline`.

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

### Modo interativo

```bash
python main.py --interactive
# ou simplesmente:
python main.py
```

O sistema pergunta tema, foco, didática, pasta e fontes no terminal.

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

### Sem fontes (só LLM + pesquisa web)

```bash
python main.py \
  --tema "Algoritmos de Ordenação" \
  --foco "quicksort, mergesort, complexidade" \
  --pasta ~/obsidian/algoritmos
```

### Chat sobre o conteúdo

Depois de gerar uma pasta de estudos, abra um chat interativo sobre o material:

```bash
# Q&A direto (estilo NotebookLM — cita a fonte de cada resposta)
python main.py --chat --pasta ~/obsidian/redes_neurais

# Tutor Socrático (nunca dá a resposta direta, faz perguntas)
python main.py --chat --pasta ~/obsidian/redes_neurais --chat-mode socratico
```

Dentro do chat, os comandos disponíveis são:

| Comando | Ação |
|---|---|
| `/modo` | Alterna entre Q&A e Socrático (limpa histórico) |
| `/novo` | Limpa o histórico da conversa |
| `/sair` | Encerra o chat |

### Opções completas

```
--tema        -t   Tema principal
--foco        -f   Tópicos específicos (separados por vírgula)
--didatica    -d   Estilo: formal | prático | exemplos do mundo real | matemático
--pasta       -p   Caminho absoluto da pasta destino
--fonte       -s   Fonte (repita para múltiplas)
--config           Caminho alternativo para config.yaml
--interactive -i   Modo interativo
--mode        -m   agent (padrão) | pipeline
--chat        -c   Abre chat sobre pasta existente (não gera conteúdo)
--chat-mode        qa (padrão) | socratico
```

### Modos de execução

**`--mode agent`** (padrão): loop agentico real. O LLM recebe ferramentas e decide sozinho o que chamar, em que ordem, podendo se adaptar ao conteúdo encontrado.

**`--mode pipeline`**: sequência fixa de 8 fases (legado). Útil quando o modelo não suporta tool_use (ex: alguns modelos Ollama).

```bash
# Forçar modo pipeline
python main.py --interactive --mode pipeline
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
    ├── agent.py               # Loop agentico (modo padrão)
    ├── llm.py                 # Cliente LLM unificado (chat + tool_use)
    ├── pipeline.py            # Pipeline legado de 8 fases
    ├── distiller.py           # Processamento de fontes
    ├── tools/
    │   ├── registry.py        # Definições das ferramentas + executor
    │   ├── files.py           # Ferramentas de filesystem
    │   ├── web.py             # WebFetch + DuckDuckGo search
    │   └── video.py           # yt-dlp + Whisper
    ├── chat.py                # Chat interativo (QA + Socrático)
    └── generators/            # Geração de conteúdo (pipeline + pós-processamento)
        ├── content.py         # Arquivos .md com 3 níveis de profundidade
        ├── canvas.py          # Canvas Obsidian
        ├── html_gen.py        # HTML (Catppuccin Mocha) com tabs de profundidade
        ├── flashcards.py      # Flashcards SM-2 (gerado automaticamente)
        └── quiz.py            # Quiz MCQ (gerado automaticamente)
```

## Ferramentas disponíveis para o agente

No modo `agent`, o LLM pode chamar:

| Ferramenta | O que faz |
|---|---|
| `web_search` | Pesquisa DuckDuckGo (sem API key) |
| `fetch_url` | Download e extração de texto de URLs |
| `transcribe_video` | Transcreve YouTube ou vídeo local |
| `write_file` | Escreve arquivo no filesystem |
| `read_file` | Lê arquivo existente |
| `create_directory` | Cria pasta |
| `list_directory` | Lista conteúdo de pasta |

## Funcionalidades de aprendizado

### Três níveis de profundidade por arquivo

Cada `.md` gerado contém obrigatoriamente três seções:

- **TL;DR** — 2 parágrafos com o essencial (leitura de 2 min)
- **Resumo (5 min)** — principais pontos com exemplos
- **Conteúdo Completo** — artigo completo com tabelas, código e exemplos

Na versão HTML, um seletor de tabs (⚡ Rápido / 📖 Médio / 📚 Completo) alterna entre os níveis automaticamente.

### Flashcards com Spaced Repetition

Gerado automaticamente em `html/flashcards.html` após cada execução. Funciona offline, sem dependências externas.

- Algoritmo **SM-2** implementado em JavaScript puro
- Card flip com animação 3D (CSS)
- Botões Difícil / Médio / Bom / Fácil ajustam o intervalo de revisão
- Progresso salvo em `localStorage` do browser

### Quiz de múltipla escolha

Gerado automaticamente em `html/quiz.html`.

- 10–15 questões por pasta de estudos
- Feedback imediato após cada resposta com explicação
- Placar final com lista de pontos fracos e links diretos para os MDs de origem
- Botão "Tentar novamente" para repetir com as mesmas questões

### Chat interativo (Q&A e Tutor Socrático)

Ver seção [Chat sobre o conteúdo](#chat-sobre-o-conteúdo) acima.

## Integração VSCode (opcional)

O repositório inclui `.vscode/tasks.json` e `.vscode/launch.json` com atalhos de conveniência. Eles chamam exatamente os mesmos comandos `python main.py` descritos acima — são opcionais e não adicionam nenhum comportamento novo.

- `Ctrl+Shift+B` → roda `python main.py --interactive`
- `F5` → debug com `python main.py --interactive`

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

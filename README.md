# Agente Estudos

Sistema agêntico Python que gera pastas de estudo completas e estruturadas para o **Obsidian** a partir de um tema, foco e fontes.

O LLM recebe um conjunto de ferramentas (busca web, download de artigos, transcrição de vídeos, escrita de arquivos) e decide por conta própria como executar a tarefa — sem sequência fixa. Funciona a partir de qualquer terminal, sem dependência de Claude Code ou VSCode — ou pela [interface web **estudAI**](#interface-web-estudai) (`uvicorn web.app:app --reload`).

Suporta Anthropic, OpenAI, Groq e Ollama.

## O que ele gera

Dado um tema (ex: *Redes Neurais*), o sistema produz:

```
~/obsidian/redes_neurais/
├── guia_de_estudos.md          # Ordem de leitura recomendada com checkpoints
├── proximos_passos.md          # Recomendações pós-estudo (gerado automaticamente)
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
│   ├── github_2.md             # README + notebooks de repositório GitHub
│   └── artigo_3.md             # Artigo resumido
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

## Fluxo Completo de Uso

O sistema tem três pontos de entrada que podem ser usados em sequência ou independentemente:

```
[1] buscar_fontes.py    →    [2] main.py    →    [3] proximos_passos.md
  Descobre fontes           Cria materiais      Recomenda o que estudar
  (curadoria LLM)          (agente + LLM)       a seguir (auto-gerado)
```

---

## 1. Descoberta de Fontes

Antes de criar a pasta de estudos, use `buscar_fontes.py` para descobrir e curar as melhores fontes automaticamente. Ele busca em YouTube, arXiv, Semantic Scholar, GitHub e web, e organiza os resultados em três camadas progressivas.

```bash
python buscar_fontes.py --tema "RAG" --foco "parent context chunking"
```

**Output interativo:**

```
┌──────────────────────────────────────────────────────────────────────┐
│  FONTES — RAG / Parent Context Chunking                              │
├──── 📚 FUNDAMENTOS ──────────────────────────────────────────────────┤
│ [1] ✓  📄 Retrieval-Augmented Generation...  arxiv.org      ★ 9.8   │
│         ↳ Paper seminal de RAG (Lewis et al.), 3.2k citações         │
│ [2]    ▶ RAG Tutorial - Karpathy            youtube.com    ★ 8.4    │
│         ↳ Introdução técnica de canal reconhecido, 54 min            │
├──── ⚡ TÉCNICAS MODERNAS ────────────────────────────────────────────┤
│ [3] ✓  📄 Parent Document Retriever...      arxiv.org      ★ 9.1   │
│         ↳ Resolve granularidade em RAG, base do LangChain            │
├──── 🔧 PRÁTICO ──────────────────────────────────────────────────────┤
│ [4] ✓  🐙 rag-from-scratch  github.com/langchain-ai ⭐47k  ★ 9.6   │
│         ↳ Notebooks oficiais do LangChain, didáticos e atualizados   │
└──────────────────────────────────────────────────────────────────────┘
Seleção: '1,3,4' · '1-4' · 'a' (todos) · Enter (manter ✓):
```

Após selecionar, o script pergunta se quer criar a pasta de estudos — se sim, chama `main.py` automaticamente com as fontes escolhidas.

### Opções do buscar_fontes.py

```
--tema   -t   Tema principal (obrigatório)
--foco   -f   Tópicos de foco específicos
--max    -m   Máximo de fontes por camada (padrão: 5)
--json   -j   Salvar resultado em JSON e sair (modo não-interativo)
--config       Caminho alternativo para config.yaml
```

### Camadas de busca

| Camada | O que busca | Fontes prioritárias |
|---|---|---|
| 📚 **Fundamentos** | Introduções, surveys, tutoriais base | Papers survey, vídeos de canais reconhecidos |
| ⚡ **Técnicas Modernas** | Estado da arte 2023-2025, papers avançados | arXiv recente, Semantic Scholar |
| 🔧 **Prático** | Implementações, código, arquiteturas reais | GitHub (repos com stars), notebooks Colab |

---

## 2. Criação dos Materiais

### Modo interativo

```bash
python main.py --interactive
# ou simplesmente:
python main.py
```

### Via argumentos

```bash
python main.py \
  --tema "Transformers e Atenção" \
  --foco "self-attention, multi-head attention, positional encoding" \
  --didatica "matemático com exemplos em PyTorch" \
  --pasta ~/obsidian/transformers \
  --fonte "https://youtu.be/iDulhoQ2pro" \
  --fonte "https://arxiv.org/abs/1706.03762" \
  --fonte "https://github.com/karpathy/nanoGPT"
```

### Sem fontes (só LLM + pesquisa web)

```bash
python main.py \
  --tema "Algoritmos de Ordenação" \
  --foco "quicksort, mergesort, complexidade" \
  --pasta ~/obsidian/algoritmos
```

### Chat sobre o conteúdo (RAG real — busca semântica)

Depois de gerar uma pasta de estudos, abra um chat interativo sobre o material. Na primeira
execução (e sempre que arquivos novos/alterados forem detectados pelo mtime), o sistema indexa
os `.md` da pasta em chunks com embeddings, cacheados em `<pasta>/.rag_index.json`. A cada
pergunta, o LLM decide por conta própria quantas vezes chamar a tool `search_vault` (busca por
similaridade de embeddings) antes de responder — não é mais um dump de todos os arquivos no
prompt, é busca real, como o NotebookLM ou a busca web do Claude.

```bash
# Q&A direto (estilo NotebookLM — cita a fonte de cada resposta)
python main.py --chat --pasta ~/obsidian/redes_neurais

# Tutor Socrático (nunca dá a resposta direta, faz perguntas)
python main.py --chat --pasta ~/obsidian/redes_neurais --chat-mode socratico

# Funciona igual apontando pra raiz do vault inteiro — pergunta através de tudo que você já estudou
python main.py --chat --pasta ~/obsidian
```

Dentro do chat, os comandos disponíveis são:

| Comando | Ação |
|---|---|
| `/modo` | Alterna entre Q&A e Socrático (limpa histórico) |
| `/novo` | Limpa o histórico da conversa |
| `/sair` | Encerra o chat |

### Opções completas do main.py

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

**`--mode agent`** (padrão): loop agêntico real. O LLM recebe ferramentas e decide sozinho o que chamar, em que ordem, podendo se adaptar ao conteúdo encontrado.

**`--mode pipeline`**: sequência fixa de 8 fases (legado). Útil quando o modelo não suporta tool_use (ex: alguns modelos Ollama).

---

## 3. Próximos Passos (Pós-estudo)

Ao final de cada execução do `main.py`, o sistema gera automaticamente `proximos_passos.md` na pasta de estudos. O arquivo analisa o que foi estudado e recomenda:

- **🗺️ Caminho Principal** — próximos 3-5 tópicos sequenciais a aprofundar
- **🔀 Desvios Pertinentes** — tópicos fora do escopo direto mas genuinamente valiosos, com justificativa não óbvia
- **🕸️ Conexões Inesperadas** — como o tema conecta-se com áreas aparentemente distantes

Exemplo para RAG:
```markdown
## 🔀 Desvios Pertinentes

### Teoria da Informação (Shannon)
**Conexão**: cross-entropy loss, que você usou nos embeddings, é a entropy de Shannon
**Por que vale**: entender o fundo matemático muda como você pensa sobre similaridade semântica
**Quando estudar**: em paralelo com o próximo tópico

### Psicologia Cognitiva — Chunking Humano
**Conexão**: o chunking de textos em RAG replica como humanos segmentam memória episódica
**Por que vale**: ajuda a intuir por que Parent Context Chunking funciona melhor
```

---

## Interface Web (estudAI)

Além da CLI, o projeto tem uma interface web local — **estudAI** — inspirada no NotebookLM:
galeria de "espaços" (pastas de estudo) na home, e um workspace de 3 painéis (estilo
VSCode/Obsidian) por espaço, com árvore de arquivos, leitor de markdown e abas de Busca de
Fontes / Geração de Conteúdo / Chat RAG.

A lógica de negócio é exatamente a mesma da CLI (`src/agent.py`, `src/source_discovery.py`,
`src/chat.py`) — a web é só uma camada de interface nova por cima (FastAPI + Jinja2 + Tailwind
via CDN + JS vanilla, sem build step nem dependência de Node).

### Rodando

```bash
uvicorn web.app:app --reload
```

Abra `http://localhost:8000`.

### Configuração

```yaml
# config.yaml (opcional — usa ~/obsidian como padrão se omitido)
web:
  vault_root: "~/obsidian"   # subpastas imediatas aparecem como "espaços" na home
```

"Abrir pasta existente" na home aceita qualquer caminho absoluto, sem se restringir a
`vault_root` — mesma flexibilidade que `--pasta` já tem na CLI.

### O que cada aba faz

| Aba | Equivalente na CLI |
|---|---|
| 📚 Buscar Fontes | `buscar_fontes.py` |
| ⚡ Gerar Conteúdo | `main.py` (modo `agent`), com checkboxes pra escolher quais dos 5 outputs opcionais (html, canvas, flashcards, quiz, mapa mental) gerar nessa execução |
| 💬 Chat | `main.py --chat`, com troca QA ↔ Socrático |

### Limitações conhecidas

- Sem streaming de token a token no chat (resposta vem completa, com indicador de "pensando...") — `src/llm.py` não suporta streaming de tokens hoje, na CLI nem na web
- Jobs de geração/busca de fontes rodam em memória (thread); se o servidor reiniciar no meio de um job, ele é perdido (mesmo custo de fechar um terminal com uma run de CLI em andamento)
- Histórico do chat não persiste entre reloads de página (gerenciado só no JS da página, sem sessão no servidor)

---

## Tipos de fonte aceitos

| Tipo | Exemplos | Como é processado |
|---|---|---|
| URL YouTube / Vimeo | `https://youtu.be/...` | yt-dlp legendas → Whisper se sem legenda |
| Arquivo de vídeo local | `/home/user/aula.mp4` | Whisper (Groq API ou local) |
| Repositório GitHub | `https://github.com/owner/repo` | README + notebooks .ipynb |
| Artigo / blog / docs | `https://medium.com/...` | BeautifulSoup text extraction |
| Paper (arxiv, ACM, IEEE) | `https://arxiv.org/abs/...` | Fetch + extração de texto |
| Nome de livro / curso | `"Deep Learning Goodfellow"` | Pesquisa web DuckDuckGo |

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

Vídeos do YouTube sem legendas disponíveis também usam esse pipeline automaticamente.

## Configuração da Descoberta de Fontes

```yaml
# config.yaml (todos os campos são opcionais)
source_discovery:
  github_token: ""          # ghp_... — aumenta rate limit GitHub de 60 para 5000 req/hora
  youtube_api_key: ""       # AIza... — opcional, não obrigatório
  max_per_camada: 5         # fontes por camada (padrão: 5)
  min_youtube_duration: 300 # duração mínima de vídeos em segundos (padrão: 5 min)
  min_github_stars: 100     # estrelas mínimas para repositórios GitHub
```

## Configuração de Embeddings (busca semântica do --chat)

```yaml
# config.yaml
embedding:
  provider: ollama   # ollama (local, sem custo) | openai | voyage
  ollama:
    base_url: "http://localhost:11434"
    model: "nomic-embed-text"   # bge-m3 (melhor em PT-BR) | all-minilm (menor)
  openai:
    api_key: ""                  # vazio = usa openai.api_key
    model: "text-embedding-3-small"
  voyage:
    api_key: ""
    model: "voyage-3-lite"
```

O `provider` de embedding é independente do `provider` de LLM do chat — você pode conversar via
Anthropic/Groq e indexar via Ollama local, por exemplo. Trocar de provider/modelo de embedding
força reindexação completa da pasta (vetores de modelos diferentes não são comparáveis).

---

## Estrutura do projeto

```
agente-estudos/
├── main.py                    # Entry point principal (CLI de criação)
├── buscar_fontes.py           # CLI de descoberta de fontes
├── setup.py                   # Wizard de configuração
├── config.example.yaml        # Template de config
├── .env.example               # Template de .env
├── requirements.txt
└── src/
    ├── agent.py               # Loop agêntico (modo padrão)
    ├── llm.py                 # Cliente LLM unificado (chat + tool_use)
    ├── pipeline.py            # Pipeline legado de 8 fases
    ├── distiller.py           # Processamento de fontes (YouTube, GitHub, papers, artigos)
    ├── source_discovery.py    # Descoberta e curadoria automática de fontes
    ├── indexer.py             # Chunking + embeddings + índice incremental (RAG)
    ├── tools/
    │   ├── registry.py        # Definições das ferramentas + executor
    │   ├── files.py           # Ferramentas de filesystem
    │   ├── web.py             # WebFetch + DuckDuckGo search
    │   ├── rag.py             # search_vault — busca semântica nos materiais indexados
    │   └── video.py           # yt-dlp + Whisper
    ├── chat.py                # Chat interativo (QA + Socrático) — RAG via search_vault
    ├── postprocessing.py      # Flashcards/quiz/próximos-passos/mapa-mental compartilhado (agent + pipeline + web)
    └── generators/
        ├── content.py         # Arquivos .md com 3 níveis de profundidade
        ├── canvas.py          # Canvas Obsidian
        ├── html_gen.py        # HTML (Catppuccin Mocha) com tabs de profundidade
        ├── flashcards.py      # Flashcards SM-2 (gerado automaticamente)
        ├── quiz.py            # Quiz MCQ (gerado automaticamente)
        ├── next_steps.py      # Recomendações pós-estudo (gerado automaticamente)
        └── visual_map.py      # Mapa mental radial (Catppuccin Mocha)
```

```
web/                            # Interface web estudAI — uvicorn web.app:app --reload
├── app.py                      # App FastAPI (monta static/, inclui routers)
├── deps.py                     # Config loader + modelo de "espaços" (sem banco)
├── jobs.py                     # JobManager em memória (threading) p/ operações longas
├── schemas.py                  # Modelos Pydantic dos payloads
├── markdown_render.py          # .md -> HTML (markdown-it-py) + wikilinks Obsidian
├── routers/
│   ├── spaces.py               # Home, workspace, árvore de arquivos, leitura de arquivo
│   ├── generation.py           # Geração de conteúdo (toggles) via job
│   ├── sources.py              # Busca de fontes via job
│   └── chat.py                 # Chat RAG síncrono
├── templates/                  # Jinja2 (base/home/workspace + partials/file_tree)
└── static/                     # css/theme.css + js/ (vanilla, sem build step)
```

## Ferramentas disponíveis para o agente

No modo `agent`, o LLM pode chamar:

| Ferramenta | O que faz |
|---|---|
| `web_search` | Pesquisa DuckDuckGo (sem API key) |
| `fetch_url` | Download e extração de texto de URLs |
| `transcribe_video` | Transcreve YouTube ou vídeo local (legendas → Whisper) |
| `search_sources` | Descobre fontes por tema/camada (YouTube, arXiv, GitHub) |
| `fetch_github_content` | Extrai README + notebooks de repositório GitHub |
| `recommend_next_steps` | Gera recomendações pós-estudo em `proximos_passos.md` |
| `write_file` | Escreve arquivo no filesystem |
| `read_file` | Lê arquivo existente |
| `create_directory` | Cria pasta |
| `list_directory` | Lista conteúdo de pasta |

No modo `--chat`, o LLM tem acesso só à tool `search_vault` (busca semântica nos materiais já
indexados) — não escreve nem lê arquivos arbitrários durante a conversa.

---

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

### Recomendações pós-estudo

Gerado automaticamente em `proximos_passos.md` ao final de cada execução.

- Caminho principal com tópicos sequenciais e comandos concretos para a próxima busca
- Desvios pertinentes com conexão explícita ao que foi estudado
- Conexões inesperadas com outras áreas do conhecimento

### Chat interativo (Q&A e Tutor Socrático)

Ver seção [Chat sobre o conteúdo](#chat-sobre-o-conteúdo) acima.

---

## Integração com Claude Code (agentes)

Se você usa **Claude Code**, dois agentes especializados estão disponíveis em `.claude/agents/`:

### `buscar-fontes`

Invocado automaticamente quando você pede curadoria de fontes sem ter URLs.

```
"Quero estudar attention mechanism, me ajuda a encontrar boas fontes"
→ agente buscar-fontes descobre YouTube + papers + GitHub, apresenta por camada,
  você seleciona, ele invoca criar-estudo
```

### `proximos-passos`

Invocado quando você quer saber o que estudar depois de terminar uma pasta.

```
"Terminei de estudar RAG em /obsidian/RAG, o que faço agora?"
→ agente lê os .md, gera caminho principal + desvios pertinentes + conexões,
  oferece chamar buscar-fontes para o próximo tópico
```

Os agentes usam o backend Python (`buscar_fontes.py` e `src/generators/next_steps.py`) quando disponível, e seus próprios tools (WebSearch, WebFetch) como fallback.

---

## Integração VSCode (opcional)

O repositório inclui `.vscode/tasks.json` e `.vscode/launch.json` com atalhos de conveniência. Eles chamam exatamente os mesmos comandos `python main.py` descritos acima — são opcionais e não adicionam nenhum comportamento novo.

- `Ctrl+Shift+B` → roda `python main.py --interactive`
- `F5` → debug com `python main.py --interactive`

## Dependências

- **Python 3.10+**
- `anthropic` / `openai` — clientes LLM
- `yt-dlp` — download de transcrições YouTube e busca de vídeos
- `requests` + `beautifulsoup4` — fetching de artigos e APIs (arXiv, GitHub, Semantic Scholar)
- `duckduckgo-search` — pesquisa web sem API key
- `rich` + `typer` — CLI e progress display
- `PyYAML` — leitura de config.yaml
- `python-dotenv` — suporte a .env (opcional)
- `fastapi` + `uvicorn` + `jinja2` + `python-multipart` — interface web estudAI (`uvicorn web.app:app`)
- `markdown-it-py` — conversão .md → HTML na interface web

## Licença

MIT

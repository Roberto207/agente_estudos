 Plano de Deploy — estudAI
                                                                                    ↑
   Contexto

   O usuário quer rodar o estudAI no celular Android de forma que o app acesse as pastas do próprio celular (vault Obsidian local). Isso descarta deploy em VPS/clo↑d e abordagem LAN-do-PC — o servidor precisa rodar diretamente no aparelho.

   A solução é Termux (terminal Linux para Android): roda o FastAPI/uvicorn no própr↑o aparelho, acessa /storage/emulated/0/obsidian (ou o path do Obsidian) no celular, e o usuário abre http://localhost:8000 no browser do celular.
                                                                                    ↑
   Adicionalmente, dois problemas de usabilidade precisam ser resolvidos antes do deploy:
   1. O workspace tem layout 3 colunas fixas (260px + 1fr + 380px) — no celular transborda horizontalmente.
   2. Não há UI para trocar de LLM — o usuário precisa editar config.yaml manualmente.
                                                                                    ↑
   ---
   O que mudar
                                                                                    ↑
   1. Mobile responsive — workspace layout

   Arquivo: web/static/css/theme.css + web/templates/workspace.html                 ↑

   Adicionar breakpoint em ≤ 768px que converte o grid de 3 colunas para layout de painel único com navegação por abas:                                             ↑
   - No mobile, .workspace-grid vira display: flex; flex-direction: column
   - 3 painéis ficam ocultos por padrão; uma barra de abas fixa na base da tela (arquivos / conteúdo / ferramentas) controla qual painel está visível
   - A barra de abas usa position: fixed; bottom: 0 para ficar sempre acessível
   - Mínimo de 44px em todos os alvos de toque (WCAG)                               ↑

   Em workspace.html, adicionar:
   <!-- Mobile bottom nav — só visível em telas pequenas -->                        ↑
   <nav class="mobile-bottom-nav md:hidden ...">
     <button data-panel="tree">📁 Arquivos</button>
     <button data-panel="content">📄 Conteúdo</button>                              ↑
     <button data-panel="tools">⚙️ Ferramentas</button>
   </nav>                                                                           ↑
   JS inline ou em workspace.js: ao clicar num botão, adiciona/remove classe hidden nos painéis.                                                                     ↑

   2. Modal de configurações de LLM — home

   Arquivos: web/templates/home.html, web/static/js/home.js, web/routers/spaces.py (ou novo web/routers/config.py), web/schemas.py                                      ↑

   UI (modal dlg-settings, idêntico em estrutura ao dlg-create):
   - Ícone ⚙️ no header da home → showModal() no dlg-settings                       ↑
   - <select id="settings-provider"> com opções: anthropic / openai / groq / ollama
   - Seções colapsáveis por provider (mostradas com JS ao mudar o select):          ↑
     - Anthropic: api_key, model
     - OpenAI: api_key, model                                                       ↑
     - Groq: api_key, model (free tier — mostrar dica)
     - Ollama: base_url, model (nota: local no Termux ou desktop)
   - Inputs de API key com type="password" (mascarado)
   - Botão "Salvar" → PUT /api/config
   - Para Ollama: botão "Testar conexão" → GET /api/config/ollama-health            ↑

   Backend — endpoint PUT /api/config:
   PUT /api/config                                                                  ↑
   Body: { provider, anthropic: {...}, openai: {...}, groq: {...}, ollama: {...} }
   - Lê config.yaml atual (caminho resolvido via deps._CONFIG_PATHS)                ↑
   - Atualiza somente os campos enviados (merge parcial)
   - Escreve de volta com yaml.dump                                                 ↑
   - Retorna { ok: true }
                                                                                    ↑
   Endpoint GET /api/config/ollama-health:
   GET /api/config/ollama-health
   - Faz GET em {ollama.base_url}/api/tags (endpoint padrão do Ollama)
   - Retorna { ok: true, models: [...] } ou { ok: false, error: "..." }
                                                                                    ↑
   Novo arquivo: web/routers/config.py com esses dois endpoints.
   Registrar no web/app.py: app.include_router(config.router)
                                                                                    ↑
   3. Script de setup Termux
                                                                                    ↑
   Novo arquivo: setup_termux.sh (na raiz do projeto)

   #!/data/data/com.termux/files/usr/bin/bash
   # Setup do estudAI no Termux (Android)
   pkg update -y && pkg install -y python git clang libffi openssl                  ↑
   pip install -r requirements.txt
 # Cria config.yaml se não existir
   [ -f config.yaml ] || cp config.example.yaml config.yaml                         ↑
   echo "Edite config.yaml e defina seu provider e API key antes de iniciar."
   echo "Depois rode: uvicorn web.app:app --host 127.0.0.1 --port 8000"             ↑

   Também criar start.sh (convenience wrapper):
   #!/data/data/com.termux/files/usr/bin/bash
   cd "$(dirname "$0")"
   uvicorn web.app:app --host 127.0.0.1 --port 8000                                 ↑

   vault_root no Termux: o path Obsidian no Android é tipicamente:                  ↑
   - /storage/emulated/0/obsidian (Obsidian com permissão de armazenamento externo)
   - Ou ~/storage/shared/obsidian (via termux-setup-storage)                        ↑

   O usuário deve ajustar web.vault_root no config.yaml para o path correto.        ↑

   ---
   Arquivos críticos

   ┌──────────────────────────────┬─────────────────────────────────────────────────↑
   │           Arquivo            │                     Mudança                     │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ web/static/css/theme.css     │ Adicionar breakpoint @media (max-width: 768px)  ↑
   │                              │ com layout mobile                               │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ web/templates/workspace.html │ Adicionar barra de abas mobile, classes de      ↑
   │                              │ painel                                          │
   ├──────────────────────────────┼─────────────────────────────────────────────────↑
   │ web/templates/home.html      │ Adicionar botão ⚙️ + modal dlg-settings         │
   ├──────────────────────────────┼─────────────────────────────────────────────────↑
   │ web/static/js/home.js        │ Lógica de save das configurações                │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ web/routers/config.py        │ Novo — PUT /api/config e GET                    │
   │                              │ /api/config/ollama-health                       │
   ├──────────────────────────────┼─────────────────────────────────────────────────↑
   │ web/app.py                   │ Registrar config.router                         │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ web/schemas.py               │ Adicionar ConfigUpdateRequest                   │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ setup_termux.sh              │ Novo — script de setup                          │
   ├──────────────────────────────┼─────────────────────────────────────────────────┤
   │ start.sh                     │ Novo — wrapper de inicialização                 │
   └──────────────────────────────┴─────────────────────────────────────────────────┘

   ---
   Funções/utilitários a reutilizar

   - web/deps.py::load_config() — reutilizar para ler config atual no endpoint PUT
   - web/deps._CONFIG_PATHS — usar para descobrir onde escrever o config.yaml
   - Estrutura dos outros modals em home.html (dlg-create, dlg-open) — copiar padrão visual                                                                           ↑
   - EstudAI.api.post/put em api.js — reutilizar para o save das settings

   ---
   Nota sobre Ollama no Android

dar Ollama no Termux é tecnicamente possível (via termux-exec + binário ARM64) mas pesado para aparelhos com menos de 8GB RAM. Para celular, recomendar Groq (free tier, leve, sem instalação). O modal deve mostrar uma dica: "Para uso móvel, Groq ratuito) é o mais prático. Ollama funciona melhor no desktop."

   ---
 Verificação

   1. Rodar em desktop: uvicorn web.app:app --reload
     - Abrir / — verificar botão ⚙️ no header
     - Abrir modal settings, trocar provider, salvar → config.yaml atualizado
   - Testar conexão Ollama → resposta correta
 2. Testar workspace em DevTools com viewport 375×812 (iPhone SE):
     - Três painéis empilhados, barra de abas na base visível
     - Clicar em cada aba muda o painel visível
- Inputs e botões têm target size ≥ 44px
 No Termux (Android):
- bash setup_termux.sh → instala dependências sem erro
- Editar config.yaml com vault_root = path do Obsidian no celular
- bash start.sh → uvicorn sobe
- Abrir http://localhost:8000 no browser do celular → home lista espaço

# G1 · Orquestração em código (driver Python + `claude -p`) no lugar do orquestrador LLM

Data: 2026-11-07. Tema A1. Restrição: só login da assinatura Pro, sem API key.

Resposta direta: sim, dá para trocar o orquestrador LLM (69% dos tokens) por um driver Python que chama `claude -p` com o login da assinatura, e ainda é o caminho oficialmente descrito. Duas pegadinhas: (1) o modo `--bare`, o recomendado para scripts, NÃO funciona com login de assinatura; (2) a regra de cobrança do `claude -p` já mudou e foi pausada, então pode mudar de novo. Ganho estimado: cerca de 68% menos tokens por série de 5 episódios e 74% por série de 10, mais o fim do limite de 5 episódios.

## 1. `claude -p` com login Pro é suportado e permitido? Conta no limite do plano?

- `claude -p` é o modo não interativo oficial; sai com código 0 em sucesso e diferente de zero em falha, para o script decidir por ele. [FATO: F1]
- Com login de plano, `claude -p` e o Agent SDK continuam consumindo os limites da assinatura. A página de ajuda (atualização de 7/10/2026) diz que os créditos mensais de API de Max, Ultra e Team só cobrem o SDK e o `claude -p` quando rodados com chave de API do Console; sem chave, "still draw from your subscription limits". A mudança anunciada antes (separar o uso programático em crédito próprio) foi pausada em 15/6/2026 ("We've paused the previously-announced changes"). [FATO: F2]
- Pro não aparece na lista de planos com crédito mensal de API. Blogs de terceiros que citam "US$ 20 para Pro" descrevem a mudança que foi pausada; ignorar. [FATO: F2] [INFERÊNCIA sobre os blogs, F8]
- Termos: Free, Pro, Max e Ultra caem nos Termos de Consumidor. Os limites anunciados "assumem uso comum e individual do Claude Code e do Agent SDK". OAuth é "destinado a uso comum"; o que é proibido é revender, intermediar ou rotear pedidos de terceiros por credenciais de plano, ou coletar tokens de login. [FATO: F3]
- Uso pessoal, na sua máquina, no seu projeto, com o binário original: dentro do descrito. Um driver que gera 5 a 10 episódios em sequência para você é uso individual. [INFERÊNCIA: não há texto que fale de "laço" em Pro; a regra é o uso ser individual e comum]
- Não há restrição documentada de uso "em laço". O que existe é o limite de 5 h + semanal, compartilhado com o claude.ai e as sessões interativas. Ao estourar, a mensagem é "You've hit your session limit" com a hora do reset. [FATO: F4]
- Risco regulatório: a política de cobrança do `claude -p` mudou duas vezes em 2026 (anúncio, pausa, atualização de outubro). [FATO: F2] Mitigação: o driver lê o custo de cada chamada e é fácil de desligar (volta ao orquestrador LLM). [INFERÊNCIA]

## 2. Flags de custo e isolamento numa chamada headless

Versão local do binário: 2.1.319 (confirmado com `claude --version` e `claude -p --help`). [FATO: F5]

| Necessidade | Flag | Observação |
|---|---|---|
| Modelo | `--model sonnet\|opus\|haiku` ou nome completo; `--fallback-model` | [FATO: F5] |
| Esforço | `--effort low\|medium\|high\|xhigh\|max` | [FATO: F5]. Não dá para desligar o raciocínio nos modelos 5.5, só baixar o esforço [FATO: F6] |
| Limite de turnos | `--max-turns N` (só em `-p`) | [FATO: F7] |
| Teto de gasto | `--max-budget-usd` | [FATO: F5]. Em assinatura o valor é estimativa local; serve de trava de segurança, não de cobrança [FATO: F1] |
| Ferramentas | `--tools "Read,Edit"` define o conjunto; `--tools ""` desliga todas; `--allowedTools` e `--disallowedTools` controlam permissão | [FATO: F5] |
| Permissões sem humano | `--permission-mode dontAsk` e `--permission-prompts none` | [FATO: F1]. Desde a 2.1.302 o `-p` começa em modo Manual: chamada que precisa de aprovação é negada |
| System prompt | `--system-prompt[-file]` substitui o padrão; `--append-system-prompt[-file]` anexa | [FATO: F7]. Trocar o prompt também tira o snapshot de git status [FATO: F1] |
| Contexto por máquina | `--exclude-dynamic-system-prompt-sections` | Ajuda o cache; só vale com o prompt padrão [FATO: F7] |
| Isolamento | `--safe-mode`: desliga CLAUDE.md, skills, plugins, hooks, MCP, comandos e agentes personalizados; autenticação e ferramentas nativas seguem normais | [FATO: F5]. É o equivalente utilizável do `--bare` |
| Isolamento parcial | `--strict-mcp-config` (só MCP da `--mcp-config`), `--setting-sources user,project,local` (lista vazia para não carregar), `--disable-slash-commands` | [FATO: F5]. Se a lista vazia funciona: lacuna |
| `--bare` | Pula hooks, memória, CLAUDE.md, plugins e MCP, mas NÃO lê OAuth nem keychain: exige `ANTHROPIC_API_KEY` | [FATO: F1]. Inutilizável com só Pro |
| Saída | `--output-format json` traz `result`, `session_id`, `total_cost_usd`, custo por modelo, uso (`usage`) e, com `--json-schema`, o campo `structured_output` | [FATO: F1]. O custo é estimativa local a preço de lista, não é a cobrança do plano [FATO: F1]. Presença exata de `num_turns` e dos campos de `usage`: não confirmada por execução (lacuna) |
| Sem persistência | `--no-session-persistence` (não gera transcrição nem permite retomar) | [FATO: F7] |
| Agente de `~/.claude/agents/` | `--agent <nome>` usa o agente na sessão; `--agents <json-ou-arquivo>` define agentes na hora (arquivo aceito com `-p` desde a 2.1.281) | [FATO: F7]. Que `--agent gerar-podcast` carregue o arquivo de `~/.claude/agents` sem `--safe-mode`: [INFERÊNCIA]. Com `--safe-mode`, agentes personalizados ficam desligados [FATO: F5], então use `--agents` |
| Retomar | `--resume <session_id>`, `--continue`, `--session-id <uuid>`, `--fork-session` | [FATO: F1]. Retomar reporta o custo acumulado da conversa [FATO: F1] |
| Subagentes no fluxo | `--forward-subagent-text` e `parent_tool_use_id` no `stream-json` | [FATO: F1]. Não serve ao driver, que evita subagentes |

Desenho recomendado de cada chamada (INFERÊNCIA, a validar no A/B):
- Crítico: `--model opus --tools "" --json-schema <schema do crítico> --max-turns 2`. O driver passa o `prompts/podcast_critico.md` (sem frontmatter) em `--system-prompt-file`, o conteúdo de ENTRADAS e o roteiro por stdin, e grava o JSON ele mesmo. Some o Read, o Write e as voltas de ferramenta: vira 1 turno.
- Redator, 1ª escrita: `--model sonnet --tools ""` com o prompt do redator no system prompt; o driver grava o roteiro, roda o lint. Evita Read e Write do agente.
- Redator, reescrita: `--tools "Read,Edit"` (corrigir com Edit fala por fala é mais barato em saída do que regravar 3 mil palavras, como o próprio `gerar-podcast.md` já orienta); passar a lista de apontamentos do crítico e os achados do lint no prompt.
- Todas: `--no-session-persistence`, `--safe-mode` (ou `--strict-mcp-config --disable-slash-commands --setting-sources ""`), `--permission-mode dontAsk`, `--output-format json`.

## 3. Custo fixo por chamada e a conta (5 e 10 episódios)

Custo fixo de uma chamada headless:
- Não há número oficial. O 1º pedido do orquestrador atual já tem cerca de 21 mil tokens (system prompt do Claude Code, ferramentas, CLAUDE.md global, lista de skills, instruções de MCP). [FATO: 00_contexto, medido 11/10/2026] Como estimativa para uma chamada headless com o ambiente atual: 15 a 25 mil tokens, quase todos em cache. [SUPOSIÇÃO]
- Este ambiente tem muitos conectores (Vercel com mais de 200 ferramentas, Supabase, Gmail, etc.); só os nomes entram no contexto, mas as instruções dos servidores entram. [FATO: observado no prompt desta sessão; F6 diz que as definições ficam adiadas] `--safe-mode` ou `--strict-mcp-config` deve cortar isso. [INFERÊNCIA]
- Com `--tools ""` e prompt próprio, o custo fixo cai bem abaixo disso. [SUPOSIÇÃO]

Por que o custo fixo não pesa contra o driver: hoje o redator e o crítico já são subagentes de contexto limpo, então o custo de partida deles já está dentro dos 20% e 11% medidos. O que sai é o contexto crescente do orquestrador. [INFERÊNCIA]

Conta (tokens processados, quase tudo leitura de cache; uso de proxy do peso no plano, ver lacuna):

| Item | Série de 5 | Série de 10 |
|---|---|---|
| Atual, total | 0,74 M x 5 = 3,70 M | 0,9 M x 10 = 9,0 M [FATO: 00_contexto] |
| Orquestrador (69% na série de 5) | 2,57 M [FATO] | 9,0 - 2,29 = 6,7 M [INFERÊNCIA: assume redator + crítico constantes] |
| Redator + crítico (31%) | 0,23 M/ep x 5 = 1,15 M | 0,23 x 10 = 2,29 M [INFERÊNCIA] |
| Driver: planejamento (1 chamada `claude -p` do planejador, hoje feito pelo orquestrador) | cerca de +0,05 M [SUPOSIÇÃO] | +0,05 M |
| Driver: total | cerca de 1,2 M | cerca de 2,34 M |
| Economia | cerca de 2,5 M (-68%) | cerca de 6,7 M (-74%) |

- Em linguagem simples: o orquestrador é o "gerente" que relê toda a conversa a cada passo; o driver em Python é uma planilha que só chama quem trabalha, sem reler nada. O custo passa de quadrático para linear no número de episódios. [INFERÊNCIA a partir de 00_contexto]
- Com reescrita: cada reescrita acrescenta 1 chamada de redator + 1 de crítico (já incluídas no 0,23 M/ep médio medido, porque as séries medidas tiveram reescritas). [INFERÊNCIA]
- Ganho adicional possível (crítico sem ferramentas, prompt no system, sem Read): 10 a 30% em cima dos 0,23 M/ep. [SUPOSIÇÃO, medir]
- O limite de 5 episódios por execução deixa de ter razão de existir, porque o custo por episódio é constante. [INFERÊNCIA; o motivo registrado em 8.3 é o contexto crescente do orquestrador]
- Cache entre chamadas: chamadas com o mesmo prefixo (mesmo modelo, ferramentas e system prompt) dentro do tempo de vida do cache reaproveitam leitura; mudar modelo ou ferramentas entre chamadas cria outro prefixo. [FATO: F6 descreve cache de prefixo e invalidação; aplicação ao driver: INFERÊNCIA] Por isso: um conjunto de flags fixo para todas as chamadas do redator e outro para as do crítico, e rodar os episódios sem pausas longas.
- Aviso de medida: "tokens processados" é majoritariamente leitura de cache; quanto isso pesa no limite Pro não está documentado. [SUPOSIÇÃO] Comparar também a barra do `/usage` antes e depois.

## 4. O que se perde ao tirar o LLM do controle, e como o código cobre

O próprio `podcast_orquestracao.md` descreve o orquestrador como mecânico (rodar comandos e passar caminhos), e `podcast-serie.md` diz "seu trabalho é mecânico e disciplinado". [FATO: arquivos lidos] Mapeamento:

| O que o LLM fazia | Substituto no código | Já existe? |
|---|---|---|
| Decidir entre `valida`, `desatualizada_ou_invalida`, `ausente` (8.1) | `status` devolve JSON; o driver ramifica e, no caso desatualizada, para e mostra o `detalhe` | Sim (`agente.py status`) |
| Planejar a série (8.2) e corrigir erros do plano (código 3, até 2 vezes, depois `--forcar`) | 1 chamada `claude -p --json-schema` com o prompt do planejador; laço de até 2 correções passando os `erros` na chamada; depois `serie --forcar` | O laço de decisão é simples; a chamada de planejamento é nova |
| Gerar só episódios com `existe: false`, em ordem | laço em Python sobre `status` | Sim (dados no `status`) |
| Encadear `finalizar N && entradas N+1` | duas chamadas de subprocesso em sequência | Sim |
| Ler o `lint` do redator e pular o crítico se reprovado | `python -m src.podcast.lint <roteiro>` (código 0 aprovado ou aviso, 1 reprovado, com `achados` e `bloqueia`) | Sim |
| Decidir se o crítico apontou problema | `critic.normalizar(json)` já calcula `aprovado` no código (o crítico não grava esse campo) | Sim; o driver importa a função |
| Reescrever uma vez e re-criticar | contador no driver: no máximo 1 reescrita guiada pelo crítico e até 1 reescrita de lint por geração (como hoje) | Sim, regra já escrita |
| Reescrita que reprova no lint | `finalizar` restaura sozinho `backup_NN.md` e a crítica anterior (`restaurado_do_backup`) | Sim |
| Crítico falhou ou não gravou JSON | `--critica-indisponivel`; `finalizar` já trata JSON inválido como `indisponivel` (fail-open) | Sim |
| Retomar depois de interrupção | `status` mostra os episódios que faltam; arquivos de `podcast/.agente/` são de trabalho | Sim |
| Erros de uso | `agente.py` sai com 1 (`ErroPodcast`, mensagem em JSON) e 3 (plano com erros) | Sim |

O que realmente se perde (INFERÊNCIA):
- Tratar situações imprevistas com bom senso (arquivo inesperado, saída do redator fora do formato, mensagem de erro nova). Cobertura: o driver trata cada chamada como falha se o código de saída for diferente de zero ou se o JSON vier sem `result` ou `structured_output`; tenta de novo 1 vez; se falhar de novo, marca o episódio como `nao_avaliado` e segue ou para (decisão configurável) e escreve o motivo.
- Limite de uso do plano no meio da série: o driver detecta a mensagem de limite (no JSON do `result` ou nos eventos `api_retry` com `error: rate_limit`) [FATO: F1 lista a categoria `rate_limit`; formato exato da mensagem em JSON: lacuna], para limpo e imprime "retome com o mesmo comando depois de HH:MM". Como o `status` é idempotente, retomar é só rodar de novo.
- Relatório final (8.4): é uma tabela, feita pelo `relatorio.json` que o `finalizar` já grava.
- Falha silenciosa de qualidade: sem o LLM revisando o fluxo, o único controle é o lint e o crítico. Mantê-los é obrigatório; é por isso que o modo econômico não pode tirar o crítico. (Redução do crítico é tema de outro pesquisador.)

Observação de permissões: o redator precisa de Bash para chamar o lint hoje; no desenho do driver, o lint passa a ser chamado pelo driver, então a chamada do redator pode rodar sem Bash. O `agente.py backup` antes da reescrita também passa para o driver. [INFERÊNCIA]

## 5. Padrões oficiais da Anthropic

- "Building effective agents" define workflows como sistemas em que LLMs e ferramentas são orquestrados "through predefined code paths" e agentes como sistemas em que o LLM "dynamically direct their own processes". Recomenda "finding the simplest solution possible, and only increasing complexity when needed". Diz que workflows dão "predictability and consistency for well-defined tasks", e que agentes são melhores quando se precisa de "flexibility and model-driven decision-making at scale". [FATO: F9] Isso sustenta a mudança: o fluxo do podcast tem passos fixos e conhecidos, e o orquestrador LLM é um agente onde cabe um workflow.
- Os padrões do artigo casam com o desenho: prompt chaining (entradas, redator, lint, crítico, finalizar) e evaluator-optimizer (um LLM gera, outro avalia em laço, bom "when we have clear evaluation criteria", e aqui há critérios e JSON fixos). [FATO: F9]
- "start by using LLM APIs directly: many patterns can be implemented in a few lines of code"; frameworks "obscure the underlying prompts". [FATO: F9] A recomendação é de API; aqui o análogo é `claude -p` num driver pequeno, sem framework. [INFERÊNCIA]
- A doc de custos recomenda delegar operações verbosas a subagentes, mas lembra que "cada subagente envia as próprias requisições por cima da conversa principal" e que o contexto completo é reenviado a cada chamada, lido do cache a taxa reduzida; recomenda Sonnet em vez de Opus quando possível e limpar contexto entre tarefas. [FATO: F6] Isso sustenta o contexto limpo por chamada.
- O que contradiz ou limita: o próprio artigo diz que agentes são a melhor opção quando o número de passos não é previsível. Se no futuro o podcast precisar de ramificações abertas (por exemplo, decidir sozinho refazer o plano), o driver terá de ganhar regras explícitas ou chamar um LLM só nesse ponto. [INFERÊNCIA]
- A página de legal diz que "developers building products or services" devem usar API key. Esta é uma ferramenta pessoal do próprio usuário, não um produto de terceiros; se um dia o driver for oferecido a outras pessoas, a regra muda. [FATO: F3; aplicação: INFERÊNCIA]

## Recomendações para o modo econômico

| Recomendação | O que muda | Como ligar/desligar | Ganho estimado | Risco de qualidade | Métrica do A/B |
|---|---|---|---|---|---|
| R1. Driver Python no lugar do orquestrador LLM | Novo módulo (ex.: `src/podcast/driver.py`) que chama `agente.py`, o lint e `claude -p` para redator e crítico; `podcast-serie` fica como caminho alternativo | Comando novo `python -m src.podcast.driver <pasta>` (modo econômico ligado) contra pedir o `podcast-serie` ao Claude (desligado). Nenhum arquivo de agente é apagado | Série de 5: 3,70 M para cerca de 1,2 M (-68%). Série de 10: 9,0 M para cerca de 2,34 M (-74%) | Baixo: as decisões já estão no código; risco em casos fora do previsto, tratados por parada com mensagem | tokens por episódio (soma de `usage` dos JSON do driver); barra do `/usage` antes e depois; nº de episódios que fecham sem intervenção; campos de `relatorio.json` (lint, crítica, reescritas) iguais entre os modos |
| R2. Chamadas isoladas com `--safe-mode` e prompt próprio | Cada chamada carrega só o prompt do redator ou do crítico, sem CLAUDE.md, skills, MCP e hooks | Flag `--safe-mode` (ou `--strict-mcp-config --disable-slash-commands --setting-sources ""`) na lista de argumentos do driver; remover a flag desliga | Corta uma parte dos 15 a 25 mil tokens fixos por chamada; ver conta: 4 a 5 chamadas por episódio x alguns mil tokens [SUPOSIÇÃO] | Baixo; atenção: `--safe-mode` desliga agentes personalizados, então usar `--system-prompt-file` ou `--agents` | tokens da 1ª requisição (`usage` da 1ª chamada) com e sem a flag |
| R3. Crítico sem ferramentas, com saída estruturada | Crítico recebe tudo em stdin, devolve JSON via `--json-schema`; o driver grava `critica_NN.json` | `--tools "" --json-schema ...` ligado; desligado volta ao agente `podcast-critico` com Read e Write | 10 a 30% dos 0,081 M/ep do crítico [SUPOSIÇÃO] | Médio: o schema precisa conter todos os campos que `critic.normalizar` espera; o Opus tem de obedecer ao schema | veredito do crítico igual entre os dois modos em 5 roteiros iguais; JSON válido na 1ª chamada (%) |
| R4. Reescrita com Read e Edit, sem Bash | Driver faz o backup e o lint; o redator só corrige falas apontadas | `--tools "Read,Edit"` na reescrita | Pouco, evita regravar o texto todo; mantém o que já existe | Baixo | % de reescritas que passam no lint e no crítico; palavras de saída |
| R5. Tirar o limite de 5 episódios no modo driver | Remover a regra de 8.3 apenas no caminho do driver; o limite do plano passa a ser o de parar e retomar | Parâmetro `--max-episodios` do driver (padrão sem limite); `podcast-serie` mantém o limite | Evita reabrir sessão e reler contexto a cada 5 episódios; custo por episódio fica constante | Baixo, com a parada por limite de uso | tokens por episódio na série de 10 e de 15 (devem ficar iguais ao da série de 5) |
| R6. Parar limpo no limite do plano | Driver detecta `rate_limit` e a mensagem de limite e imprime a hora de retomada | Sempre ligado; é só proteção | Evita queimar o resto da janela em tentativas inúteis | Nenhum | nº de chamadas desperdiçadas por série |

Ordem sugerida de implementação para o A/B: R1 sozinho (mantendo as flags atuais) para isolar o ganho do orquestrador; depois R2, R3 e R4 um por vez.

## Lacunas

- Não rodei `claude -p` de verdade (instrução do briefing); então: custo fixo real por chamada, campos exatos do JSON (`num_turns`, `usage`) e a forma da mensagem de limite no JSON não foram medidos. Primeiro passo do A/B: 1 chamada curta com `--output-format json` para registrar esses campos.
- Se `--safe-mode` remove também os conectores do claude.ai (Vercel, Supabase etc.) e se `--setting-sources ""` é aceito: a ajuda local diz que o `--safe-mode` desliga MCP, mas não testei.
- Se `--agent gerar-podcast` encontra o agente em `~/.claude/agents` sem `--safe-mode`: não testado; a alternativa segura é `--system-prompt-file`.
- Quanto "tokens processados" (leitura de cache) pesa no limite do Pro: não documentado; os números de economia estão em tokens processados, não em porcentagem da cota.
- Percentual real de reescritas por série e custo de uma chamada de planejamento via `claude -p`: não medidos; a conta supõe que as séries medidas já têm a taxa típica de reescrita.
- O texto do Termo de Consumidor sobre "uso automatizado" não foi lido no original; usei a página de legal do Claude Code.
- Valores exatos de créditos mensais descritos por blogs (não oficiais) não foram verificados e não afetam o Pro.

## Fontes

- F1. Run Claude Code programmatically (headless / `claude -p`), https://code.claude.com/docs/en/headless, acesso 2026-11-07.
- F2. Use the Claude Agent SDK with your Claude plan (Central de Ajuda), https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan, acesso 2026-11-07 (atualizações de 15/6/2026 e 7/10/2026).
- F3. Legal and compliance (Claude Code), https://code.claude.com/docs/en/legal-and-compliance, acesso 2026-11-07.
- F4. Manage costs effectively, seção "When a developer asks about a limit", https://code.claude.com/docs/en/costs, acesso 2026-11-07.
- F5. `claude --help` e `claude -p --help` locais, versão 2.1.319, 2026-11-07.
- F6. Manage costs effectively (redução de tokens, cache, MCP adiado, esforço, subagentes), https://code.claude.com/docs/en/costs, acesso 2026-11-07.
- F7. CLI reference, https://code.claude.com/docs/en/cli-reference, acesso 2026-11-07.
- F8. Resultado de busca com blogs de terceiros sobre créditos (não oficial, usado só como alerta), consulta 2026-11-07.
- F9. Building effective agents, Anthropic Engineering, https://www.anthropic.com/engineering/building-effective-agents, acesso 2026-11-07.
- Arquivos locais lidos: `specs/economia/00_contexto.md`, `prompts/podcast_orquestracao.md`, `~/.claude/agents/podcast-serie.md`, `gerar-podcast.md`, `podcast-critico.md`, `src/podcast/agente.py`.

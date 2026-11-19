# G4 · Contexto de cada agente: custo fixo (D1), contexto que cresce (B2) e material menor (D2)

Data: 2026-11-07. Escopo: podcast (`podcast-serie`, `gerar-podcast`, `podcast-critico`) e `criar-estudo`. Tokens locais estimados com 3,5 caracteres por token (português); onde há uso real gravado nas transcrições, o número é medido e vem marcado.

Convenção: `[FATO: Fn]` = fonte numerada no fim; `[MEDIDO]` = medido por mim em arquivos locais ou transcrições; `[INFERÊNCIA]`, `[SUPOSIÇÃO]`. Preço de API só aparece como pista de peso relativo (a restrição é o limite do plano Pro).

## 0. Resposta curta

1. D1 (custo fixo) é pequeno no podcast e grande só no `criar-estudo`. [MEDIDO] O primeiro pedido do redator (`gerar-podcast`) tem ~6,3 mil tokens e o do crítico ~4,5 mil. O do `criar-estudo` tem ~19–21 mil. O ganho possível de D1 é de 1 a 6 mil tokens por chamada, e quase todo no `criar-estudo`.
2. B2 (contexto que cresce) é o item grande. [MEDIDO] No `criar-estudo`/orquestrador de 77 chamadas, 98% dos 5,96 M tokens são releitura de cache e o contexto vai de 21 mil a 117 mil. O padrão oficial que ataca isso é subagente com contexto limpo por unidade de trabalho. Estimativa: de -45% a -65% dos tokens por pasta.
3. D2 (material menor) rende pouco em tokens (~2–3% do episódio), mas melhora a qualidade: hoje o corte do orçamento é `t[:cota]`, que joga fora o fim de cada arquivo. [MEDIDO] Código, mermaid e tabelas são 22–32% dos caracteres das pastas reais.

## 1. Custo fixo por sessão/subagente (D1)

### 1.1 O que entra no contexto inicial

- [FATO: F2] Subagente comum começa com janela nova. Recebe: o prompt do próprio agente (corpo do `.md`) mais detalhes de ambiente (não recebe o prompt de sistema do Claude Code); a mensagem de tarefa; a hierarquia inteira de CLAUDE.md (Explore e Plan pulam); o git status (Explore e Plan pulam); skills listadas em `skills` (conteúdo completo); e a lista de agentes irmãos, só se tiver `SendMessage`.
- [FATO: F2] Subagentes herdam as ferramentas nativas e as ferramentas MCP da conversa principal, restringidas por `tools`/`disallowedTools`/`mcpServers`.
- [FATO: F3] Definições de ferramentas MCP são adiadas por padrão: só nomes e instruções do servidor entram no contexto até a ferramenta ser usada. O `/context` mostra o que ocupa espaço.
- [FATO: local, esta sessão] A ferramenta `Agent` exibe a lista de todos os agentes com a descrição completa, incluindo os blocos `<example>`. [INFERÊNCIA] Quem tem `Agent` em `tools` (`criar-estudo`, `podcast-serie`, `buscar-fontes`, `plano-estudos`...) carrega essa lista em toda chamada.
- [FATO: F2] As descrições dos seus agentes (exceto os nativos) passam por um orçamento de 15 mil tokens; acima disso aparece aviso no início.

### 1.2 Tabela de medições locais

| Item | Caracteres | ~Tokens (3,5 c/t) | Onde pesa | Fonte |
|---|---|---|---|---|
| Descrições dos 18 agentes (frontmatter) | 17.420 | ~5.000 (33% do orçamento de 15 mil) | toda conversa principal; [INFERÊNCIA] todo agente com `Agent` | [MEDIDO] `~/.claude/agents/*.md` |
| Parte dessas descrições que é `<example>` | 9.515 (55%) | ~2.700 | idem | [MEDIDO] |
| Maiores descrições | ai-lecture-distiller 1.961, corretor-redacao-enem 2.176, carreira-ia 1.981, repertorios-enem 1.955 | ~550–620 cada | idem | [MEDIDO] |
| Descrições dos 9 skills do usuário | 8.166 | ~2.300 | conversa principal (a lista real tem também skills de plugin/nativos, não medidos) | [MEDIDO] `~/.claude/skills/*/SKILL.md` |
| `~/.claude/CLAUDE.md` | 1.021 | ~290 | todo subagente (sem `omitClaudeMd`) | [MEDIDO] |
| CLAUDE.md do projeto `agente_estudos` | não existe | 0 | | [MEDIDO] |
| Corpo de `criar-estudo.md` | 20.187 | ~5.800 | toda chamada do `criar-estudo` | [MEDIDO] |
| Corpo de `gerar-podcast.md` / `podcast-critico.md` / `podcast-serie.md` | 3.603 / 2.056 / 1.842 | ~1.000 / ~590 / ~530 | cada chamada do respectivo agente | [MEDIDO] |
| `prompts/podcast_redator.md` | 7.498 (1.166 palavras) | ~2.100 | lido pelo redator, fica no contexto | [MEDIDO] |
| `prompts/regras_didaticas.md` | 9.886 (1.496 palavras) | ~2.800 | lido pelo `criar-estudo`, fica no contexto até o fim | [MEDIDO] |
| `prompts/podcast_orquestracao.md` | 6.268 | ~1.800 | lido pelo orquestrador | [MEDIDO] |
| 1º pedido: redator `gerar-podcast` (tools Read, Write, Edit, Bash) | | **~6.300** | | [MEDIDO] 12 execuções, 6.275–7.290 |
| 1º pedido: crítico `podcast-critico` (tools Read, Write) | | **~4.500** | | [MEDIDO] 20+ execuções, 4.446–4.676 |
| 1º pedido: `criar-estudo` (7 ferramentas, inclui `Agent`) | | **~19.000–21.300** | | [MEDIDO] 4 execuções |
| 1º pedido: `Explore` (todas as ferramentas) | | ~24.800–24.900 | | [MEDIDO] 3 execuções |
| Servidores MCP configurados | `settings.json` não define nenhum. Aparecem como adiados: conectores do claude.ai (Canva, Slack, Gmail, Google Calendar, Google Drive, Spotify, Supabase, Vercel, Claude Docs), plugins de produtividade (Atlassian, ClickUp, Linear, Monday, Notion, Slack) e `claude-in-chrome` | só nomes: ~500 nomes, [INFERÊNCIA] ~5–6 mil tokens na conversa principal | conversa principal; subagentes herdam o conjunto [FATO: F2] | [MEDIDO] lista local |

Leitura da tabela [INFERÊNCIA]: crítico (4,5 mil) menos redator (6,3 mil) dá ~1,8 mil de diferença, que bate com +0,4 mil de corpo e +2 ferramentas (Edit e Bash, esquemas longos). A base comum (prompt de ambiente, 2 ferramentas, CLAUDE.md) fica em ~3,5 mil. Os ~21 mil do `criar-estudo` se decompõem aproximadamente em: base 3,5 mil + corpo 5,8 mil + lista de agentes da ferramenta `Agent` ~5–6 mil + 5 ferramentas a mais ~3–4 mil + git status e o resto. A decomposição é estimada; a única forma de confirmar é rodar `/context` num subagente.

Observação sobre medida: cada pedido aparece duplicado nas transcrições (uma linha por bloco de conteúdo). Eu desduplico por `requestId` para as contas deste arquivo. As somas por agente que aparecem no `00_contexto.md` não são afetadas.

### 1.3 Alavancas oficiais e quanto tiram de CADA chamada

| Alavanca | O que faz [fonte] | Tira por chamada | Aplica ao nosso caso? |
|---|---|---|---|
| `omitClaudeMd: true` | Subagente começa sem CLAUDE.md de usuário, projeto e local [FATO: F2] (exige Claude Code 2.1.271+) | ~0,3 mil [MEDIDO] | Quase nada: o CLAUDE.md global tem 1 KB e o projeto não tem. Só vale se o CLAUDE.md crescer |
| `tools` restrito / `disallowedTools` | `tools` omitido herda tudo; lista limita [FATO: F2] | ~0,5–0,9 mil por ferramenta retirada [INFERÊNCIA, pela diferença crítico x redator]. Retirar `WebFetch` e `WebSearch` do `criar-estudo` (se a pesquisa complementar da Fase 4 for feita por outro agente): ~1–1,5 mil | `gerar-podcast` e `podcast-critico` já estão enxutos |
| Tirar `Agent` de quem não precisa de subagentes | a lista de agentes vem na ferramenta `Agent` [FATO: local; INFERÊNCIA sobre o tamanho] | ~5–6 mil por chamada nos agentes que a têm | Só se o `criar-estudo` deixar de orquestrar (ver B2). Alternativa: restringir `Agent` aos tipos necessários, se a sintaxe `Agent(tipo1, tipo2)` valer (não confirmei na página lida; ver Lacunas) |
| Encurtar descrições (tirar `<example>`) | descrições ocupam contexto; mover detalhe para o prompt do agente [FATO: F2] | ~2,7 mil (os exemplos) na conversa principal e [INFERÊNCIA] em quem tem `Agent` | Alto retorno, baixo risco. Mantém a delegação automática se a 1ª frase for boa |
| Corpo do agente em arquivo sob demanda | só o corpo do agente roda carregado [FATO: F2]; skills carregam sob demanda [FATO: F3] | `criar-estudo`: ~2,5–3 mil (Fases 5b, 6, 7, 8 e modelos só quando chegar a vez) | Média: exige reestruturar o `.md` do agente |
| Desligar servidores/conectores MCP por projeto | `disabledMcpServers` por projeto em `~/.claude.json`, `/mcp` para desligar; `--strict-mcp-config` usa só os servidores de `--mcp-config` [FATO: F4] | ~3–6 mil (só nomes) [INFERÊNCIA]; os subagentes herdam o conjunto | Rende bem. Zero risco: o projeto não usa nenhum MCP. Vale para sessão principal e subagentes lançados dali |
| `mcpServers` no frontmatter | define quais servidores o subagente vê [FATO: F2] | mesmo ganho, por agente | Redundante se o desligamento por projeto for feito |
| `skills` no frontmatter | cada skill listada injeta o conteúdo inteiro [FATO: F2] | Não usar: seria custo adicionado | Nenhum agente nosso lista skills; manter assim |
| CLAUDE.md abaixo de 200 linhas | detalhe específico vai para skills [FATO: F3] | já está em ~0,3 mil | nada a fazer |
| `maxTurns` | teto de passos [FATO: F2] | não reduz o custo de partida; limita o crescimento | Útil como trava (ver recomendação R6) |

Correção em relação à pesquisa anterior (`pesquisa_agentes.md`): lá, as descrições com `<example>` foram classificadas como "impacto baixo por pedido". Medindo, são ~5 mil tokens (55% exemplos) e entram também na ferramenta `Agent`. Continua pequeno frente aos 5,96 M do `criar-estudo`, mas é custo certo em toda chamada. A conclusão geral de lá (D1 não é o maior item) se confirma.

Conta de D1 no podcast: redator ~6,3 mil e crítico ~4,5 mil de partida, 3 a 5 pedidos reais cada [MEDIDO, depois de desduplicar]. Mesmo zerando todo o custo fixo desses dois, o ganho por episódio seria da ordem de 5 pedidos x 6 mil + 3 x 4,5 mil = ~44 mil de ~740 mil (6%) [INFERÊNCIA]. Por isso não recomendo mexer neles.

## 2. Contexto que cresce (B2)

### 2.1 O que foi medido

[MEDIDO] Transcrição do `criar-estudo` da sessão `7db0877c` (subagente `agent-a514e605...`, 77 pedidos reais): soma 5.959.852 tokens processados, dos quais 5.842.439 (98,0%) leitura de cache, 117.209 escrita de cache, 204 sem cache. Contexto: 21,3 mil no 1º pedido, 78 mil no pedido 38, 117 mil no 77º, ou +1,25 mil por pedido.

Conta que reproduz o total: soma = N·C0 + g·N²/2 = 77 x 21,3 mil + 1,25 mil x 77²/2 = 1,64 M + 3,70 M = 5,3 M (o medido é 5,96 M). O termo que cresce com N² é cerca de 70% do total.

O que fez o contexto crescer nesse caso: [MEDIDO] os resultados de ferramenta somam só 77 mil caracteres (~22 mil tokens) e as entradas das ferramentas (inclui o conteúdo gravado com Write) 37 mil caracteres (~11 mil tokens). O crescimento de ~96 mil tokens é maior que isso: [INFERÊNCIA] o resto são blocos de raciocínio (não gravados em texto nas transcrições) e o formato JSON das mensagens. Para um `criar-estudo` normal, [INFERÊNCIA] cada arquivo escrito com Write entra no contexto como entrada de ferramenta (um arquivo de 20 mil caracteres = ~5,7 mil tokens) e fica lá até o fim; 10 arquivos = ~57 mil tokens relidos em todas as chamadas seguintes. Isso não foi medido na pasta CNT-34; é a primeira coisa a confirmar (ver Lacunas).

Também [MEDIDO] no podcast: orquestrador 21 mil → 80 mil em 45 pedidos, 2,57 M no total. Refazendo a conta com N episódios na mesma execução (9 pedidos por episódio, g = 1,3 mil): 5 episódios seguidos = 45 x 21 mil + 1,3 mil x 45²/2 = 0,95 M + 1,32 M = 2,3 M (medido: 2,57 M). Cinco execuções separadas de 1 episódio = 5 x (9 x 21 mil + 1,3 mil x 9²/2) = 5 x 0,29 M = 1,4 M. Queda de 39% no orquestrador.

### 2.2 Padrões oficiais que reduzem isso

- [FATO: F6] Contexto é recurso finito com retorno decrescente: a recordação cai quando o contexto cresce. Recomenda recuperação "just-in-time" (guardar caminhos e carregar o dado só quando for usar), compactação, limpeza de resultados de ferramenta ("uma das formas mais seguras e leves de compactação"), notas estruturadas fora da janela (memória em arquivo) e subagentes que exploram em janela limpa e devolvem um resumo, "muitas vezes 1.000–2.000 tokens".
- [FATO: F5] Sistema multiagente de pesquisa: cada subagente recebe objetivo, formato de saída, orientação de ferramentas e limites de tarefa; subagentes gravam o resultado em sistema externo e devolvem só uma referência leve; o agente líder salva o plano em memória porque o contexto é truncado acima de 200 mil tokens; quando o contexto se esgota, lança subagentes novos com handoff e memória. Também: o uso de tokens explica ~80% da variação de desempenho (BrowseComp), agentes usam ~4x mais tokens que chat e multiagentes ~15x. Multiagente não serve quando todos precisam do mesmo contexto ou há muitas dependências. Isso é um aviso sobre custo total: dividir não reduz tokens por si só.
- [FATO: F7] Limpeza de resultados de ferramenta (`clear_tool_uses_20250919`: `trigger` padrão 100 mil tokens, `keep` 3 usos, `clear_at_least`, `exclude_tools`, `clear_tool_inputs` padrão falso) é um recurso da API Messages em beta, com cabeçalho `context-management-2025-06-27`; a página não cita Claude Code. [INFERÊNCIA] Não dá para ligar isso no Claude Code com assinatura Pro e, como `clear_tool_inputs` é falso por padrão, mesmo ligado não removeria o conteúdo gravado com Write. [FATO: F3] O Claude Code usa internamente "limpeza de resultados de ferramenta" e compactação (contam como "reconstrução esperada" do cache), sem botão de configuração na página lida.
- [FATO: F3] Tarefas verbosas vão para subagentes para que só o resumo volte à conversa principal. Cada requisição do subagente continua contando no plano.

### 2.3 A conta: agente único sequencial x N redatores paralelos

Dados de entrada. Agente único [MEDIDO]: C0 = 21 mil, g = 1,25 mil, 77 pedidos = 5,96 M. Redator por arquivo [SUPOSIÇÃO, ancorada na partida de 6,3 mil do `gerar-podcast`]: partida 8 mil (corpo + ferramentas + regras didáticas 2,8 mil), material do arquivo (trechos das transcrições que ele precisa) ~10 mil, 6 pedidos, contexto de 18 mil a ~30 mil (o próprio arquivo escrito entra: ~5 mil), média 24 mil. Orquestrador do `criar-estudo` sem a escrita dos arquivos (Fases 1–4, 6, 7): ~30 pedidos, contexto de 21 mil a ~60 mil, média ~40 mil.

| Cenário (pasta de 10 arquivos) | Conta | Tokens processados |
|---|---|---|
| A. Agente único (medido, devops) | 77 pedidos, 21 → 117 mil | 5,96 M |
| B. Orquestrador + 10 redatores paralelos, 1 por arquivo | 30 x 40 mil + 10 x 6 x 24 mil = 1,2 M + 1,44 M | ~2,6 M (-56%) |
| C. Igual a B, com material por arquivo ainda menor (D2: -25% no material) | redator 6 x 21,5 mil = 129 mil; 1,2 M + 1,29 M | ~2,5 M (-58%) |
| D. Faixa de sensibilidade de B (partida 6–10 mil, 5–8 pedidos, orquestrador 0,9–1,5 M) | | 2,1–3,3 M (-45% a -65%) |

Observações. Em paralelo, o limite do plano é gasto na mesma proporção dos tokens; o paralelismo reduz o tempo (de ~24–45 min), não o gasto. O ganho vem de quebrar o termo N². Com 10 redatores, o custo fixo extra (10 x 8 mil de partida) é só 80 mil, 3% de B [INFERÊNCIA]. Se o arquivo i precisa de contexto dos anteriores, passar só um índice (lista de termos já definidos e ordem de leitura, ~1–2 mil tokens), nunca os arquivos anteriores.

Risco de qualidade: as regras didáticas 1–3 (definir termo na 1ª ocorrência, sem referência para a frente, ordem por dependência) são globais. Um redator isolado não vê o que os outros definiram. Mitigação: o orquestrador define na Fase 3 a ordem e, por arquivo, "termos que este arquivo deve definir" e "termos já definidos em arquivos anteriores", e um passo final barato (script) checa links `[[...]]` apontando para a frente. [SUPOSIÇÃO] A qualidade se mantém se o plano da Fase 3 for detalhado. Precisa de A/B.

Para o podcast, o orquestrador já delega redator e crítico e já guarda estado em arquivos (`entradas`, `finalizar`, planejamento). [INFERÊNCIA] Resta executar 1 episódio por chamada de `podcast-serie` (39% a menos no orquestrador, ver 2.1), o que equivale a "memória em arquivo + contexto novo" do padrão oficial.

## 3. Material de entrada menor (D2)

### 3.1 O que o código faz hoje

[MEDIDO] `texto_material` (`src/podcast/writer.py`, l. 56–64) divide o orçamento `max_chars_material` (24.000, `comum.py`) entre os arquivos do episódio em proporção ao tamanho, com piso de 500 caracteres, e corta cada arquivo com `t[:cota]`, ou seja, mantém o começo e descarta o fim. Cada arquivo medido tem em média 10–20 mil caracteres, então um episódio com 2 arquivos já estoura o orçamento. [INFERÊNCIA] O fim dos arquivos do `criar-estudo` é onde ficam "por que importa na prática", status atual da técnica e exemplos finais (regras didáticas 6 e 10); o corte atual pode derrubar justamente isso.

### 3.2 O que dá para cortar sem LLM

Medição em 3 pastas reais do vault (arquivos de conteúdo, mesma regra de `material.py`):

| Pasta | Arquivos | Média por arquivo | Blocos de código (inclui mermaid) | Tabelas | Código + tabelas | Arquivos > 24 mil |
|---|---|---|---|---|---|---|
| devops | 33 | 20.158 | 22,2% | 9,4% | 31,6% | 3 |
| nlp | 77 | 9.987 | 16,3% | 5,9% | 22,1% | 4 |
| machine_learning | 31 | 12.978 | 14,7% | 8,4% | 23,1% | 0 |

Mermaid sozinho é 0,4–2,3%. [FATO: local] O prompt do redator diz "o ouvinte só escuta: não vê tela, fórmula, tabela nem código".

| Técnica determinística | Economia por chamada | Risco de qualidade |
|---|---|---|
| T1. Antes do corte, trocar blocos de código e mermaid por uma linha (`[código yaml omitido, 12 linhas]`) | 15–22% do material: 1,0–1,5 mil tokens (24 mil caracteres = ~6,9 mil tokens) | Baixo a médio: em devops, o YAML ou comando pode SER o conceito. Mitigar mantendo a 1ª linha e comentários do bloco, ou só trocar blocos acima de N linhas |
| T2. Trocar tabelas por 1ª linha (cabeçalho) mais nº de linhas | 6–9%: 0,4–0,6 mil | Médio: tabelas comparativas viram fala de contraste. Mitigar mantendo tabelas com até 6 linhas |
| T3. Tirar callouts decorativos, comentários HTML e linhas de navegação do Obsidian | 1–3% [SUPOSIÇÃO, não medido] | Baixo |
| T4. Cortar por seção em vez de `t[:cota]`: manter H2/H3 cujo título contém um conceito do plano do episódio (`conceitos centrais` e `de apoio`), mais a abertura e o TL;DR; sem casamento, cai no arquivo todo | 30–50% quando o episódio cobre 1 de várias seções do arquivo [SUPOSIÇÃO] | Médio: perde conexões entre seções. Corrige o defeito do corte de cauda. Exige um log do que foi omitido |
| T5. Trocar `t[:cota]` por corte na fronteira de seção (nunca no meio da frase) e orçamento por prioridade (centrais antes de apoio) | 0% de tokens, ganho de qualidade | Baixo; é correção de comportamento |
| T6. Reduzir `max_chars_material` de 24 mil para 16–18 mil depois de T1–T2 | 25–33% do material: 1,7–2,3 mil | Médio: fidelidade cai se faltar conceito central; medir pelo critério "fidelidade" do crítico |
| T7. Encurtar `podcast_redator.md` (2,1 mil tokens) em 25% | ~0,5 mil | Médio: o prompt tem histórico de rodadas de crítica (`specs/voz/PROMPTS.md`); não cortar sem repetir os casos de teste |
| T8. `criar-estudo`: carregar as regras didáticas por fase (regras 1–4 e 10–13 só na escrita; formato de referências, Fase 6) | `regras_didaticas.md` = ~2,8 mil tokens; cortar 40% = ~1,1 mil por chamada nas ~60 chamadas após a leitura = ~0,07 M (1% de 5,96 M) | Médio: as regras vêm de reclamações reais do usuário |

Conta de D2 no podcast: o material de 24 mil caracteres (~6,9 mil tokens) é relido a cada pedido do redator (~5 pedidos reais) e do crítico (~3): ~55 mil tokens por episódio, 7% dos ~740 mil [INFERÊNCIA a partir das medidas]. T1+T2 (-22 a -30%) tiram ~12–16 mil por episódio, ou 2% do total. Pequeno, mas quase de graça e sem mexer em agente. Com T6 no total: 3–4%. O valor principal de T4 e T5 é qualidade, não tokens.

Conta de D2 no `criar-estudo`: depende do que cada redator lê; as transcrições não foram medidas (ver Lacunas). O prompt de regras é 1–2% do custo; o ganho real de "menos material" vem de dar a cada redator só as seções de transcrição do seu arquivo (2.3, cenário C).

## 4. Recomendações para o modo econômico

Modo sugerido: `modo_economico: true` em `config.yaml` (podcast) e uma flag equivalente no prompt do `criar-estudo`. Ganhos em tokens processados por chamada ou por execução, conta ao lado. Métrica comum a todas: tokens processados e escritos em cache por execução (script `uso_subagentes.py`, desduplicando por `requestId`), mais nota do crítico/lint no podcast e o quiz/checagem de referências no `criar-estudo`.

| # | Recomendação | O que muda | Como ligar/desligar | Ganho estimado (conta) | Risco de qualidade | Métrica do A/B |
|---|---|---|---|---|---|---|
| R1 | Escrita do `criar-estudo` em subagentes por arquivo (orquestrador mais N redatores com contexto mínimo e índice de termos) | agente novo ou parâmetro no `criar-estudo`; plano da Fase 3 vira contrato por arquivo | flag `redator_por_arquivo`; desligar volta ao fluxo único | 5,96 M → ~2,6 M por pasta de 10 arquivos (-56%; faixa -45% a -65%). Por chamada: o contexto médio cai de ~77 mil para ~24–40 mil | Médio: coerência entre arquivos (regras 1–3). Mitigar com índice de termos e checagem de links para a frente | tokens por pasta; nº de termos sem definição e de referências para a frente; nota de quiz; leitura humana de 2 arquivos |
| R2 | Podcast: 1 episódio por execução do orquestrador (estado já em arquivos) | `podcast-serie` ou o chamador roda `--lote 1`; limite "5 por execução" vira "1 por execução, N execuções" | opção `episodios_por_execucao: 1` (padrão atual: até 5) | Orquestrador 2,3 M → 1,4 M por 5 episódios (-39%). Total por episódio de ~0,74 M para ~0,51 M (-31%): orquestrador é 69% do total | Baixo: a série já guarda estado em `podcast/.agente/`; precisa conferir se o orquestrador usa algo que só está na memória da conversa | tokens por série de 5; pontes entre episódios (presença no lint/crítico) |
| R3 | Enxugar descrições dos agentes: tirar `<example>` (e deixar a 1ª frase) | só frontmatter dos agentes. Não editei: só recomendo | A/B por cópia do diretório de agentes; desligar restaurando | ~2,7 mil tokens por chamada na sessão principal e [INFERÊNCIA] em quem tem `Agent`: no `criar-estudo`, 77 x 2,7 mil = 0,2 M (-3,5%) | Baixo a médio: pode reduzir o acerto da delegação automática. Mitigar com gatilhos claros na 1ª frase | tokens da 1ª chamada; delegação correta em 5 pedidos de teste |
| R4 | Desligar conectores MCP no projeto `agente_estudos` (ou sessão com `--strict-mcp-config`) | `disabledMcpServers` do projeto / flag da CLI; nada no repositório | ligar/desligar pelo `/mcp` | ~3–6 mil tokens por chamada [INFERÊNCIA]; no `criar-estudo`: 77 x 4,5 mil = 0,35 M (-6%) se os subagentes herdarem o conjunto | Nulo: o projeto não usa MCP | `/context` antes e depois; 1ª chamada de subagente |
| R5 | `criar-estudo`: tirar `Agent` quando R1 não for usada ou restringir os tipos spawnáveis; tirar `WebFetch`/`WebSearch` se a pesquisa complementar for de outro agente; corpo em arquivo sob demanda | frontmatter e estrutura do `criar-estudo.md` | duas versões do agente | `Agent` fora: ~5–6 mil por chamada; ferramentas: ~1–1,5 mil; corpo sob demanda: ~2,5–3 mil. Somados ~9–10 mil x 77 = 0,7 M (-12%), se nada mais mudar | Médio: o agente perde capacidades; só se o fluxo for dividido (R1) | tokens da 1ª chamada (de ~21 mil para ~11–12 mil) |
| R6 | `maxTurns` nos redatores e críticos | frontmatter | remover a linha | não reduz custo médio; limita o pior caso (redator de 23–27 pedidos, 540–800 mil tokens em "Bastidor", [MEDIDO]) | Baixo | nº de execuções cortadas por limite |
| R7 | D2 no podcast: T1 mais T2 mais T5 (limpeza determinística, corte por seção, orçamento por prioridade) | `src/podcast/writer.py` `texto_material`; é código, não agente | `material_enxuto: true` | ~12–16 mil tokens por episódio (-2%); com T6 -3 a -4% | Baixo a médio (T1/T2); T5 melhora a qualidade | fidelidade e cobertura de conceitos centrais no crítico; palavras do roteiro |
| R8 | D2 com T4 (seleção por seção por conceito do plano) | `src/podcast/material.py` | `material_por_conceito: true` | 30–50% do material onde casar [SUPOSIÇÃO]: 2–3,5 mil por pedido, ~25 mil por episódio (-3%) | Médio | idem, e % de episódios em que o casamento falhou e caiu no arquivo inteiro |

Ordem por retorno e facilidade: R2 (alto, baixo risco), R1 (maior, médio risco, mais trabalho), R4 e R3 (pequenos e quase sem risco), R5, R7, R8, R6.

Ganhos não somam por linha: R1 e R5 atacam os mesmos pedidos; R5 só vale integralmente se R1 não for adotada. Somando R2 + R7 + R4 + R3 no podcast e R1 + R4 + R3 no `criar-estudo` [INFERÊNCIA]: podcast de ~0,74 M para ~0,45–0,50 M por episódio (-33% a -39%); `criar-estudo` de ~6 M para ~2,3–2,6 M (-57% a -62%).

## 5. Lacunas

- Não medi o que compõe os ~21 mil do `criar-estudo` (corpo x lista de agentes x ferramentas x MCP). A decomposição da seção 1.2 é estimada; `/context` rodado dentro de um subagente resolveria.
- Não confirmei que a lista de agentes entra na ferramenta `Agent` dos subagentes (só vi isso na conversa principal desta sessão), nem a sintaxe `Agent(tipo1, tipo2)` para restringir; a página de subagentes tem 16,7 mil caracteres que não li, e a seção de ferramentas MCP (ferramenta de busca) foi truncada.
- Não medi quanto cada nome de ferramenta MCP adiada custa; os 3–6 mil por chamada são estimativa.
- A pasta CNT-34 (83 chamadas) não foi analisada; a medição de B2 vem do `criar-estudo` do podcast de devops (77 pedidos), que orquestrou o podcast e não é a escrita de 10 arquivos. Falta medir quanto do contexto de uma execução normal são entradas de `Write` e transcrições.
- O tamanho das transcrições lidas pelo `criar-estudo` por arquivo não foi medido, então o redator por arquivo (cenário B) usa material de 10 mil tokens como suposição.
- Não sei como o plano Pro pondera leitura de cache contra escrita e saída. Usei tokens processados; se a leitura de cache pesar muito menos que o resto, o ganho percentual em plano pode ser menor que o de tokens brutos, embora a direção seja a mesma. O orquestrador seria o item mais afetado.
- O `output_tokens` gravado nas transcrições é parcial (limitação já registrada no `00_contexto.md`), então a saída ficou fora das contas.
- Qualidade de R1, R7 e R8 não foi testada; todas as estimativas de risco são julgamento.

## 6. Fontes

Data de acesso de todas: 2026-11-07.

- F1: arquivos locais lidos e medidos: `~/.claude/agents/*.md`, `~/.claude/skills/*/SKILL.md`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `agente_estudos/prompts/*.md`, `src/podcast/material.py`, `writer.py`, `comum.py`, pastas do vault (`devops`, `nlp`, `machine_learning`), transcrições `~/.claude/projects/-home-robertocaetano207-dev-agente-estudos/7db0877c-3b31-436a-a42c-cd4174ee4226/subagents/*.jsonl`.
- F2: Custom subagents. https://code.claude.com/docs/en/sub-agents (data de publicação não visível; leitura parcial, 100 mil de 116,7 mil caracteres)
- F3: Manage costs effectively. https://code.claude.com/docs/en/costs (data não visível)
- F4: Connect Claude Code to tools via MCP. https://code.claude.com/docs/en/mcp (data não visível; leitura parcial, 100 mil de 157 mil caracteres)
- F5: How we built our multi-agent research system. https://www.anthropic.com/engineering/multi-agent-research-system (13/06/2025)
- F6: Effective context engineering for AI agents. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (29/09/2025)
- F7: Context editing (API). https://platform.claude.com/docs/en/build-with-claude/context-editing (data não visível; leitura parcial)
- Complemento: `/home/robertocaetano207/dev/aferes/pesquisa_agentes.md` (2026-10-25), citado na correção da seção 1.3.

# G2 · Limite do plano, cache de prompt e medição (temas A2, A3, C2)

Data: 2026-11-07. Acesso a todas as fontes: 2026-11-07. Base: `00_contexto.md`, `pesquisa_agentes.md` (complementada, não repetida) e `BUILD_REPORT.md` ("Redução de custo").

Resposta curta: a Anthropic não publica quanto cada tipo de token pesa no limite do Pro. O que está documentado é que leitura de cache gasta limite (mais barata que entrada nova), que Opus gasta "significativamente mais" que Sonnet, e que subagentes têm cache de 5 min (a conversa principal tem 1 h). Por isso a métrica a otimizar é um "peso" calculado por tipo de token e por modelo, validado contra a barra do `/usage`, e não a contagem bruta de tokens. Nessa leitura, o crítico Opus (não o orquestrador) tende a ser o maior gasto.

## 1. Como o limite do Pro contabiliza tokens

Pergunta: leitura de cache, gravação de cache, entrada nova e saída pesam igual? O modelo muda o peso?

- [FATO: F1] Pro e Max têm limite de sessão de 5 h e limite semanal, compartilhados entre claude.ai e Claude Code. Os "Fable" ficam fora do limite no Pro (F7, da pesquisa anterior).
- [FATO: F2] Trocar de modelo com `/model` não devolve cota quando o limite de sessão ou semanal estoura: o limite vale para todos os modelos. Só as mensagens "Opus limit" e "Sonnet limit" (específicas de família) permitem trocar de família.
- [FATO: F2] A página de custos diz que o Claude Code "re-lê o histórico à taxa de cache" e que "uma pergunta de uma linha numa sessão aberta o dia todo ainda consome uso pela conversa inteira". Ou seja, leitura de cache gasta limite. A documentação não diz com que fração.
- [FATO: F3] Na ajuda do claude.ai, conteúdo em cache "conta menos contra o limite quando reutilizado"; caches expiram por inatividade e, depois de pausa, a primeira mensagem conta o conteúdo por inteiro de novo. Os fatores listados são tamanho da mensagem, tamanho da conversa, anexos, modelo, esforço e uso de ferramentas. O texto é sobre projetos do claude.ai; não é uma tabela de pesos do Claude Code.
- [FATO: F4, via pesquisa anterior S2] Opus "usa significativamente mais da cota"; Opus custa várias vezes mais por turno que Sonnet, e Sonnet mais que Haiku. Não há multiplicador oficial.
- [FATO: F2] O pensamento (thinking) é cobrado como saída. Não dá para desligá-lo no Opus 5.5, Sonnet 5.5 e Haiku 5.5, então o `effort` é a alavanca.
- [FATO: F2] O `/usage` calcula o valor em dólar localmente, a preço de lista. Para assinante, o bloco "Session" não serve de cobrança.
- [INFERÊNCIA] Os pesos do limite acompanham, de forma aproximada, a relação de preços da API: saída ~5× a entrada; leitura de cache ~0,1× a entrada; gravação de cache de 5 min ~1,25× e de 1 h ~2× a entrada; Opus ~2× Sonnet. Motivo: as fontes oficiais dizem "mais barato", "significativamente mais" e "conta menos", sempre na mesma direção do preço. Os multiplicadores 0,1/1,25/2 vêm do conhecimento geral da tabela da API e não foram reconfirmados nesta rodada. Preço de lista usado só como peso relativo, como manda o 00_contexto.
- [SUPOSIÇÃO] Um blog de terceiros (resultado de busca, não aberto) afirma que no plano Team tokens em cache "não contam". Sem número medido e contradiz F2. Não usar.
- [FATO: F5] Comunidade: nenhuma medição publicada que isole o peso de cada tipo de token no limite do Pro. Só há estimativas de "prompts por janela" (por exemplo ~90 prompts por janela de 5 h após a duplicação de maio de 2026, estimativa de blog) sem metodologia.

Efeito prático: não existe fórmula oficial. A saída é calibrar (seção 3, procedimento B) comparando 3 hipóteses de peso com a variação real da barra do `/usage`.

## 2. Cache de prompt no Claude Code

TTL em sessão com assinatura

- [FATO: F6] Dentro do uso incluído no plano, a conversa principal pede TTL de 1 h. Todo o resto (subagentes, workflows, teammates, forks, compactação, títulos de sessão) recebe 5 min, exceto pequenos pedidos auxiliares controlados pelo servidor. Passou do limite do plano e entrou em créditos extras: a conversa principal cai para 5 min.
- [FATO: F6] "Subagentes ... recebem 5 minutos mesmo em assinatura, até você escolher um TTL maior". Ajustes: `subagentPromptCacheTtl` / `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` (global, v2.1.242+) ou `experimental: { cacheTtl: 1h }` no frontmatter do agente (v2.1.248+). `FORCE_PROMPT_CACHING_5M=1` força 5 min em tudo (útil para comparar).
- [INFERÊNCIA] O `podcast-serie` (orquestrador), o `gerar-podcast` e o `podcast-critico` são todos subagentes quando chamados pelo agente `criar-estudo` ou pelo Agent tool, então rodam com TTL de 5 min. Se o `podcast-serie` rodar como conversa principal (sessão com `--agent`), ele pega 1 h. A distinção não foi testada.

O que invalida o cache

- [FATO: F6] O casamento é por prefixo exato; mudar qualquer coisa no prefixo recalcula tudo depois. Ordem do pedido: prompt de sistema e ferramentas, depois contexto do projeto (CLAUDE.md, memória), depois conversa. Invalidam: trocar de modelo (cada modelo tem cache próprio), fast mode, adicionar ou remover definições de ferramenta (MCP sem tool search, deny de ferramenta inteira sem tool search), `/compact`, acúmulo de imagens, atualizar o Claude Code. Não invalidam: editar arquivos, editar CLAUDE.md no meio da sessão (também não vale até `/clear`), trocar permissão, invocar skill (exceto se a skill troca `model`), `/rewind`, criar subagente.
- [FATO: F6] No Opus 5.5, Sonnet 5.5 e Haiku 5.5 com assinatura, mudar `effort` no meio da sessão mantém o cache.
- [FATO: F6] O escopo do cache é por máquina e diretório: o prompt de sistema embute os caminhos da memória e a conversa abre com diretório, plataforma, shell, SO; sessões em diretórios diferentes não se leem. Sessões em paralelo no mesmo diretório criam prefixos iguais e podem ler o cache uma da outra. Sessões sequenciais só dividem prefixo se o snapshot de git do início for igual.

Subagentes do mesmo tipo reaproveitam cache uns dos outros?

- [FATO: F6] Cada invocação de subagente é uma conversa nova com prompt de sistema e ferramentas próprios. O primeiro pedido dela não lê o cache do pai. Ela aquece um cache próprio ao longo dos seus turnos. Fork é a exceção: herda prompt, ferramentas e histórico do pai e lê o cache dele.
- [FATO: F6] Dois pedidos compartilham cache quando modelo, velocidade e prefixo coincidem. Num fan-out de workflow com agentes de mesmo prefixo, o Claude Code segura todos menos o primeiro por até 5 s para que leiam o cache que o primeiro gravou. Isso mostra que o compartilhamento entre agentes de mesmo prefixo existe quando o prefixo é idêntico.
- [FATO: F6, F8] Subagente retomado (`SendMessage` com o ID ou nome do agente) mantém o histórico completo e "pode continuar lendo o cache que a execução original aqueceu". Explore e Plan são one-shot e não retomam. Transcrições ficam em `~/.claude/projects/{projeto}/{sessão}/subagents/agent-{id}.jsonl`.
- [INFERÊNCIA] O redator do episódio 2 (mesmo agente, mesmo modelo, chamado em até 5 min do redator do 1) pode ler do cache a parte comum do início (sistema, ferramentas, CLAUDE.md), mas não o resto, porque o prompt de delegação difere e o snapshot de git muda a cada episódio finalizado. Não há documentação explícita para chamadas sequenciais de subagentes; precisa de teste (seção 3, passo de verificação).

Por que a gravação de cache dos subagentes foi 58% do custo na série devops

- [INFERÊNCIA] Quatro causas somadas, sem medição que as separe: (a) cada subagente novo (9 redatores, 9+ críticos, reescritas) grava do zero o prefixo de ~21 mil tokens; (b) toda a conversa de cada subagente é gravada uma vez, porque cada turno acrescenta resultado de ferramenta e saída que viram prefixo novo (a gravação total de um agente é aproximadamente o contexto final dele); (c) a gravação custa mais que a leitura (~1,25× a entrada de 5 min contra ~0,1×); (d) série toda em Opus, o modelo mais caro, e roteiros refeitos por estouro de palavras (4 de 9), o que gerou mais agentes e mais gravação.
- [INFERÊNCIA] Ordem de grandeza: ~1,0 M gravados em ~27 invocações dá ~37 mil por invocação, coerente com 21 mil de partida mais ~15 mil de conversa.

O que reduz a gravação

| Alavanca | Por que ajuda | Status |
|---|---|---|
| Prefixo estável e idêntico entre chamadas do mesmo agente (parte fixa primeiro, parte variável por último; sem data, nome de episódio ou contador no começo do prompt) | Mais pedidos casam o prefixo e leem em vez de gravar | [FATO: F6] regra do prefixo; efeito em subagentes sequenciais [INFERÊNCIA] |
| Não mexer em modelo, ferramentas, MCP e CLAUDE.md durante a execução | Evita invalidação | [FATO: F6] |
| Menos subagentes novos por episódio (a reescrita virar `SendMessage` ao mesmo redator em vez de novo agente) | Evita gravar de novo o prefixo de ~21 mil e reaproveita o cache aquecido | [FATO: F8] retomada lê o cache; economia [INFERÊNCIA] |
| Retomar o mesmo subagente entre episódios | Poupa o prefixo, mas carrega o histórico anterior (contexto cresce e entra contaminação de um episódio no outro) | [INFERÊNCIA]; não recomendado entre episódios, só na reescrita do mesmo episódio |
| Evitar pausas maiores que 5 min dentro de um subagente ou do orquestrador-subagente (por exemplo esperar o edge-tts de ~5 min por episódio) | Cache de 5 min expira e o pedido seguinte regrava o contexto inteiro | [FATO: F6] TTL; se o orquestrador espera o áudio é [SUPOSIÇÃO] |
| `cacheTtl: 1h` nos subagentes | Só vale se houver pausas entre 5 min e 1 h; a gravação de 1 h custa ~2× (contra ~1,25×) | [FATO: F6] existe; só compensa com pausas [INFERÊNCIA]; em série contínua, manter 5 min |
| `omitClaudeMd: true` nos agentes do podcast que não precisam do CLAUDE.md global | Menos tokens no prefixo de cada subagente | [FATO: F8] campo existe (v2.1.271+); ganho pequeno, o CLAUDE.md global é curto [INFERÊNCIA] |
| Meta de palavras e lint (já feitos) | Menos reescritas, menos agentes | [FATO: BUILD_REPORT] |

Dividir o orquestrador em um por episódio compensa? [INFERÊNCIA] Não. Com pesos de preço (leitura 0,1; gravação 1,25), um orquestrador único de 5 episódios custa ~257 mil (leituras: 2,57 M × 0,1) + ~100 mil (80 mil gravados × 1,25) ≈ 357 mil unidades de entrada. Um orquestrador novo por episódio custa ~87 mil cada (≈ 34 mil × 1,25 de partida + 8 mil × 1,25 de crescimento + 9 chamadas × ~38 mil × 0,1) e ≈ 435 mil nos 5. O orquestrador único ganha ~18%; com 9 episódios, ~10% (703 mil contra 783 mil). A conta usa a curva medida (21, 34 → 80 mil) e o preço como peso; não é medição direta.

## 3. Medição

O que cada ferramenta mostra

| Ferramenta | Por execução | Por subagente | Observação |
|---|---|---|---|
| `/usage` bloco Session | Entrada, saída, leitura e gravação de cache por modelo (`Usage by model`), tempo de API e de relógio, custo estimado | Não separa | [FATO: F2] valor em US$ é estimativa de lista, "não relevante" para assinante; zera no `/clear` (v2.1.211+) |
| `/usage` linha `Prompt cache (main)` | Requisições, % de entrada vinda de cache, falhas, causa provável, quente ou frio e TTL | Só conversa principal, não subagentes | [FATO: F2] v2.1.251+ |
| `/usage` atribuição e recomendações | % do uso recente por skill, subagente, plugin e MCP (24 h ou 7 dias) | Por tipo, em % | [FATO: F2] aproximado, calculado do histórico local, não inclui outro dispositivo nem claude.ai. Barras de plano mostram % do limite |
| `/cost` | Mesmo conteúdo do bloco Session (o comando foi absorvido pelo `/usage`) | Não | [SUPOSIÇÃO] não aparece na documentação lida; conferir `/help` |
| `/context` | Tamanho atual do contexto e o que o ocupa | Só a sessão atual | [FATO: F2] |
| OpenTelemetry (métrica `claude_code.token.usage`) | `type` = input, output, cacheRead, cacheCreation; `model`; `query_source` = main, subagent, auxiliary; `effort` | Por tipo de agente via `agent.name`, mas nomes definidos pelo usuário viram "custom" | [FATO: F9] `cacheCreation` soma 5 min e 1 h na métrica |
| OpenTelemetry (evento `api_request`) | Por requisição: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `cache_creation_5m_tokens`, `cache_creation_1h_tokens`, `duration_ms`, `cost_usd`, `model`, `query_source`, `request_id` | `agent_id` e `parent_agent_id` por subagente (v2.1.310+); `session.id` e `prompt.id` para agrupar | [FATO: F9] é a única fonte oficial por requisição e por subagente |
| `claude -p --output-format json` | `total_cost_usd`, `usage`, detalhe por modelo, `session_id` | Não confirmado se inclui subagentes | [FATO: F10] estimativa do cliente, "pode diferir da cobrança" |
| ccusage (terceiros) | Totais por dia, sessão e modelo a partir dos `.jsonl` | Pode pular arquivos de subagentes | [FATO: F5] relatos da comunidade de subcontagem de saída de 77–94%, parte por pular subagentes; não verificado em primeira mão |

Por que o `output_tokens` das transcrições `.jsonl` aparece parcial

- [FATO: F11] Relato no GitHub (Claude Code 2.1.29): o `.jsonl` grava cada bloco de conteúdo durante o streaming e não grava o fim da mensagem; as linhas têm `stop_reason: null` e `output_tokens` de 1 ou valores muito pequenos, um instantâneo do meio do streaming. Medido: 26 linhas com `output_tokens: 1` numa sessão; ccusage somou ~5 mil de saída em 85 milhões de tokens.
- [FATO: F5] O mesmo `requestId` aparece de 2 a 10 vezes com os mesmos valores; somar sem deduplicar multiplica o erro (relatos de comunidade).
- [FATO: F11] O relato foi fechado pelo autor e por um bot, sem resposta nem correção confirmada da Anthropic. Os valores de 40–200 do `00_contexto.md` batem com esse padrão, mas a causa nas versões atuais não foi confirmada [INFERÊNCIA].
- [INFERÊNCIA] Consequência: entrada, leitura e gravação de cache nos `.jsonl` são confiáveis (vêm do início da resposta); saída não. Como a saída pesa ~5× a entrada, ignorá-la subestima o peso do redator e do crítico (que escrevem), logo subestima o Opus.

Procedimento de medição do A/B (modo atual contra modo econômico)

A. Instrumentar uma vez (sem alterar settings globais; só variáveis de ambiente do comando)

1. `claude --version` (os campos por subagente pedem v2.1.310+; os de 5 min e 1 h pedem v2.1.300+).
2. Subir um coletor local: servidor HTTP de ~40 linhas em Python que recebe OTLP em JSON em `http://127.0.0.1:4318/v1/logs` e grava uma linha por evento em `medidas/<run_id>.jsonl`. Não envia nada para fora. [SUPOSIÇÃO] funciona com `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`; testar com um `claude -p "oi"` antes.
3. Rodar cada execução em modo não interativo, com as variáveis só no comando: `CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_LOGS_EXPORTER=otlp OTEL_EXPORTER_OTLP_PROTOCOL=http/json OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 OTEL_LOGS_EXPORT_INTERVAL=1000 claude -p "<pedido do podcast>" --output-format json > resultado.json`, e medir o tempo de relógio com `date +%s` antes e depois. Plano B se o coletor não funcionar: `OTEL_LOGS_EXPORTER=console` redirecionando o stderr para arquivo (formato a conferir).

B. Calcular o peso e calibrá-lo (resolve o "qual métrica otimizar")

4. Por execução, somar os eventos `api_request` por `model` e `agent_id` (e `query_source`): entrada, saída, leitura, gravação 5 min, gravação 1 h, mais `duration_ms`.
5. Calcular três pesos por execução (unidade: tokens de entrada Sonnet; fator de modelo Opus 1,0, Sonnet 0,5, Haiku a definir):
   - W1, "preço": entrada×1 + saída×5 + leitura×0,1 + gravação5m×1,25 + gravação1h×2, vezes o fator de modelo.
   - W2, "tudo igual": soma dos quatro tipos, vezes o fator de modelo.
   - W3, "sem leitura": W1 com leitura = 0.
6. Antes e depois de cada execução, anotar as barras de `/usage` (sessão de 5 h e semanal). Não usar o claude.ai nem outra sessão durante o teste (o limite é compartilhado e o `/usage` não vê o outro dispositivo). Como a barra tem granularidade de ponto percentual, usar execuções de série de 5 episódios (peso grande) e pelo menos 3 por modo.
7. A hipótese de peso que melhor acompanha a variação da barra entre as execuções (maior correlação, mesma ordem de grandeza) vira a métrica oficial do projeto. Com poucos pontos, tratar como indício, não como prova.

C. Desenho do A/B

8. Mesma pasta, mesmo tema e mesmo número de episódios nos dois modos; o modo econômico liga por flag no prompt de orquestração (uma linha `MODO=economico`), nunca por edição de arquivo no meio da execução.
9. Ordem ABBA ou ABABAB, 3 execuções por modo, com pelo menos 10 min entre elas (o cache de 5 min esfria igual para todas) e fora de horários de uso do claude.ai.
10. Registrar por execução: W1, W2, W3; tokens por tipo e por agente; nº de subagentes; falhas de cache (`cache_creation_tokens` da 1ª requisição de cada subagente contra a 2ª); tempo de relógio e soma de `duration_ms`; nota do crítico e nº de reescritas (qualidade).
11. Verificação do cache entre subagentes do mesmo tipo: na 1ª requisição do 2º redator, se `cache_read_tokens` for maior que 0, o prefixo é compartilhado; se for 0, cada subagente grava do zero. Isso responde a lacuna da seção 2.
12. Contar como "ganho" só se a mediana de W1 cair e a nota do crítico não cair; apresentar W2 e W3 como faixa de incerteza.

Fallback sem OTel: somar entrada, leitura e gravação dos `.jsonl` (principal e `subagents/agent-*.jsonl`), deduplicando por `requestId`, e estimar a saída por caracteres do texto escrito (~1,8 token por palavra em português, conforme F5 da pesquisa anterior, mais thinking desconhecido). Menos confiável.

## 4. Releitura das medições do 00_contexto.md em peso no limite

Dados: orquestrador 69% dos tokens (2,57 M em 45 chamadas, quase tudo leitura de cache), redator 20%, crítico 11%. Orquestrador e redator em Sonnet; crítico em Opus. Em dólar de lista (BUILD_REPORT): crítico 42%, orquestrador 31%, redator 27%.

| Hipótese de peso | Orquestrador | Redator | Crítico | Maior gasto |
|---|---|---|---|---|
| Contagem bruta de tokens (não é peso) | 69% | 20% | 11% | Orquestrador |
| W2, tudo igual, com fator de modelo (Opus 1, Sonnet 0,5): 0,69×0,5 : 0,20×0,5 : 0,11×1 | ~62% | ~18% | ~20% | Orquestrador |
| W1, preço relativo (o BUILD_REPORT já usa) | 31% | 27% | 42% | Crítico Opus |
| W3, leitura de cache pesando ~0 | Menor que em W1 [INFERÊNCIA]: sobra só gravação e saída do orquestrador | — | — | Crítico Opus, provavelmente |

- [INFERÊNCIA] O orquestrador só é o maior gasto na contagem de tokens, que pesa leitura de cache como se fosse entrada nova. Em peso por preço (hipótese mais coerente com F2, F3 e F4), o maior gasto é o crítico em Opus (42%), seguido do orquestrador (31%). A conclusão "orquestrador é o maior gasto" só se sustenta se a leitura de cache pesar quase como entrada nova (W2), o que contradiz F3 ("conta menos").
- [INFERÊNCIA] A série devops, 58% de gravação de cache nos subagentes, reforça que no peso o que pesa é gravação e saída dos agentes que escrevem e avaliam, não a leitura repetida do orquestrador.
- [INFERÊNCIA] Os números de output das transcrições estão subestimados (seção 3), então o peso do redator e do crítico (que mais escrevem) é maior que o das tabelas acima; isso desloca ainda mais o peso para os subagentes, em particular o Opus.
- [SUPOSIÇÃO] As porcentagens de W1 vêm do BUILD_REPORT (dólar de lista de uma configuração, a série de 5 episódios do 00_contexto pode ter outra divisão). Recalcular com a seção 3 antes de decidir.

Efeito prático: reduzir o orquestrador (menos chamadas, contexto menor) ainda vale, mas a alavanca de maior peso provável é o crítico Opus e a gravação de cache dos subagentes. Antes de mexer no crítico, medir W1, W2 e W3 com o procedimento acima; o teste do BUILD_REPORT (Sonnet deixou passar 3 de 4 erros) mostra que trocar o modelo do crítico tem risco de qualidade, então as alavancas que não mexem em qualidade (prefixo estável, reescrita por `SendMessage`, evitar pausas > 5 min) vêm primeiro.

## 5. Recomendações para o modo econômico

| Recomendação | O que muda | Como ligar/desligar | Ganho estimado (conta) | Risco de qualidade | Métrica do A/B |
|---|---|---|---|---|---|
| R0. Medir antes (instrumentação OTel local + peso W1/W2/W3 + calibração com a barra do `/usage`) | Só ambiente do comando e um script coletor; nenhum arquivo do sistema | Variáveis de ambiente no comando de teste; sem elas, nada muda | Não economiza; define a métrica. Evita otimizar o número errado (orquestrador 69% em tokens contra 31% em preço) | Nenhum | Correlação de W1, W2, W3 com a variação da barra, em 3+ execuções |
| R1. Prefixo estável nos prompts de delegação (parte fixa primeiro, variável por último; sem data ou contador no começo; não editar prompts nem trocar modelo no meio da série) | Prompt de orquestração e templates de delegação | Linha `MODO=economico` escolhe o template estável; sem ela, o atual | [INFERÊNCIA] se o prefixo comum ao 2º subagente passar a ler do cache: ~21 mil × (1,25 − 0,1) ≈ 24 mil unidades por subagente evitadas; em ~27 invocações ≈ 650 mil, perto de 15–25% do peso de gravação. Só se o passo 11 mostrar leitura > 0 | Nenhum | `cache_read_tokens` e `cache_creation_tokens` da 1ª requisição de cada subagente; W1 |
| R2. Reescrita por `SendMessage` ao mesmo redator (dentro de 5 min), em vez de novo agente | Orquestração (usar o ID do redator) | Flag no modo econômico | [INFERÊNCIA] poupa regravar ~21 mil de prefixo + o material já lido: ~24 mil+ unidades por reescrita; 4 de 9 episódios reescritos na série medida ⇒ ~100 mil na série (~2% do peso total). Pequeno | Baixo; o redator mantém o histórico do episódio e pode "defender" o texto antigo [SUPOSIÇÃO] | Reescritas por episódio, W1, nota do crítico |
| R3. Manter orquestrador único por execução (não dividir por episódio) e seguir o limite de 5 episódios | Nenhuma | Já é o atual; conferir se não vira um por episódio | ~18% menos que um por episódio com 5 episódios (357 mil contra 435 mil unidades, conta na seção 2) | Nenhum | Peso do orquestrador por episódio |
| R4. Não deixar nenhum agente parado por mais de 5 min (áudio edge-tts fora da espera do orquestrador, ou em processo separado) | Orquestração e CLI | Flag que roda a síntese depois da última geração | [SUPOSIÇÃO] depende de o orquestrador esperar o áudio; se esperar, cada expiração regrava ~40–80 mil (≈ 50–100 mil unidades por expiração) | Nenhum | `cache_creation_tokens` na 1ª requisição após cada pausa; tempo de relógio |
| R5. `omitClaudeMd: true` em redator e crítico se o CLAUDE.md não lhes serve | Frontmatter dos agentes | Cópia do agente com e sem o campo | [INFERÊNCIA] pequeno (CLAUDE.md global curto): < 2 mil tokens por subagente | Baixo; checar se algum prompt depende de regra do CLAUDE.md | Tokens da 1ª requisição do subagente |
| R6. Medir o `effort` por agente (o campo muda o consumo sem invalidar cache no Opus/Sonnet/Haiku 5.5) | Frontmatter `effort` | Variante do agente | Não estimável sem medição; saída pesa ~5× a entrada [INFERÊNCIA] | Médio; testar nota do crítico | `output_tokens` por agente (via OTel, não `.jsonl`) e nota do crítico |
| R7. Avaliar rebaixar de modelo o orquestrador (de Sonnet para Haiku) | Frontmatter `model` | Variante do agente | Em W2 o orquestrador é ~62% do peso; em W1 ~31%; ganho depende de qual W vale. Só decidir depois de R0 | Médio (o orquestrador é mecânico, mas segue regras longas) | W1 por modelo; falhas de protocolo do orquestrador |
| R8. Crítico em Opus: manter até medir | Nenhuma | — | Em W1 é o maior gasto (42%); o teste com Sonnet economizaria ~11% da série e deixaria passar 3 de 4 erros | Alto (comprovado no BUILD_REPORT) | Erros que escapam por episódio |

Como medir o A/B do modo econômico (resumo): executar o passo A (coletor), rodar 3 execuções por modo em ordem ABBA com o mesmo tema e 10 min de intervalo, extrair do `api_request` os tokens por tipo, por modelo e por `agent_id`, calcular W1, W2, W3 e o tempo, anotar a barra do `/usage` antes e depois, e comparar a mediana de W1 (e a faixa W2–W3) junto com a nota do crítico. Detalhe na seção 3, passos 1 a 12.

## 6. Lacunas

- Nenhum peso oficial por tipo de token ou por modelo no limite do Pro; só a direção (leitura "conta menos", Opus "significativamente mais"). A calibração do passo B é a forma de fechar.
- O multiplicador de preço (0,1, 1,25, 2; Opus 2× Sonnet) vem do conhecimento da tabela da API e não foi reconfirmado nesta rodada; o preço do Haiku 5.5 ("a partir de") é impreciso.
- Se subagentes sequenciais do mesmo tipo leem o cache um do outro: não documentado; o passo 11 testa.
- Se `claude -p --output-format json` soma os subagentes: não confirmado.
- Nomes de agentes definidos pelo usuário aparecem como "custom" nas métricas; confirmar se o evento `api_request` traz o nome real ou só `agent_id` (o `agent_id` basta, pois dá para ligar ao tipo pelo `parent_agent_id` e pelo transcript).
- A causa do `output_tokens` parcial nas versões atuais (o relato é da 2.1.29, sem correção confirmada).
- `/cost`: a página de custos lida cita só `/usage`; conferir se o comando ainda existe.
- A divisão 69/20/11 e a de dólar (31/27/42) vêm de execuções diferentes (série de 5 e BUILD_REPORT); o W1 do orquestrador não foi recalculado a partir dos tokens brutos por tipo.
- Comunidade: sem medição própria de peso no limite; o único número (≈90 prompts por janela) é estimativa de blog.
- O arquivo `/usage` por subagente é só em %, aproximado e local.

## 7. Fontes

| # | Título | URL |
|---|---|---|
| F1 | Use Claude Code with your Pro or Max plan | https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan |
| F2 | Manage costs effectively (Claude Code) | https://code.claude.com/docs/en/costs |
| F3 | Usage limit best practices | https://support.claude.com/en/articles/9797557-usage-limit-best-practices |
| F4 | Models, usage, and limits in Claude Code (a página lida não trata de Pro; as frases sobre Opus vêm dela e da pesquisa anterior, S2) | https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code |
| F5 | Resultados de busca de comunidade (não abertos individualmente, sem metodologia): morphllm.com/claude-code-usage-limits; dev.to/gabrielanhaia (somar uso da transcrição: um pedido aparece várias vezes); gille-ai.pages.dev (subcontagem do JSONL); aident.ai/blog/claude-code-jsonl-token-usage; claude-wiki.com/jsonl-token-undercount-100-174x.html | busca web em 2026-11-07 |
| F6 | How Claude Code uses prompt caching | https://code.claude.com/docs/en/prompt-caching.md |
| F7 | Claude Fable models on your plan | https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan |
| F8 | Custom subagents | https://code.claude.com/docs/en/sub-agents.md |
| F9 | Monitor usage (OpenTelemetry) | https://code.claude.com/docs/en/monitoring-usage |
| F10 | Run Claude Code programmatically | https://code.claude.com/docs/en/headless.md |
| F11 | [BUG] Output tokens incorrectly recorded in JSONL, anthropics/claude-code#22686 | https://github.com/anthropics/claude-code/issues/22686 |

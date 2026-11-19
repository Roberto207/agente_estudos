# Plano · Modo econômico do agente_estudos (2026-11-07)

Síntese das pesquisas G1 a G4 desta pasta. Restrição de base: só a assinatura Claude Pro, sem nenhuma API key (ver `00_contexto.md`). Tudo aqui entra como **modo econômico**, que liga e desliga e é comparado em A/B com o modo atual. Nada substitui o fluxo atual antes de o A/B aprovar.

Nada foi implementado. Este documento é para aprovação.

---

## 1. Resposta curta

| Pipeline | Hoje (medido) | Com o modo econômico (estimado) | Mudança principal |
|---|---|---|---|
| Podcast, por episódio | ~0,74 M tokens processados | ~0,25 a 0,40 M (de -46% a -66%), se o custo fixo de uma chamada `claude -p` ficar entre 10 e 20 mil tokens (a Fase 0 mede isso; ver seção 5) | Um driver em Python conduz a série no lugar do orquestrador LLM, chamando redator e crítico por `claude -p` |
| `criar-estudo`, por pasta de 10 arquivos | ~5,96 M | ~2,3 a 2,6 M (de -57% a -62%) | Um subagente redator por arquivo, com contexto mínimo, no lugar de um agente longo |

O crítico continua em Opus. Nenhuma recomendação aprovada mexe nele, porque o Sonnet deixou passar 3 de 4 erros reais.

Aplicado às pastas da análise anterior (36 episódios de podcast), o roteiro cairia de ~27 M para algo entre 9 e 14 M tokens processados.

---

## 2. O que a pesquisa mudou no nosso entendimento

| Achado | Fonte | Consequência |
|---|---|---|
| A Anthropic não publica quanto cada tipo de token pesa no limite do Pro. Só diz que a leitura de cache "conta menos" e que o Opus gasta bem mais que o Sonnet | G2 | Toda economia aparece como faixa: W2 (todo token igual) até W1 (peso pelo preço). O orquestrador é 69% em W2 e 31% em W1; o crítico Opus é o maior em W1 (42%) |
| `claude -p` com login da assinatura é permitido para uso pessoal e consome o mesmo limite. A política mudou duas vezes em 2026 | G1 | O driver é viável, mas o caminho atual (`podcast-serie`) fica mantido como plano B |
| `--bare` exige API key e não serve. O equivalente é `--safe-mode` ou `--strict-mcp-config --disable-slash-commands --setting-sources ""` | G1 | A Fase 0 confirma as flags antes de construir o driver |
| O JSON do `claude -p` traz `usage` e custo estimado por chamada | G1 | A medição do A/B fica simples no caminho do driver |
| Subagentes usam cache de 5 min; a conversa principal usa 1 h. Subagente novo não lê o cache do pai | G2 | Pausas acima de 5 min (ex.: esperar o áudio) fazem regravar o cache. A síntese do áudio fica fora do laço do roteiro |
| O `output_tokens` das transcrições `.jsonl` é parcial (instantâneo do streaming). A medida oficial por requisição e por agente é a telemetria OpenTelemetry (`api_request`) | G2 | A Fase 0 monta um coletor OTel local |
| O custo fixo de partida é pequeno no podcast: redator ~6,3 mil e crítico ~4,5 mil na 1ª chamada. No `criar-estudo` é ~19 a 21 mil | G4 | Enxugar descrições e MCP rende pouco no podcast e uns 6 a 10% no `criar-estudo` |
| No `criar-estudo`, 98% dos tokens são releitura de cache, e uns 70% vêm do contexto que cresce a cada chamada | G4 | O ganho grande está em dividir o trabalho, não em encurtar prompts |
| A limpeza de resultados de ferramenta (`clear_tool_uses`) só existe na API | G4 | Descartada |
| O lint não confere nenhum fato contra o material. Lints de números (L10) e de superlativos (L11) pegariam 2 dos 4 erros reais sem gastar token | G3 | Entra na Fase 1, sem custo |
| O gabarito de regressão está incompleto: a versão com erro do ep. 3 se perdeu e a do ep. 6 precisa ser confirmada | G3 | A Fase 0 refaz o gabarito antes de qualquer teste que mexa na verificação |
| O material do redator é cortado com `t[:cota]` e perde o fim dos arquivos | G4 | Cortar por seção economiza pouco (2 a 4%), mas melhora a qualidade |

---

## 3. Como o modo econômico funciona

- **Podcast:** comando novo `python -m src.podcast.driver <pasta>` (modo econômico) contra pedir ao agente `podcast-serie` (modo atual). As sub-opções ficam numa seção `modo_economico:` do `config.yaml`, uma chave por mudança, para testar uma de cada vez.
- **`criar-estudo`:** opção `redator_por_arquivo` (agente novo ou parâmetro). Desligada, o fluxo atual segue igual.
- **A/B (protocolo do G2, seção 3):**
  - 3 execuções por modo, na ordem ABBA, com a mesma pasta e 10 min de intervalo;
  - tokens por tipo, por modelo e por agente via OTel;
  - W1, W2 e W3, mais a barra do `/usage` antes e depois;
  - qualidade: veredito do lint e do crítico, e o gabarito de erros (os 4 reais mais uns 12 semeados em episódios limpos).
- **Regra de aceite:** o modo econômico só vira padrão se não perder nenhum erro do gabarito que o modo atual pega.

---

## 4. Fases

### Fase 0 · Medir e preparar (sem mudar o sistema)

| Item | O que fazer | Origem |
|---|---|---|
| 0.1 | Coletor OTel local e script de W1, W2 e W3 por execução | G2 R0 |
| 0.2 | Confirmar no `claude -p` com a assinatura: `--safe-mode`, se `--agent` acha os agentes de `~/.claude/agents`, os campos de `usage` no JSON, o custo fixo real de uma chamada e a mensagem de limite atingido | G1, lacunas |
| 0.3 | Refazer o gabarito: reconstruir o erro do ep. 3, confirmar o ep. 6 e semear uns 12 erros em episódios limpos | G3 |
| 0.4 | Medir uma execução do modo atual com o OTel (linha de base W1, W2, W3) | G2 |

### Fase 1 · Podcast econômico (risco baixo)

Uma mudança por vez, cada uma com seu A/B:

| # | Mudança | Ganho estimado | Risco | Origem |
|---|---|---|---|---|
| E1 | Driver em Python no lugar do orquestrador LLM, com parada limpa no limite do plano | De -46% a -66% por episódio em tokens processados (custo fixo de 20 mil ou 10 mil por chamada). O G1 estimou -68% supondo custo fixo baixo | Baixo | G1 R1, R6 |
| E2 | Lints L10 (números) e L11 (superlativos), só como aviso | Zero token; menos reescritas | Falso positivo | G3 |
| E3 | Chamadas isoladas: `--safe-mode` com o prompt do papel; crítico sem ferramentas e com `--json-schema`; reescrita só com Read e Edit | 10 a 30% do custo do redator e do crítico (suposição) | Médio no crítico (o schema precisa bater com `critic.normalizar`) | G1 R2 a R4 |
| E4 | Material por seção, em vez de `t[:cota]` | 2 a 4%, e melhora a qualidade | Baixo | G4 R7 |
| E5 | Reconferência do crítico só nas falas editadas na reescrita | ~8% em W1 | Médio-baixo | G3 B |
| E6 | Áudio fora do laço do roteiro (nenhum agente parado mais de 5 min) | Evita regravar cache | Nenhum | G2 R4 |

Com o driver, o limite de 5 episódios por execução perde o motivo, porque o custo vira linear. Proposta: o driver começa com `--max-episodios 5` por segurança e só sobe depois do A/B. No `podcast-serie`, o limite fica como está.

### Fase 2 · `criar-estudo` econômico (risco médio)

| # | Mudança | Ganho estimado | Risco | Origem |
|---|---|---|---|---|
| C1 | Um orquestrador e um subagente redator por arquivo, com contexto mínimo e um índice de termos compartilhado (o `00_contexto_e_mapa` já faz esse papel) | 5,96 M para ~2,6 M por pasta (-56%; de -45% a -65%) | Coerência entre arquivos (termo definido duas vezes, referência a algo que ainda não foi explicado) | G4 R1 |
| C2 | Desligar os conectores MCP nos projetos de estudo | ~0,35 M por pasta (-6%) | Nenhum | G4 R4 |
| C3 | Tirar os blocos `<example>` das descrições dos agentes (cerca de 2,7 mil tokens em toda chamada que lista agentes) | ~-3,5% | Delegação automática errar mais. Testar com 5 pedidos | G4 R3 |

A/B do C1: tokens por pasta, termos sem definição, referências para a frente, quiz e a sua leitura de 2 arquivos.

### Fase 3 · Testes que arriscam qualidade (só com o gabarito pronto, exigindo 4 de 4)

| Mudança | Ganho | Por que fica para depois | Origem |
|---|---|---|---|
| Crítico Sonnet em esforço `xhigh`, com checklist por afirmação (sozinho ou com o E5) | 11 a 15% em W1 | O Sonnet em esforço medium pegou só 1 de 4 erros; o esforço xhigh nunca foi testado | G3 A e C |
| Redator com autoverificação e esforço ajustado | ~6% | Pode estourar o tamanho e mexer na qualidade do texto | G3 R |

### Descartados ou adiados

| Item | Motivo |
|---|---|
| 1 episódio por execução do `podcast-serie` | Pesquisas em conflito (de -31% a +18%); deixa de importar com o driver. Só volta se o E1 falhar |
| Orquestrador em Haiku ou esforço `low` | Deixa de importar com o driver |
| Reescrita via SendMessage ao mesmo redator | ~2% da série; o driver já resolve de outro jeito |
| `omitClaudeMd` | Menos de 2 mil tokens por subagente, porque o CLAUDE.md global é curto |
| Crítico Sonnet do jeito que foi testado | Deixou passar 3 de 4 erros reais |
| Limpeza de resultados de ferramenta, Batch API, API key, modelos abertos | Fora da assinatura Pro ou rejeitados |

---

## 5. Riscos e premissas

- A política da Anthropic sobre `claude -p` com assinatura mudou duas vezes em 2026. O driver precisa ser fácil de desligar, e o `podcast-serie` continua funcionando.
- Todos os ganhos são estimativas de tokens processados. Os pesos reais no limite do Pro só saem da Fase 0.
- **O custo fixo de uma chamada headless (F) decide o tamanho do ganho do E1, e ainda não foi medido.** Ele é relido em cada turno dentro da chamada: uns 11 turnos por episódio (redator ~4, crítico ~3, mais 60% de chance de reescrita e reconferência). Hoje, como subagentes, redator e crítico partem de ~5 mil. Conta: episódio com driver ≈ 0,23 M + (F − 5 mil) × 11.
  - F = 10 mil: ~0,29 M (-61%)
  - F = 20 mil: ~0,40 M (-46%)
  - F ≈ 50 mil: empata com o modo atual

  Por isso, `--safe-mode`, `--tools ""` no crítico e prompt próprio por papel (E3) entram junto com o E1, e a medição 0.2 vem antes de construir o driver.

## 6. Pesquisas de origem

- `pesquisa_g1_orquestracao_codigo.md`: driver em Python, `claude -p` e flags
- `pesquisa_g2_limite_cache_medicao.md`: limite do Pro, cache e protocolo de medição
- `pesquisa_g3_verificacao_esforco.md`: crítico, lint, esforço e gabarito
- `pesquisa_g4_contexto_custo_fixo.md`: custo fixo, `criar-estudo` e material de entrada

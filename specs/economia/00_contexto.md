# Pesquisa de economia de tokens · contexto compartilhado (2026-11-07)

Leitura obrigatória de todo pesquisador desta pasta. Objetivo da pesquisa: reduzir o gasto de tokens das gerações do `agente_estudos` (podcast de estudo e `criar-estudo`) sem perder qualidade, ou com um trade-off claramente positivo.

## 1. Restrições (não negociáveis)

- O usuário só tem a **assinatura Claude Pro** (uso pelo Claude Code com login da assinatura). **Não tem API key** da Anthropic nem de nenhum outro provedor pago. Está FORA: Batch API, Agent SDK com chave, "pagar API em vez do plano", OpenAI/Groq/outras chaves, outras assinaturas, modelos abertos (rejeitados nesta rodada).
- O que conta é o **limite do plano Pro** (janela de 5 h + limite semanal, compartilhados com o claude.ai), não o preço em dólar. Quando uma fonte falar de preço de API, use-a só como pista de peso relativo e diga isso.
- Modelos disponíveis no Claude Code: Opus 5.5, Sonnet 5.5, Haiku 5.5 (Fable fica fora, é pago à parte).
- **Toda recomendação precisa caber num "modo econômico"** do sistema de podcasts (e, quando couber, do `criar-estudo`): uma opção que liga e desliga, para comparar em A/B contra o modo atual. Para cada recomendação, diga: o que muda (prompt, agente, código, config), como ligar e desligar, que métrica comparar e qual o risco de qualidade.

## 2. O sistema hoje

- Projeto: `/home/robertocaetano207/dev/agente_estudos` (Python). Specs do podcast: `specs/voz/` (ler `BUILD_REPORT.md`, seção "Redução de custo" em diante).
- Orquestração do podcast (fonte única): `prompts/podcast_orquestracao.md`. Prompts: `prompts/podcast_redator.md`, `podcast_critico.md`, `podcast_planejador.md`. CLI determinística: `src/podcast/agente.py`.
- Agentes do Claude Code: `~/.claude/agents/podcast-serie.md` (orquestrador, Sonnet), `gerar-podcast.md` (redator, Sonnet), `podcast-critico.md` (crítico, Opus), `criar-estudo.md` (Opus, escreve as pastas de estudo; lê `prompts/regras_didaticas.md`).
- Fluxo do podcast por episódio: orquestrador roda `entradas` → redator escreve (lint embutido) → crítico avalia → se reprovado, 1 reescrita com Edit → crítico de novo → orquestrador roda `finalizar && entradas N+1`. Limite atual: no máximo 5 episódios por execução (8.3 da orquestração).

## 3. O que já foi medido (use como linha de base)

| Medida | Valor | Fonte |
|---|---|---|
| Tokens por episódio, configuração atual (série de 5) | ~0,74 M processados (quase tudo leitura de cache) | transcrições da sessão `~/.claude/projects/-home-robertocaetano207-dev-agente-estudos/7db0877c-3b31-436a-a42c-cd4174ee4226/` (subagentes "Gerar/Criticar episódio 1–5" e orquestrador `agent-a3567040443998918`), 11/10/2026 |
| Divisão desses tokens | orquestrador 69% (2,57 M em 45 chamadas), redator 20%, crítico 11% | idem |
| Contexto do orquestrador por chamada | sobe de 21 mil (1ª) e 34 mil (2ª) até 80 mil (45ª): ~+1 mil por chamada, ~8–9 chamadas por episódio → custo total quadrático no nº de episódios | idem |
| Série antiga, tudo em Opus (devops, 9 ep.) | ~8,8 M lidos de cache, ~1,0 M escritos em cache, ≥100 mil de saída; cache escrito pelos subagentes = 58% do custo | `specs/voz/BUILD_REPORT.md` |
| Custo em US$ da configuração atual | crítico Opus 42%, orquestrador 31%, redator 27% (preço de API, só como peso relativo) | `BUILD_REPORT.md` |
| Tempo | roteiro ~3 min/ep; áudio edge-tts ~5 min/ep (0 tokens) | idem |
| `criar-estudo` (pasta devops) | 77 chamadas, ~5,96 M tokens processados, 45 min | mesma sessão, subagente `criar-estudo` de 45 min |
| `criar-estudo` (pasta CNT-34, 10 arquivos) | 83 chamadas de ferramenta, 24 min | sessão atual |
| Custo fixo de partida | o 1º pedido de um subagente já tem ~21 mil tokens; o 2º, ~34 mil (depois de ler o prompt de orquestração) | transcrição do orquestrador |
| Limitação de medida | o `output_tokens` gravado nas transcrições `.jsonl` parece parcial (valores de 40–200 por subagente que escreveu 3 mil palavras) | script `/tmp/claude-1000/-home-robertocaetano207-dev-aferes/5ef0429d-5bcc-4cda-9d71-bb1c52bbcb36/scratchpad/uso_subagentes.py` |

Pesquisa anterior, mais geral (não repetir, só complementar ou corrigir): `/home/robertocaetano207/dev/aferes/pesquisa_agentes.md`.

## 4. Formato de saída de cada pesquisador

Arquivo `.md` em português do Brasil, sem blockquote (`>`), com:

1. **Respostas diretas** às perguntas do briefing, uma seção por pergunta.
2. Cada afirmação marcada: `[FATO: Fn]` (com fonte numerada no fim, URL e data de acesso), `[INFERÊNCIA]` ou `[SUPOSIÇÃO]`. Fonte oficial da Anthropic vale mais que blog; relato da comunidade só com número medido.
3. **Recomendações para o modo econômico**: tabela com recomendação · o que muda · como ligar/desligar · ganho estimado (com a conta) · risco de qualidade · métrica do A/B.
4. **Lacunas**: o que não deu para confirmar.
5. **Fontes** numeradas.

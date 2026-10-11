# BUILD_REPORT — Podcast de estudo por voz (em andamento)

**Atualizado:** 2026-10-10 · Implementa `DESIGN.md` §9. Branch: `feat/podcast-e-limpeza-html`.

## Estado por etapa

| Etapa | Estado | Verificação |
|---|---|---|
| B1 — `script_io`, `lint`, `normalize`, `material` + pytest | ✅ feito | `pytest` verde |
| B2 — planner, writer, critic, `--mode podcast`, `relatorio.json`, `temperature` por chamada no `LLMClient`, prompts v2 em `prompts/` | ✅ código + testes com LLM falso (55 testes no total) | ⚠️ **não rodado contra modelo real**: as chaves OpenAI e Groq do `config.yaml` local devolveram 401 (inválidas) em 2026-10-10 |
| B3 — `src/tts` (edge), montagem, cache, `voice-test` | ⏳ pendente | — |
| B4 — xtts / chatterbox / qwen3 + `notebooks/podcast_audio.ipynb` | ⏳ pendente | — |
| B5 — agentes `gerar-podcast` e `podcast-critico` + Fase 8 do `criar-estudo` + CLI `src.podcast.agente` | ✅ feito | ✅ **testado com o agente Claude real** (2026-10-10): série de 5 episódios planejada (válida na 1ª tentativa); episódios 1 e 2 gerados, lint e crítica aprovados; o crítico pegou um erro real de fidelidade no ep. 2 e a reescrita corrigiu |
| B6 — README final, changelog dos prompts | ⏳ parcial (README menciona o modo como "em construção") | — |

## Teste real do caminho Claude (B5) — achados corrigidos

Cópia de `~/obsidian/machine_learning/alura_modelos_tradicionais_classificacao` no scratchpad, fora do vault. Os achados do teste e o que mudou:

- **Lint L5 com falso positivo** em "veja que pergunta você está fazendo": "que" e "grande" saíram da lista de elogios.
- **Ponte do planejador para arquivo de episódio futuro** (ep. 1 → arquivo do ep. 4): agora é removida em código no `consertar` e no `pontes_filtradas`.
- **`--reescritas` ambíguo:** passou a ser o total de reescritas (lint + crítico), como no Python.
- **Reescrita "completa" × "só o trecho":** a regra agora é gravar o arquivo inteiro e mudar só o necessário.
- **`commit` no frontmatter não refletia código não commitado:** agora usa `git describe --always --dirty`.
- **Observado, sem mudança:** o planejador listou de 7 a 14 conceitos em "introduz" por episódio, e o crítico aprovou assim mesmo. Fica a avaliar se a v3 do prompt do planejador deve limitar a quantidade.

## Como verificar o B2 com um modelo real (pendente)

1. Renove uma chave (Groq tem camada gratuita) no `config.yaml`.
2. Copie uma pasta pequena do vault para fora dele (o comando escreve em `<pasta>/podcast/`).
3. `python main.py --mode podcast --pasta <cópia>`.
4. Confira `podcast/relatorio.json` (lint/crítica/reescritas por episódio) e ouça mentalmente 1 roteiro.
5. Rode os casos R-T*/C-T* de `PROMPTS.md` como eval offline — ainda não existe script para isso (DESIGN §8).

## Interpretações e desvios (registrar se virar ADR)

- **R22 — reescrita guiada pelo crítico que quebra o lint:** mantém a versão anterior (que já passava no lint) com o veredito anterior, em vez de gravar a última versão. Motivo: não trocar um problema de conteúdo por um de formato, pior para o áudio.
- **R7 sem `serie.json`:** `--episodios` exige série já planejada (erro antes de qualquer chamada), em vez de planejar e depois validar.
- **Limpeza de formato antes do lint:** cercas de código e preâmbulo antes do primeiro `## ` são removidos por código (deslize sem significado); todo o resto fica para o lint julgar.
- **Pontes no frontmatter (D11):** extraídas do texto por código: menções D8 a episódios anteriores e falas que citam o título de um arquivo que não é fonte do episódio.
- **Busca RAG (R25/R26):** usa `_load_index` + `search` direto do `indexer`, porque `search_vault` chama `build_or_update_index` e reindexaria a pasta.
- **DEFINE v1.1** (D7, R15, R17) — ver Histórico no `DEFINE.md`.

## Redução de custo (2026-10-11)

Medição da série `devops/01_fundamentos_devops` (9 episódios, tudo em Opus 5.5): ~8,8 M tokens lidos de cache, ~1,0 M escritos em cache, ≥ ~100 mil de output. Custo a preço de tabela: ≥ ~$8,70, cerca de $1 por episódio. O cache escrito pelos sub-agentes responde por 58%.

Mudanças sem impacto na qualidade:
- **Meta de palavras 2.200–2.700, teto 3.000 no prompt.** Na série medida, 4 de 9 primeiras versões estouraram 3.200 e foram refeitas.
- **Lint L9 (R17b) e redator v4, regra 8 "sem bastidor".** O prompt v3 induzia frases como "é o nome usado no material"; a série tinha 75 falas assim, e o crítico oscilava entre aprovar e reprovar.
- **Reescrita pontual com Edit** (lint e crítico), em vez de regravar o roteiro inteiro.
- **Menos chamadas do orquestrador:** o backup passou para o sub-agente (`agente backup`); o `finalizar` restaura sozinho quando a reescrita quebra o lint; `finalizar N` e `entradas N+1` rodam numa só chamada Bash.

### Teste: crítico em Sonnet 5.5 contra o gabarito do Opus

O teste usou 4 roteiros com problema real achado pelo Opus (versões antes da reescrita) e 2 episódios aprovados de primeira. O prompt do crítico foi o mesmo, v3, e o esforço ficou no padrão do Sonnet.

| Ep | Problema real (achado pelo Opus) | Sonnet 5.5 |
|---|---|---|
| 3 | "Cada sexta era uma aposta nova" — no material o deploy era trimestral | ❌ aprovou |
| 6 | Atribui à cardinalidade o que o material atribui à agregação das métricas | ❌ aprovou |
| 7 | "A definição mais citada" (de Fowler), sem fonte | ❌ aprovou |
| 8 | "Nome usado no material" (bastidor) | ✅ pegou |
| 2, 5 | Limpos | ✅ sem falso positivo |

Custo de entrada por execução: Sonnet ~$0,084 contra Opus ~$0,156 (1,9× mais barato, com o mesmo volume de tokens). Em 9 episódios, isso economizaria ~$0,9 (~11% da série) e deixaria passar 3 de 4 erros de fidelidade.

**Decisão:** o crítico continua em Opus. O erro do ep. 8 agora é barrado pelo lint L9, sem LLM.

# BUILD_REPORT — Podcast de estudo por voz (em andamento)

**Atualizado:** 2026-10-10 · Implementa `DESIGN.md` §9. Branch: `feat/podcast-e-limpeza-html`.

## Estado por etapa

| Etapa | Estado | Verificação |
|---|---|---|
| B1 — `script_io`, `lint`, `normalize`, `material` + pytest | ✅ feito | `pytest` verde |
| B2 — planner, writer, critic, `--mode podcast`, `relatorio.json`, `temperature` por chamada no `LLMClient`, prompts v2 em `prompts/` | ✅ código + testes com LLM falso (55 testes no total) | ⚠️ **não rodado contra modelo real**: as chaves OpenAI e Groq do `config.yaml` local devolveram 401 (inválidas) em 2026-10-10 |
| B3 — `src/tts` (edge), montagem, cache, `voice-test` | ⏳ pendente | — |
| B4 — xtts / chatterbox / qwen3 + `notebooks/podcast_audio.ipynb` | ⏳ pendente | — |
| B5 — agentes `gerar-podcast` e `podcast-critico` + Fase 8 do `criar-estudo` | ⏳ pendente | — |
| B6 — README final, changelog dos prompts | ⏳ parcial (README menciona o modo como "em construção") | — |

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

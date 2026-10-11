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

### Teste: redator em Sonnet 5.5 (crítico Opus), episódios 3, 6 e 7 do devops

O teste usou as mesmas entradas que o Opus recebeu. A única diferença foi a meta de palavras, que passou de "2200 a 3000" para "2200 a 2700".

| | Opus 5.5 (série original) | Sonnet 5.5 |
|---|---|---|
| Problemas na 1ª versão, segundo o crítico Opus | 1 / 1 / 1 | 3 / 3 / 2 |
| Depois de 1 reescrita | aprovados | aprovados |
| Custo de entrada do redator (3 episódios) | $1,22 | $0,49 |
| Output estimado do redator | ~$0,84 | ~$0,20 |
| Palavras | 2714 / 2981 / 3136 | 2787 / 2989 / 2421 |

- **Erros típicos do Sonnet:** precisão numérica (2.400 ms lidos como "dois segundos e meio"), atribuição sem fonte, anúncio do conteúdo do próximo episódio e o Professor confirmando uma reformulação errada do Aprendiz.
- **Leitura do texto:** natural e didático, no mesmo padrão do Opus.
- **Decisão:** o redator `gerar-podcast` passa a usar Sonnet e o crítico continua em Opus. O custo por episódio cai ~1,8×. O risco aceito é que, com primeiras versões mais erradas, cresce a chance de algum erro escapar também do crítico.

### Bastidor removido da série devops

As 75 falas de bastidor foram corrigidas com edição pontual (Sonnet, modo reescrita) nos episódios 1–6 e 9. Os 9 episódios passam no lint. Os metadados foram refeitos com `finalizar`, que soma 1 reescrita. O veredito do crítico é o da versão anterior às edições, porque elas não mexeram no conteúdo técnico.

### Orquestração movida para `prompts/podcast_orquestracao.md`

A orquestração passou a ser fonte única, lida pelo novo agente `podcast-serie` (orquestrador dedicado, Sonnet) e pela Fase 8 do `criar-estudo`. O `criar-estudo` continua em Opus, porque também escreve o material de estudo.

### Teste: configuração final (orquestrador Sonnet, redator Sonnet, crítico Opus), série completa

Cópia limpa de `alura_modelos_tradicionais_classificacao`: 6 arquivos, 5 episódios, 9.038 palavras.

- **Planejamento v3:** de 3 a 5 conceitos centrais e de 1 a 6 de apoio por episódio. A v2, na mesma pasta, tinha listado de 7 a 14 centrais.
- **Resultado:** 4 episódios aprovados; o episódio 2 terminou `critica: reprovado`. A 1ª crítica só apontou uma ponte; depois da reescrita, a 2ª crítica achou uma contradição de fidelidade que já estava na 1ª versão. É sinal de que o crítico não é determinístico, e o problema ficou registrado no frontmatter.
- **Orquestrador:** 45 chamadas, sem nenhuma falha, e o planejamento passou na 1ª tentativa. O passo `finalizar N && entradas N+1` foi seguido. Sobrou um loop de espera desnecessário.
- **Custo de entrada:** $2,28, dividido assim:

| Papel | Custo |
|---|---|
| Crítico Opus (8 execuções) | $0,96 |
| Orquestrador Sonnet | $0,70 |
| Redator Sonnet (7 execuções) + 1 execução em Opus | $0,48 + $0,14 |

  A execução em Opus veio da definição do agente recarregada com atraso dentro da sessão.
- **Custo total estimado (com output):** ~$2,6, ou ~$0,52 por episódio. Os episódios desta pasta são mais curtos que os do devops, então a comparação direta é a do A/B acima.
- **Gargalo atual:** o crítico em Opus virou o maior custo (42%). Com primeiras versões piores, ele roda mais vezes: 1,6 execução por episódio, contra 1,44 com o redator em Opus.

## B3 — áudio local (edge-tts) — 2026-10-11

`src/tts/`:
- `audio.run`: lint reprovado é pulado (R28), clone validado antes de sintetizar (R31), cache atômico (R32/R33) e manifesto (R34);
- `voice_test.run`: R35–R37;
- motores: `edge`, `xtts`, `chatterbox` e `qwen3`;
- montagem com ffmpeg e `wave`: silêncio das pontas aparado, pausas configuráveis, loudnorm −16 LUFS, MP3 mono 128k;
- números por extenso com `normalizar` (R19) e falas longas quebradas pelo `max_chars` de cada motor.

Na CLI: `--mode podcast-audio` e `--mode voice-test`, com `--engine` e `--saida`. São 77 testes, com um motor falso e ffmpeg real.

**Testado de verdade (edge-tts):**
- Teste de vozes: 5 falas, MP3 de 43 s, vozes Antonio (Professor) e Francisca (Aprendiz).
- Episódio 1 do devops (3.041 palavras, 136 falas): síntese em 5 min 35 s. MP3 de 19 min 21 s, contra 20 min 16 s estimados no roteiro. Loudness −16,5 LUFS, 18,6 MB.
- 2ª execução: 100% do cache, 22 s (só concatenação e codificação).
- O cache ocupa ~52 MB por episódio, por isso saiu do vault (`voz.cache_dir`).

**Observado:** as pausas entre frases dentro de uma fala (~0,9 s) são da prosódia do próprio edge-tts, não da montagem.

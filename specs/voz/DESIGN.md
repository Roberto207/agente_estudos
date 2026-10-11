# DESIGN — Podcast de estudo por voz

**Status:** Aprovado em 2026-10-10 · Implementa `DEFINE.md` v1 (D1–D11, R1–R38). Prompts v1 em `PROMPTS.md`.

## 1. Visão geral

```
 pasta de estudo (.md finalizados, guia_de_estudos.md)
        │
        ▼  ESTÁGIO 1 — roteiros (mesmo LLM do fluxo: Python → provider do config; Claude → Claude)
 ┌──────────────┐   serie.json   ┌──────────────┐  roteiro  ┌──────┐  ok   ┌──────────┐
 │ Planejador   │──────────────▶│ Redator (×N) │─────────▶│ Lint │─────▶│ Crítico  │
 │ (1 chamada)  │               │ sub-agente   │◀─────────│ det. │◀─────│ sub-agente│
 └──────────────┘               └──────────────┘ reescrita └──────┘ reprova└──────────┘
        │                                  (no máx. 1 reescrita por lint e 1 por crítico)
        ▼
 podcast/serie.json · podcast/episodio_NN_<slug>.md (frontmatter = rastro) · podcast/relatorio.json
        │
        ▼  ESTÁGIO 2 — áudio (local: edge-tts | notebook GPU: xtts / chatterbox / qwen3)
 parse falas → normaliza (num2words) → TTS fala-a-fala (cache por hash) → concatena + pausas + loudnorm
        ▼
 podcast/audio/episodio_NN_<slug>.mp3 + .json (manifesto)
```

Decisões de arquitetura (viram ADRs curtos na Fase 4):
- **ADR-001: dois estágios e síntese fala a fala.** O roteiro é um artefato revisável e barato. A síntese fala a fala funciona com qualquer engine e dá cache granular. Modelos de diálogo nativo (VibeVoice, Dia) ficam como engines futuros, porque o pt-BR deles não está confirmado.
- **ADR-002: prompts como fonte única em `prompts/`.** Python e agentes Claude leem os mesmos arquivos, no mesmo padrão já adotado em `prompts/regras_didaticas.md`.

## 2. Módulos (projeto Python)

| Caminho | Responsabilidade |
|---|---|
| `src/podcast/__init__.py` | `run(config, pasta, replanejar=False, episodios=None)`, que orquestra o estágio 1 |
| `src/podcast/material.py` | Implementa D1 (`.md` de conteúdo) e D2/D3 (ordem do guia e posição do episódio); expõe a contagem de palavras usada em D9 |
| `src/podcast/planner.py` | Prompt do planejador, `chat_json` com retry e **validação em código** (R9–R11, arquivos existentes, `ideia` ≤ 20 palavras); detecção de `serie.json` desatualizado (R3/R4) e arquivamento no `--replanejar` (R5) |
| `src/podcast/writer.py` | Monta o contexto do episódio (§5) com tags de id aleatório e neutralização de tags forjadas; filtra pontes sem base (R-T9); chama o redator; reescritas de R21/R22 |
| `src/podcast/critic.py` | Chama o crítico com as **mesmas entradas do redator** + roteiro; valida o schema; **calcula em código** `ok` por critério e `aprovado`; trunca citações; erro vira `indisponivel` (R23) |
| `src/podcast/lint.py` | Lint determinístico (§6). Também roda como CLI (`python -m src.podcast.lint <arquivo>`), usado pelo agente Claude |
| `src/podcast/script_io.py` | Lê e escreve o roteiro: frontmatter D11, parse de falas (D6) e blocos, contagem de palavras, `duracao_estimada_s` |
| `src/podcast/normalize.py` | Texto da fala → texto falável (R19): `num2words(lang="pt_BR")` para inteiros, decimais, ordinais, anos e `%`; tabela de casos em `tests/podcast/normalize_casos.json`. Roda só no estágio 2 (o roteiro guarda dígitos) |
| `src/tts/base.py` | `class Engine(Protocol): nome; clona: bool; sintetizar(texto, voz, ref_wav|None, saida_wav) -> None` |
| `src/tts/edge.py` · `xtts.py` · `chatterbox.py` · `qwen3.py` | Adaptadores com **import tardio**, para a máquina local não precisar de torch. Cada um declara `clona` |
| `src/tts/registry.py` | `get_engine(nome)` e `engines_que_clonam()` (D10, usado em R31/R36) |
| `src/tts/assemble.py` | Concatena WAVs com pausas (`fala`/`bloco`), aplica `loudnorm` do ffmpeg e gera MP3 mono 128k |
| `src/tts/audio.py` | `run(config, pasta, episodios=None, engine=None)`: pula `lint: reprovado` (R28), valida clone antes de sintetizar (R31), cache atômico (R32/R33), manifesto (R34) |
| `src/tts/voice_test.py` + `src/tts/trecho_teste.md` | Trecho fixo de 5 falas para cada engine de `voz.teste.engines`; clone só onde D10 (R36); falha isolada + `relatorio.json` (R37) |
| `prompts/podcast_{planejador,redator,critico}.md` | Prompts aprovados, com cabeçalho `versao: N` |

`main.py` ganha os modos `podcast`, `podcast-audio` e `voice-test`, e as flags `--replanejar`, `--episodios 2,5`, `--engine` e `--saida`.
`LLMClient.chat`/`chat_json` ganham o parâmetro opcional `temperature`, que sobrescreve o do provider. É o que permite o gate central `podcast.temperaturas`.
Novas dependências: `num2words` (pura) e `edge-tts` (leve). Os engines de GPU (`coqui-tts`, `chatterbox`, Qwen3-TTS) são instalados **só no notebook**, fora do `requirements.txt` principal.

## 3. Configuração

```yaml
podcast:
  palavras: {min: 2000, max: 3200}
  max_chars_material: 24000        # orçamento de contexto do material por episódio
  rag_raiz: ""                     # ex. ~/obsidian — vazio desliga pontes entre pastas (R12/R13)
  rag_k: 5
  temperaturas: {planejador: 0.3, redator: 0.8, critico: 0.1}
  reescritas: 1
voz:
  engine: edge                     # edge | xtts | chatterbox | qwen3
  engines:                         # vozes fixas POR engine (os nomes de voz não são intercambiáveis)
    edge:  {professor: pt-BR-AntonioNeural, aprendiz: pt-BR-FranciscaNeural}
    xtts:  {professor: "<speaker embutido>", aprendiz: "<speaker embutido>"}
    chatterbox: {professor: default, aprendiz: default}
    qwen3: {professor: "<voz pt>", aprendiz: "<voz pt>"}
  clone:                           # opcional; só xtts/chatterbox (e qwen3 se confirmado)
    professor: {ref_wav: null}
    aprendiz:  {ref_wav: null}
  pausa_ms: {fala: 250, bloco: 700}
  teste: {engines: [edge, xtts, chatterbox, qwen3]}
```
Os nomes de voz dos engines open-source são preenchidos no B4, depois de inspecionar cada modelo. Não chuto nomes.

## 4. Lado Claude (agentes) — R38

No caminho Claude, o LLM é o próprio Claude, e todo o resto é determinístico.

**A ponte com o Python.** `python -m src.podcast.agente` é uma CLI **sem LLM**. Ela expõe as mesmas funções do caminho Python, de modo que os dois produzem os mesmos artefatos:

| Subcomando | Faz |
|---|---|
| `status` | Estado da série: `ausente`, `valida` ou `desatualizada_ou_invalida`; lista os episódios sem roteiro (R1/R3/R4) |
| `planejamento` | Escreve a entrada do planejador (`mensagem_planejamento`, a mesma do Python) em `podcast/.agente/` |
| `serie` | Valida o plano. Sai com código 3 e a lista de erros para o agente corrigir, no máximo 2 vezes; com `--forcar`, `consertar` resolve o resto. Arquiva no `--replanejar` |
| `entradas` | Grava `podcast/.agente/entradas_NN.md`, com as mesmas tags com id que o redator e o crítico recebem no Python (`montar_entradas`) |
| `finalizar` | Lint, normaliza o JSON do crítico, grava o frontmatter D11 (`frontmatter()`, a mesma função do Python, com `gerado_por: claude-agent`) e uma linha no `relatorio.json` |

**Os papéis.**
- **`criar-estudo`, Fase 8 opcional**: é o próprio agente que planeja. O planejador não é sub-agente porque precisa da visão do todo e é uma única chamada. A Fase 8 orquestra os episódios em ordem crescente, com no máximo 1 reescrita guiada pelo crítico. Se a reescrita reprovar no lint, restaura o backup.
- **`~/.claude/agents/gerar-podcast.md`** (redator): lê `prompts/podcast_redator.md` e o arquivo de entradas, grava o roteiro e roda `python -m src.podcast.lint`, corrigindo uma vez se reprovar.
- **`~/.claude/agents/podcast-critico.md`** (verificador independente): lê `prompts/podcast_critico.md`, as entradas e o roteiro, e grava o JSON. Não emite veredito global; quem calcula é o `finalizar`.

**Ganho dos sub-agentes:**
- contexto limpo (sem as transcrições e o histórico do agente principal);
- verificador separado do autor.

**Custo:** handoff entre agentes e mais chamadas.

**Limitação:** os episódios rodam em sequência, porque as entradas do episódio N resumem os roteiros já escritos dos anteriores.

## 5. Contexto de cada chamada do redator (e do crítico — mesmas entradas)

| Bloco | Conteúdo | Limite |
|---|---|---|
| `<situacao>` | número, total, primeiro/último, `material_curto` (D9), `palavras_material`, `palavras_alvo`, `introduz`, `proximo_tema` (sanitizado para D7) | — |
| `<material>` | `.md` dos arquivos do episódio, em ordem | `max_chars_material` (truncamento proporcional por arquivo) |
| `<episodios_anteriores>` | **resumo determinístico**: título, títulos dos blocos e `introduz` de cada episódio já escrito | ~80 palavras/episódio |
| `<pontes_sugeridas>` | pontes do `serie.json` **filtradas em código**: some a "retomada" cujo conceito não está no resumo do episódio citado e toda ponte para episódio ≥ N | — |
| `<outras_pastas>` | `search_vault` sobre `rag_raiz` (só se o índice existir; **nunca indexa**, R26) | `rag_k` × 800 chars |

Defesas em código (não confiadas ao prompt): cada bloco é delimitado com um id aleatório por chamada; antes de montar o prompt, qualquer `<` seguido de nome de tag no conteúdo vira `‹`, então tag forjada não fecha nada. O resumo é determinístico (não LLM) para não somar chamada nem alucinação.

## 6. Lint determinístico (camada barata antes do crítico)

| Código | Regra (DEFINE) | Resultado |
|---|---|---|
| L1 | Linha fora de frontmatter/`## `/fala (R12) | reprova |
| L2 | Caractere fora da lista branca D7, `.` entre letras (R14) — pega markdown, LaTeX, código, rubricas `(risos)`/`[música]` | reprova |
| L3 | Palavras de fala fora de 2.000–3.200; limite inferior ignorado em material curto D9 (R13) | reprova |
| L4 | Ep. 1 com "episódio anterior"; menção a episódio ≥ N com marcador de passado; episódio inexistente; "próximo episódio" no último (R15) | reprova |
| L5 | Elogio a pergunta/dúvida/observação em qualquer fala (R17) | reprova |
| L6 | Ep. N > 1 sem menção D8 a episódio anterior (R16) | aviso |
| L7 | Aprendiz sem nenhum "por que/por quê" ou sem nenhum "e se" (R18) | aviso |
| L8 | Mais de 2 falas seguidas do Aprendiz que só concordam (≤ 6 palavras + "entendi/faz sentido/certo/legal") | aviso (o crítico decide) |

Fluxo (R21/R22): lint reprova → 1 reescrita com as violações → lint de novo → persiste = `lint: reprovado`, `critica: nao_avaliado`. Lint ok/aviso → crítico → reprova → 1 reescrita → lint + crítico de novo → grava a última versão.

## 7. Áudio

- Parse das falas, `normalize.py`, chave de cache `sha1(engine|versão do adaptador|voz ou sha1 do ref_wav|texto normalizado)` (R32), e o arquivo `podcast/audio/.cache/<chave>.wav`, gravado como `.tmp` e renomeado (R33). A retomada vem do próprio cache. No notebook, o cache só sobrevive à sessão se a pasta estiver no Drive (Colab) ou for salva como output (Kaggle).
- A montagem coloca a pausa `fala` entre falas e `bloco` entre blocos, aplica `ffmpeg loudnorm` (−16 LUFS) e gera MP3.
- O manifesto `episodio_NN_<slug>.json` registra engine, vozes ou o hash do `ref_wav`, o sha1 do roteiro, a duração real (ffprobe), a data e a versão do pacote do engine.
- **Notebook `notebooks/podcast_audio.ipynb`** (GPU), seguindo o mesmo padrão do `gerar_estudo.ipynb`:
  - escolhe o engine;
  - instala só as dependências dele;
  - recebe a pasta `podcast/` (upload ou Drive);
  - roda `voice-test` ou `podcast-audio`;
  - zipa os `.mp3`.
- Licenças: XTTS-v2 tem licença Coqui Public Model License (não comercial), adequada para uso pessoal de estudo. Chatterbox é MIT. `edge-tts` usa um serviço da Microsoft não oficial e pode parar de funcionar.

## 8. Os três pilares

**Identidade.** O frontmatter de cada roteiro (chaves fixas em D11) registra:
- `prompts: {planejador: v1, redator: v1, critico: v1}`, mais o sha1 de cada arquivo de prompt;
- `provider` e `modelo`;
- `gerado_por: python|claude-agent`;
- `commit` (git, quando houver);
- `data`.

O manifesto de áudio fecha a cadeia roteiro → áudio pelo sha1 do roteiro. Com isso dá para responder qual prompt, modelo e engine geraram um áudio ruim.

**Observabilidade.**
- `podcast/relatorio.json` por execução registra, por episódio: palavras, duração estimada, códigos de lint, veredito e problemas do crítico, número de reescritas, tempo e erros. O console mostra a mesma tabela.
- **Suíte mínima `pytest` (a primeira do repositório)** cobre só as partes determinísticas: lint (L1-L7), `script_io` (parse e frontmatter), `normalize` (números e símbolos), validação do planejador (R6 e R8) e chave de cache. Um LLM falso cobre o fluxo de reescrita e o fail-open (R20/R21).
- **Eval offline dos prompts:** os casos R-T*, P-T* e C-T* viram fixtures em `tests/podcast/casos/`, com um script que roda contra o LLM configurado e salva os resultados. Ele é rodado manualmente a cada mudança de versão de prompt, sem CI.

**Rastreabilidade.**
- O roteiro lista `fontes` (arquivos) e `pontes` (alvo e fala).
- O crítico cita a fala e o trecho do material de cada problema.
- `serie.json` registra o que cada episódio introduz e retoma.
- As ADR-001 e ADR-002 ficam em `docs/decisions/`.

**Débito técnico declarado.**
1. A fidelidade é checada por LLM, sem citação por fala. Um erro sutil pode passar.
2. Não há métrica automática de naturalidade do áudio; vale o ouvido do estudante.
3. O resumo determinístico de episódios anteriores é pobre em nuance, o que é aceito para evitar alucinação.

## 9. Ordem de build (cada etapa verificável sozinha)

| Etapa | Entrega | Verificação |
|---|---|---|
| B1 | `script_io`, `lint`, `normalize` e pytest | `pytest tests/podcast` verde |
| B2 | planner, writer e critic + `--mode podcast` + `relatorio.json` + `temperature` no `LLMClient` | rodar numa pasta real pequena; lint e crítico registrados no frontmatter |
| B3 | `src/tts` com `edge` + assemble + cache + `voice-test` local | `--mode voice-test` gera o MP3 do edge; segunda execução de `podcast-audio` usa 100% do cache |
| B4 | adaptadores `xtts`, `chatterbox` e `qwen3` + `podcast_audio.ipynb` | `voice-test` no Kaggle gera um MP3 por engine; escuta comparativa (H4) define o engine padrão |
| B5 | agentes `gerar-podcast` e `podcast-critico` + Fase 8 do `criar-estudo` | gerar 1 episódio pelo agente Claude e passar no `python -m src.podcast.lint` |
| B6 | README e prompts finais com changelog | — |

Os prompts só são gravados em `prompts/` depois do portão da skill `prompt-engineering` (PROMPTS.md, Fase 6).

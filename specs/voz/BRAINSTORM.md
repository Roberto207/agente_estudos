# BRAINSTORM — Podcast de estudo por voz

**Status:** Aprovado em 2026-10-10 · **Trilha SDD:** pipeline completo · **Origem:** `ideia_voz.md` (2026-06-16) + conversa de 2026-10-10

## Problema percebido

O material escrito (pastas `.md` no Obsidian) só é consumido sentado, lendo. O estudante quer revisar
em deslocamento/tarefas manuais, em **áudio**, num formato que ensine e não só leia em voz alta.
Ler o `.md` com TTS não serve: markdown, fórmulas, tabelas e código não "soam"; e um monólogo
tem retenção baixa.

## O que já está decidido (não reabrir)

- Formato **diálogo socrático**: Professor muito explicativo + Aprendiz que pergunta ("por quê?",
  "e se…?", "isso se conecta com X?"), relacionando assuntos **entre arquivos e entre episódios**, com naturalidade.
- **Dois estágios**: (1) roteiro escrito pelo mesmo LLM do fluxo, só **depois** do material escrito
  finalizado; (2) áudio a partir do roteiro.
- TTS **gratuito**, de preferência em **Kaggle/Colab** (GPU) — local só quando o engine for leve.
- Vozes **fixas** por papel; clonagem **configurável e testável**, sem voz definida agora.
- Valer nos **dois lados**: agente Claude `criar-estudo` e projeto Python `agente_estudos`.
- Sub-agente: **sim** para redator de episódio e crítico; **não** para o planejador da série.

## Hipóteses (a validar)

| # | Hipótese | Como validar |
|---|---|---|
| H1 | Planejar a série inteira antes (o que cada episódio introduz/retoma) é o que faz as pontes soarem naturais | Comparar 1 episódio escrito com e sem `serie.json` no contexto |
| H2 | Um crítico separado do redator pega contradições e "professor que só cita" que o redator não vê | Casos adversariais do PROMPTS.md |
| H3 | ~2.500 palavras ≈ 17 min em pt-BR é o tamanho certo por episódio | Ouvir 2 episódios reais |
| H4 | Qwen3-TTS / Chatterbox-pt / XTTS-v2 superam `edge-tts` em naturalidade de diálogo em pt-BR | Teste de vozes (mesmo trecho em cada engine), escuta cega |
| H5 | Converter números/símbolos em código (não no LLM) elimina leitura errada de fórmulas | Lint + escuta de um episódio com fórmulas |
| H6 | Modelo local pequeno (Ollama 1–3B) não escreve diálogo aceitável; o caminho Python precisa do notebook/LLM maior | Rodar o redator com llama3.2 e com o modelo do notebook |

## Espaço de soluções (divergente — não escolhido aqui)

- **Unidade do episódio:** 1 por subpasta · 1 por arquivo `.md` · agrupamento livre pelo planejador guiado pelo `guia_de_estudos.md`.
- **Pontes entre pastas:** só dentro da pasta · RAG (`search_vault`) sobre a raiz do vault · lista manual de pastas relacionadas.
- **Formato do roteiro:** marcadores `[Professor]:`/`[Aprendiz]:` em `.md` · JSON de falas · SSML.
- **Síntese:** fala-a-fala + concatenação · modelo de diálogo nativo (VibeVoice, Dia — pt-BR não confirmado).
- **Onde roda o TTS:** local (`edge-tts`, nuvem Microsoft, sem GPU) · notebook GPU · ambos via mesma interface.
- **Disparo:** `--mode podcast` na CLI · fase opcional do `criar-estudo` · botão na web (estudAI).

## Riscos

| Risco | Impacto | Nota |
|---|---|---|
| pt-BR fraco ou sotaque lusitano nos engines open-source | alto | Por isso o teste de vozes vem antes de fixar engine; `edge-tts` é o plano B |
| Diálogo artificial ("Ótima pergunta!" a cada fala, aprendiz que só concorda) | alto | Regras + exemplo negativo no prompt; lint de bordões |
| Alucinação/contradição com o material escrito | alto | Crítico checa contra os `.md`; fontes por bloco no frontmatter |
| Fórmula/código lidos literalmente ("x elevado a i barra") | médio | Redator verbaliza; código normaliza números; lint de símbolos |
| Episódio estourar o contexto do LLM (material + série + resumos) | médio | Orçamento de contexto por chamada; resumos curtos dos episódios anteriores |
| YouTube/rede bloqueados no Kaggle não afetam aqui (entrada é o vault) | baixo | — |
| Custo de GPU/tempo: 10 episódios × 17 min de síntese | médio | Cache por fala (hash) e retomada |
| Licença: XTTS-v2 é não-comercial | baixo | Uso pessoal de estudo; registrar no DESIGN |
| `edge-tts` depende de serviço não oficial da Microsoft (pode quebrar) | médio | Ser plano B, não o único caminho |
| Índice RAG só existe sob demanda (`specs/concluidas/verificações.md`) | médio | Pontes entre pastas devem degradar com elegância sem índice |

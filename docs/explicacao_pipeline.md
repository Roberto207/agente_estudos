# Explicação do pipeline — material de estudo e podcast

Como o sistema gera o material escrito e, depois dele, os roteiros do podcast.
Estado em 2026-10-11. Spec de referência do podcast: `specs/voz/`.

O sistema funciona em dois momentos. Primeiro gera o **material escrito**. Depois, só quando o usuário pede, gera os **roteiros do podcast** a partir desse material já pronto.

---

## 1. Geração do material de estudo

Existem dois caminhos que produzem a mesma estrutura de pasta.

### Agente Claude `criar-estudo`

É o caminho usado no Claude Code (`~/.claude/agents/criar-estudo.md`).

| Fase | O que faz |
|---|---|
| 1. Preparação | Cria a pasta e as subpastas no vault |
| 2. Extração | Transcreve vídeos e lê artigos, papers e repositórios GitHub para `transcripts/` |
| 3. Planejamento | Decide subpastas e arquivos, ordenados pela cadeia de dependências |
| 4. Pesquisa | Faz buscas complementares na web |
| 5. Escrita | Escreve os `.md` com TL;DR, Resumo e Conteúdo Completo. Antes de escrever, lê as 13 regras de `prompts/regras_didaticas.md` (intuição antes da fórmula, exemplo-fio-condutor, citações, mermaid…) |
| 6. Guia | Escreve o `guia_de_estudos.md` com a ordem de leitura |
| 7. Revisão | Chama o Python para gerar `html/flashcards.html` e `html/quiz.html` |
| 8. Podcast | Opcional, só quando o usuário pede (seção 2) |

### Projeto Python

Usado por `main.py`, pela interface web e pelo notebook do Kaggle/Colab. Faz o mesmo fluxo com o LLM configurado no `config.yaml`.

- O `content.py` lê o mesmo `prompts/regras_didaticas.md`, então as duas versões não divergem.
- Para modelos menores, reenvia quando o JSON vem quebrado (`json_retries`) e reescreve arquivos que saem curtos demais (`content.min_words`).
- O notebook `notebooks/gerar_estudo.ipynb` roda isso com um modelo maior numa GPU gratuita (Ollama na GPU, Groq ou API compatível com OpenAI).

### O que não existe mais

O hub `html/index.html`, as páginas HTML por conceito e o mapa mental foram removidos por desuso. O material é lido no Obsidian. Os únicos HTMLs gerados são:

- `html/quiz.html`: questões e alternativas embaralhadas a cada sessão, grade numerada, campo "ir para questão N";
- `html/flashcards.html`: fila embaralhada, modo "pendentes hoje" (SM-2) ou "todos os cards", grade numerada e "ir para card N".

---

## 2. Geração dos roteiros do podcast

**Princípio:** o LLM só faz o que exige julgamento (planejar, escrever, criticar). O código faz tudo o que precisa ser exato. No caminho do agente Claude, o LLM é o próprio Claude e o código é a CLI `python -m src.podcast.agente`, que não chama LLM nenhum.

```
 criar-estudo (Fase 8)
      │
 8.1  status ─────────────► série existe? está atualizada? quais episódios faltam?
      │
 8.2  planejamento ───────► código monta a lista de arquivos (tamanho, seções, começo)
      │                      e a ordem do guia
      Claude planeja ─────► plano.json (episódios, conceitos, pontes)
      serie ──────────────► código valida e conserta ─► podcast/serie.json
      │
 8.3  para cada episódio, em ordem:
      entradas N ─────────► código monta o pacote de contexto do episódio
      gerar-podcast ──────► escreve o roteiro e roda o lint (corrige 1x se reprovar)
      podcast-critico ────► revisa o roteiro contra o material e grava um JSON
      [se houve problema] ► gerar-podcast reescreve 1x → lint → crítico de novo
      finalizar N ────────► código grava os metadados e o relatório
      │
 8.4  tabela final
```

### 2.1 Planejamento da série (o próprio `criar-estudo`)

O código prepara a entrada: a lista dos `.md` de conteúdo, com tamanho, títulos das seções e o começo de cada um, mais a ordem de leitura do guia. `guia_de_estudos.md`, `proximos_passos.md` e `fontes_selecionadas.md` ficam de fora (D1 do DEFINE).

O Claude, seguindo `prompts/podcast_planejador.md`, decide:

- quantos episódios fazer e quais arquivos entram em cada um (de 1 a 3);
- os **conceitos centrais** de cada episódio (`introduz`, de 1 a 5), que recebem a explicação completa;
- os **conceitos de apoio** (`menciona`, até 8), explicados em uma ou duas frases;
- o que cada episódio **retoma** de episódios anteriores;
- as **pontes** sugeridas.

Depois o código valida e conserta o plano:

- cada arquivo entra em exatamente um episódio;
- os episódios são numerados pela ordem do guia;
- se um episódio "retoma" algo, esse conceito precisa ter aparecido num episódio anterior;
- pontes só apontam para trás (episódios anteriores ou arquivos de episódios anteriores);
- um conceito fica em um grupo só, e um central repetido de episódio anterior vira "retoma";
- os títulos são limpos para poderem ser falados.

Se houver erro, o Claude corrige até 2 vezes; depois disso o código resolve sozinho e registra avisos.

### 2.2 Pacote de contexto do episódio (código)

Para o episódio N, o código monta `podcast/.agente/entradas_NN.md` com cinco blocos, cada um delimitado por tags com um id aleatório. Um texto do material que tente fechar uma tag ou dar ordens não funciona: o código neutraliza as tags forjadas.

| Bloco | Conteúdo |
|---|---|
| `<situacao>` | Número do episódio, se é o primeiro ou o último, se o material é curto, palavras-alvo, conceitos centrais e de apoio, tema do próximo |
| `<material>` | Os `.md` do episódio — a única fonte de fatos |
| `<episodios_anteriores>` | Resumo feito por código (não por LLM) do que os anteriores cobriram: títulos dos blocos e conceitos |
| `<pontes_sugeridas>` | Pontes filtradas: somem as que apontam para o futuro e as "retomadas" de algo que não foi visto |
| `<outras_pastas>` | Trechos de outras pastas do vault, só se `podcast.rag_raiz` estiver configurado e o índice RAG já existir (o sistema nunca cria o índice sozinho) |

O redator e o crítico recebem exatamente o mesmo pacote.

### 2.3 Redator: sub-agente `gerar-podcast`

Roda em contexto limpo, sem o histórico do `criar-estudo`. Lê `prompts/podcast_redator.md` e o pacote de contexto, e escreve o diálogo:

- **Professor**: explica em degraus — intuição cotidiana, depois exemplo concreto, depois definição precisa, depois por que importa. Constrói a intuição antes de definir.
- **Aprendiz**: representa o ouvinte. Pergunta "por quê?" e "e se…?", faz conexões, reformula com um erro plausível e é corrigido. Nunca concorda em mais de duas falas seguidas.
- **Fidelidade**: todo fato técnico vem do material. São permitidas analogias que não carregam afirmação técnica própria e deduções explícitas a partir do mecanismo do material. O que o material não cobre fica de fora; o redator não inventa para encher tempo.
- **Pontes**: com episódios anteriores só quando há base no resumo.
- **Fechamento**: o Aprendiz recapitula e o Professor corrige ou completa; termina com o tema do próximo episódio, ou com a recapitulação da série se for o último.
- **Para o ouvido**: sem markdown, fórmulas ou código. Tudo é descrito em palavras.

Em seguida roda o **lint** (código, não LLM). Ele reprova:

- linhas fora do formato `## título` / `[Professor]:` / `[Aprendiz]:`;
- caracteres que não se falam (símbolos, `loss.backward`, rubricas como "(risos)");
- tamanho fora de 2.000 a 3.200 palavras (o limite inferior não vale para material curto, abaixo de 1.500 palavras);
- citar como já visto um episódio que ainda não aconteceu, ou "episódio anterior" no episódio 1, ou "próximo episódio" no último;
- elogios vazios ("ótima pergunta", "boa dúvida").

Emite apenas aviso quando um episódio N > 1 não menciona nenhum episódio anterior, ou quando o Aprendiz não faz pergunta "por quê" ou "e se". Se o lint reprovar, o redator corrige uma vez.

### 2.4 Crítico: sub-agente `podcast-critico`

É um revisor separado do autor. Recebe os mesmos dados que o redator, lê `prompts/podcast_critico.md` e avalia cinco critérios:

| Critério | O que confere |
|---|---|
| fidelidade | Cada afirmação técnica, inclusive as dentro de analogias, contra o material |
| pontes | Se as pontes têm base; se há promessa de episódio inexistente |
| explicação | Os degraus, só para os conceitos centrais |
| aprendiz | Se faz perguntas e reformulações de verdade, ou só concorda |
| integridade | Falas dirigidas ao "revisor", autoafirmações de correção, conteúdo fora de uma aula |

Ele grava só a lista de problemas. **Quem decide "aprovado" é o código**: aprovado significa zero problemas em todos os critérios.

Se houver problema, o redator reescreve uma vez guiado pelos apontamentos (mudando só o necessário), roda o lint de novo e o crítico revisa outra vez. Se a reescrita quebrar o formato, volta a versão anterior, que já passava no lint. Se o crítico falhar por erro técnico, o roteiro é gravado com `critica: indisponivel` (fail-open) em vez de ser descartado.

### 2.5 Finalização (código)

O `finalizar` grava no frontmatter de cada roteiro:

- versões dos prompts (`v3+<hash>`), modelo e commit do código (`git describe --dirty`);
- número de palavras e duração estimada (150 palavras por minuto);
- resultado do lint e veredito do crítico, com os problemas que sobraram;
- número de reescritas;
- as pontes que de fato aparecem no texto.

Também acrescenta uma linha em `podcast/relatorio.json`. Assim dá para saber depois qual prompt e qual versão do código geraram cada episódio.

### 2.6 O que sai na pasta

```
<pasta>/podcast/
  serie.json                 ← plano da série
  episodio_01_<tema>.md      ← roteiros (o Obsidian lê normalmente)
  ...
  relatorio.json             ← histórico de execuções
  .agente/                   ← arquivos de trabalho (entradas, críticas, backups)
```

### 2.7 O mesmo fluxo no Python

`python main.py --mode podcast --pasta <pasta>` (com `--episodios 2,5` e `--replanejar`) executa o mesmo fluxo com o LLM do `config.yaml` no lugar do Claude. Os dois caminhos usam os mesmos prompts (`prompts/podcast_*.md`) e o mesmo código determinístico. O caminho Python só foi testado com um LLM falso; o caminho do agente Claude foi testado com o agente real.

### 2.8 Situações que o fluxo trata

| Situação | Comportamento |
|---|---|
| Material mudou depois do planejamento | `status` avisa que a série está desatualizada; é preciso replanejar (`--replanejar` arquiva os roteiros antigos em `podcast/arquivo/`) |
| Fluxo interrompido | Nada a limpar: `status` mostra o que falta e os episódios existentes são mantidos |
| Material curto | O episódio fica curto; o redator não inventa conteúdo para chegar ao tamanho |
| Roteiro reprovado no lint duas vezes | Gravado com `lint: reprovado` e `critica: nao_avaliado`; fica fora do estágio de áudio |

---

## 3. O que ainda não existe

O **áudio** (estágio 2 do podcast): ler os roteiros fala por fala, sintetizar cada fala com a voz do papel (Professor ou Aprendiz) e montar o `.mp3`. Planejado em `specs/voz/DESIGN.md` §7:

- `edge-tts` local como plano B;
- engines em GPU (XTTS, Chatterbox, Qwen3-TTS) num notebook Kaggle/Colab;
- vozes fixas por papel, com clonagem opcional apenas nos engines que suportam;
- um teste de vozes que sintetiza o mesmo trecho em cada engine para comparar de ouvido.

---

## 4. Onde está cada coisa

| O quê | Onde |
|---|---|
| Agente que orquestra | `~/.claude/agents/criar-estudo.md` (Fase 8) |
| Sub-agentes | `~/.claude/agents/gerar-podcast.md`, `~/.claude/agents/podcast-critico.md` |
| Prompts (fonte única) | `prompts/podcast_planejador.md`, `podcast_redator.md`, `podcast_critico.md`, `regras_didaticas.md` |
| CLI sem LLM do caminho Claude | `src/podcast/agente.py` |
| Fluxo Python | `src/podcast/run.py` |
| Planejador, redator, crítico | `src/podcast/planner.py`, `writer.py`, `critic.py` |
| Lint, normalização, material | `src/podcast/lint.py`, `normalize.py`, `material.py`, `script_io.py` |
| Testes | `tests/podcast/` (`python -m pytest`) |
| Spec completa | `specs/voz/` (BRAINSTORM, DEFINE, DESIGN, PROMPTS, BUILD_REPORT) |

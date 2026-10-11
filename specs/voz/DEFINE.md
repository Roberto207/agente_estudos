# DEFINE — Podcast de estudo por voz

**Status:** Aprovado em 2026-10-10 · Requisitos em EARS (moldes: Ubíquo / QUANDO…ENTÃO / ENQUANTO / SE…ENTÃO / ONDE).
v1 incorpora a rodada do `sdd-ears-critico` sobre a v0 (ver "Histórico" no fim). Decisões tomadas por
mim para fechar ambiguidades estão marcadas com ⚑ — todas confirmadas pelo usuário no portão de 2026-10-10.

## Escopo

**Dentro:** planejamento da série, roteiros de diálogo (estágio 1), síntese de áudio configurável com
teste de vozes e clonagem opcional (estágio 2), CLI, notebooks Kaggle/Colab e agente `criar-estudo`.
**Fora (v1):** botão na web estudAI, música/vinheta, mais de 2 vozes, feed RSS, outros idiomas.

## Definições (únicas — os requisitos apontam para cá)

- **D1 · `.md` de conteúdo:** todo arquivo `*.md` sob `<p>`, em qualquer nível, exceto os que estão em
  diretórios `transcripts/`, `podcast/`, `html/` ou ocultos (`.*`), e exceto `guia_de_estudos.md`,
  `proximos_passos.md` e `fontes_selecionadas.md` (gerados pelos agentes) em qualquer nível. Em `serie.json` os caminhos são relativos a `<p>`, com `/`.
- **D2 · Ordem do guia:** existindo `<p>/guia_de_estudos.md`, é a ordem da primeira ocorrência de cada
  wikilink `[[nome]]` que resolve (pelo nome do arquivo sem extensão) para um `.md` de conteúdo; os
  demais `.md` de conteúdo vêm depois, em ordem alfabética de caminho. Sem guia, a ordem alfabética de caminho.
- **D3 · Posição de um episódio:** a menor posição (D2) entre seus arquivos-fonte. Episódios são numerados de 1 em diante por essa posição.
- **D4 · `NN` e `slug`:** `NN` = número com 2 dígitos (3 se a série tiver mais de 99 episódios).
  `slug` = título do episódio sem acentos, minúsculo, cada sequência não alfanumérica vira `_`, sem `_`
  nas pontas, cortado em 40 caracteres.
- **D5 · Conceito:** string livre; duas referências são o mesmo conceito quando iguais após `strip()` e `casefold()`.
- **D6 · Fala:** uma única linha iniciada por `[Professor]: ` ou `[Aprendiz]: `. **Palavras de fala** =
  número de tokens separados por espaço depois do rótulo, somados, contados **antes** da normalização de R19.
- **D7 · Caracteres permitidos numa fala:** letras (inclusive acentuadas), dígitos, espaço e
  `. , ; : ! ? - ' " %`, mais as variantes tipográficas da mesma pontuação falada (`“ ” ‘ ’ … – —`).
  Um `.` entre duas letras sem espaço (ex. `loss.backward`) também é proibido.
- **D8 · Menção a episódio:** ocorrência, numa fala, de "episódio" seguido de número em dígitos ou por
  extenso (um a noventa e nove).
- **D9 · Material curto:** episódio cujos arquivos-fonte somam menos de 1.500 palavras.
- **D10 · Engines que clonam:** os que o adaptador declara com `clona = True`; a lista é exposta por
  `src.tts.registry.engines_que_clonam()` ⚑ (hoje: `xtts`, `chatterbox`; `qwen3` a confirmar no B4).
- **D11 · Frontmatter do roteiro (chaves fixas):** `episodio` (int), `titulo`, `fontes` (lista de
  caminhos D1), `pontes` (lista de `{alvo: "episodio:<n>"|"arquivo:<caminho>"|"vault:<caminho>", fala: <trecho>}`),
  `rag_trechos` (lista de caminhos, pode ser vazia), `prompts` (`{planejador, redator, critico}` → `"v<N>+<sha1[:8]>"`),
  `provider`, `modelo`, `gerado_por` (`python`|`claude-agent`), `data` (ISO 8601 com fuso), `palavras` (int),
  `duracao_estimada_s` (int, palavras ÷ 150 × 60), `lint` (`aprovado`|`aviso`|`reprovado`), `lint_codigos` (lista),
  `critica` (`aprovado`|`reprovado`|`indisponivel`|`nao_avaliado`), `critica_problemas` (lista; última rodada), `reescritas` (int).

## Estágio 1 — roteiros

**Disparo e reexecução**
- R1. QUANDO o usuário executar `main.py --mode podcast --pasta <p>` ENTÃO o sistema DEVE gravar `<p>/podcast/episodio_<NN>_<slug>.md` (D4) para cada episódio de `serie.json` que ainda não tenha roteiro, criando `serie.json` antes se ele não existir.
- R2. SE `<p>` não existir ou não tiver nenhum `.md` de conteúdo (D1) ENTÃO o sistema NÃO DEVE chamar o LLM e DEVE sair com código diferente de 0 e mensagem contendo o caminho absoluto de `<p>`.
- R3. ENQUANTO `serie.json` existir, for válido no schema e listar exatamente o conjunto atual de `.md` de conteúdo, o sistema DEVE reutilizá-lo sem chamar o planejador.
- R4. SE `serie.json` existir mas for inválido ou não corresponder ao conjunto atual de `.md` de conteúdo ENTÃO o sistema NÃO DEVE gerar roteiros e DEVE sair com código diferente de 0 listando arquivos novos/removidos e sugerindo `--replanejar`.
- R5. QUANDO `--replanejar` for passado ENTÃO o sistema DEVE mover `serie.json` e os roteiros existentes para `<p>/podcast/arquivo/<data-hora>/` antes de planejar de novo. ⚑
- R6. QUANDO `--episodios <lista>` for passado (inteiros separados por vírgula) ENTÃO o sistema DEVE regenerar apenas esses episódios, sobrescrevendo seus roteiros, e NÃO DEVE alterar nenhum outro arquivo de `<p>/podcast/` além do `relatorio.json`.
- R7. SE `--episodios` contiver número ausente de `serie.json` ENTÃO o sistema NÃO DEVE chamar o LLM e DEVE sair com código diferente de 0 nomeando os números inválidos.

**Planejamento** ⚑ agrupamento livre, guiado pelo guia
- R8. O sistema DEVE numerar os episódios pela posição D3.
- R9. O sistema DEVE listar cada `.md` de conteúdo (D1) como fonte de exatamente um episódio em `serie.json`.
- R10. O sistema DEVE gravar `serie.json` no schema `{titulo_serie, episodios: [{numero, titulo, arquivos, introduz, menciona, retoma: [{conceito, episodio}], pontes: [{alvo, ideia}]}]}`, com no máximo 5 conceitos centrais em `introduz` (o excedente vai para `menciona`, com aviso).
- R11. Para todo item `retoma {conceito: c, episodio: k}` do episódio N, o sistema DEVE garantir `k < N` e `c ∈ introduz(k) ∪ menciona(k)` (D5); SE a resposta do planejador violar isso ENTÃO o sistema DEVE reenviar com o erro e, persistindo, remover o item inválido e registrar o aviso em `relatorio.json`.

**Roteiro — critérios verificáveis por código (lint)**
- R12. O sistema DEVE gravar roteiros contendo apenas: frontmatter YAML no topo (D11), linhas `## <título>`, falas (D6) e linhas em branco.
- R13. O sistema DEVE manter as palavras de fala (D6) de cada roteiro entre 2.000 e 3.200, exceto em material curto (D9), em que o limite inferior não se aplica.
- R14. SE uma fala contiver caractere fora de D7 ENTÃO o lint DEVE reprovar o roteiro.
- R15. O lint DEVE reprovar o roteiro SE: (a) o episódio 1 contiver "episódio anterior/passado" ou "último episódio"; (b) uma fala do episódio N mencionar (D8) episódio de número ≥ N junto de marcador de passado ("vimos", "viu", "falamos", "aprendemos", "lembra"…); (c) houver menção a episódio de número maior que o total; (d) o último episódio contiver "próximo episódio".
- R16. ONDE a série tiver mais de um episódio, o lint DEVE emitir aviso para todo episódio N > 1 sem nenhuma menção (D8) a episódio de número < N.
- R17. SE uma fala contiver elogio do tipo `<ótima|ótimo|excelente|boa|bom|bela|belo|grande|que> <pergunta|dúvida|observação|questão|ponto>` (sem diferenciar maiúsculas) ENTÃO o lint DEVE reprovar o roteiro.
- R18. O lint DEVE emitir aviso quando nenhuma fala do Aprendiz contiver "por que"/"por quê" ou quando nenhuma contiver "e se".
- R19. ONDE o estágio 2 for executado, o sistema DEVE converter, antes da síntese, numerais, `%`, decimais com vírgula e ponto, ordinais e anos para extenso em pt-BR, de forma que a mesma entrada produza sempre a mesma saída (tabela de casos em `tests/podcast/normalize_casos.json`).

**Roteiro — rubrica avaliada pelo crítico LLM** (não verificável por código; o critério de aceite é o crítico emitir o veredito)
- R20. QUANDO um roteiro passar no lint (aprovado ou aviso) ENTÃO o sistema DEVE submetê-lo ao crítico e gravar o veredito por critério: `fidelidade`, `pontes`, `explicacao` (intuição antes da definição para os conceitos de `introduz`), `aprendiz` (por quê, e se, conexão, reformulação corrigida) e `integridade`.

**Reescrita e gravação**
- R21. QUANDO o lint reprovar ENTÃO o sistema DEVE fazer 1 reescrita com a lista de violações e repassar o resultado pelo lint; se reprovar de novo, DEVE gravar a última versão com `lint: reprovado` e `critica: nao_avaliado`.
- R22. QUANDO o crítico reprovar ENTÃO o sistema DEVE fazer 1 reescrita com os apontamentos, repassá-la pelo lint e pelo crítico, e gravar a última versão com o veredito final e os apontamentos da última rodada.
- R23. SE o crítico não devolver JSON válido no schema após 1 reenvio, ou a chamada falhar depois das retentativas do cliente, ENTÃO o sistema DEVE gravar o roteiro com `critica: indisponivel` (fail-open).
- R24. O sistema DEVE gravar no frontmatter todas as chaves de D11 e acrescentar uma linha por episódio em `<p>/podcast/relatorio.json` com número, palavras, `lint`, `lint_codigos`, `critica`, reescritas e duração da geração em segundos.

**Pontes entre pastas**
- R25. ONDE `podcast.rag_raiz` estiver configurado e existir `<rag_raiz>/.rag_index.json`, o sistema DEVE passar ao redator os `podcast.rag_k` trechos de maior similaridade fora de `<p>` e listar seus caminhos em `rag_trechos`.
- R26. SE `podcast.rag_raiz` estiver vazio ou o índice não existir ENTÃO o sistema NÃO DEVE criar nem atualizar índice e DEVE gravar `rag_trechos: []`.

## Estágio 2 — áudio

- R27. QUANDO o usuário executar `main.py --mode podcast-audio --pasta <p>` ENTÃO o sistema DEVE gerar `<p>/podcast/audio/episodio_<NN>_<slug>.mp3` para cada roteiro com `lint` diferente de `reprovado`, aceitando `--episodios` com a mesma semântica de R6/R7.
- R28. SE um roteiro tiver `lint: reprovado` ENTÃO o sistema NÃO DEVE sintetizá-lo e DEVE listá-lo ao final como pulado.
- R29. O sistema DEVE sintetizar cada fala com a voz do seu papel, usando o engine `--engine` quando passado e senão `voz.engine` (padrão `edge`), e as vozes de `voz.engines.<engine>.<papel>`.
- R30. ONDE `voz.clone.<papel>.ref_wav` for um caminho não vazio e o engine estiver em D10, o sistema DEVE usar esse áudio de referência para o papel, no lugar da voz fixa.
- R31. SE `voz.clone.<papel>.ref_wav` for não vazio e o engine não estiver em D10, ou o arquivo não existir, ENTÃO o `podcast-audio` NÃO DEVE sintetizar nada e DEVE sair com código diferente de 0 nomeando o engine e listando D10.
- R32. ENQUANTO existir no cache um arquivo para a chave `sha1(engine | versão do adaptador | voz ou sha1 dos bytes do ref_wav | texto normalizado)`, o sistema DEVE reutilizá-lo em vez de chamar o engine.
- R33. O sistema DEVE gravar cada arquivo de cache de forma atômica (arquivo temporário + renomear), de modo que uma execução interrompida não deixe arquivo parcial com nome de chave válida.
- R34. O sistema DEVE gravar `episodio_<NN>_<slug>.json` ao lado do `.mp3` com: `engine`, `versao_engine`, `vozes` (ou `clone_sha1` por papel), `roteiro_sha1` (sha1 do arquivo de roteiro inteiro), `duracao_s` (real, via ffprobe), `data` (ISO 8601).

**Teste de vozes**
- R35. QUANDO o usuário executar `main.py --mode voice-test [--saida <dir>]` ENTÃO o sistema DEVE sintetizar o trecho fixo `src/tts/trecho_teste.md` (5 falas alternadas, com número, sigla e termo em inglês) em cada engine de `voz.teste.engines` e gravar `<dir>/<engine>.mp3` (padrão `<dir>` = `./teste_vozes/`), sem escrever em nenhuma pasta de estudo.
- R36. ONDE o clone estiver configurado durante o teste de vozes, o sistema DEVE aplicá-lo só aos engines em D10 e usar as vozes fixas nos demais, sem tratar isso como erro.
- R37. SE um engine falhar no teste de vozes (inclusive por dependência ausente ou falta de GPU) ENTÃO o sistema NÃO DEVE interromper os demais e DEVE gravar `<dir>/relatorio.json` com `{engine, ok, erro}` por engine, saindo com código 0 se ao menos um engine funcionou.

## Integração com o agente Claude

- R38. QUANDO o usuário pedir ao `criar-estudo` a fase "Podcast" ENTÃO o agente DEVE produzir os mesmos artefatos de R1, R10 e R12, com o frontmatter D11 (`gerado_por: claude-agent`), e cada roteiro DEVE passar pelo mesmo lint (`python -m src.podcast.lint`) e pelo fluxo de crítica de R20 a R23.

## DEVE / NÃO DEVE (resumo)

| DEVE | NÃO DEVE |
|---|---|
| Gerar roteiro só depois do material escrito existir | Reescrever ou alterar qualquer `.md` de conteúdo |
| Planejar a série antes dos episódios e validar o plano em código | Reutilizar `serie.json` desatualizado em silêncio |
| Reprovar no lint o que não é falável (D7) | Criar/atualizar índice RAG implicitamente |
| Converter números para extenso em código | Sintetizar roteiro reprovado no lint |
| Cachear falas de forma atômica e retomar | Clonar com engine que não clona |
| Registrar versão de prompt, modelo e engine | Descartar roteiro porque o crítico falhou |

## Movido para o DESIGN (requisitos de design disfarçados)

- Prompts como arquivos versionados em `prompts/`, lidos por Python e agentes Claude (era R32) → DESIGN §2 e ADR-002.
- Notebooks de estágio 1 e 2 (era R33) → DESIGN §7; o critério observável é R27/R35 executado dentro do notebook.
- Ordem intuição → exemplo → definição → prática e papel do Aprendiz (eram R14/R15) → rubrica do crítico (R20) e prompt do redator.

## Histórico

- **v1.1 → v1.2** (teste real do caminho Claude): D1 exclui `fontes_selecionadas.md` (curadoria do `buscar-fontes`, não é material); planejador v3 separa conceitos `introduz` (1–5 centrais) de `menciona` (apoio) — R10 ganha `menciona`, R11 aceita `retoma` de conceito em `introduz ∪ menciona`.
- **v1 → v1.1** (durante o build B1 e a rodada 2 de crítica dos prompts; esclarecimentos sem mudar o escopo aprovado):
  - D7 aceita a variante tipográfica da pontuação permitida (o próprio prompt e os modelos usam travessão e reticências);
  - R15 virou heurística verificável: "Bem-vindos ao episódio três" dentro do episódio 3 é legítimo, então só reprova menção com marcador de passado, episódio inexistente e "próximo episódio" no último;
  - R17 cobre as variações de elogio ("boa dúvida", "bela observação") que a rodada 2 mostrou escaparem.

- **v0 → v1** (`sdd-ears-critico`):
  - definições únicas criadas (D1–D11);
  - critérios subjetivos movidos para a rubrica do crítico;
  - requisitos de design movidos para o DESIGN;
  - moldes corrigidos (estado → ENQUANTO/SE);
  - lacunas fechadas: `serie.json` desatualizado (R4), `--replanejar` (R5), episódio inválido (R7), versão gravada após reescritas (R21/R22), cache atômico (R33), conflito clone × teste de vozes (R36), engines que clonam (D10), roteiros excluídos do áudio (R28).

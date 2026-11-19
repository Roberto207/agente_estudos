# G3 · Verificação mais barata, geração e esforço/pensamento (temas B1 e D3)

Pesquisa de 2026-11-07. Base: `00_contexto.md`, `specs/voz/BUILD_REPORT.md`, prompts `podcast_critico.md` (v3) e `podcast_redator.md` (v4), `src/podcast/lint.py`, `src/podcast/critic.py`. Valores em US$ são pesos relativos tirados do BUILD_REPORT (preço de API), não o limite do plano Pro.

## 0. Resposta direta

O crítico Opus não pode ser trocado por Sonnet com o prompt atual: o teste medido deixou passar 3 de 4 erros reais [FATO: F1]. Mas esse teste rodou com esforço padrão, e o prompt só pede "liste os problemas", sem obrigar o modelo a conferir cada afirmação. As duas coisas nunca foram testadas juntas em Sonnet com esforço alto [INFERÊNCIA]. O caminho mais seguro de economia é, nesta ordem:

1. mais lint determinístico (custo zero em tokens);
2. a reconferência depois da reescrita feita só sobre as falas editadas;
3. um A/B de Sonnet em esforço alto com checklist por afirmação, aceito só se acertar 4 de 4 nos gabaritos reais.

Ganho realista do pacote: 10 a 20% do custo por episódio (US$ 0,05 a 0,10 de US$ 0,52), com a conta na seção 4. Não há "grande economia" escondida aqui: o maior custo do crítico é a leitura de entrada (material mais roteiro), e esforço quase não mexe nisso [INFERÊNCIA].

Linha de base usada nas contas (do 00_contexto e do BUILD_REPORT):
- Série de 5 episódios custou ~US$ 2,6, ou US$ 0,52 por episódio [FATO: F1].
- Crítico Opus: 8 execuções, US$ 0,96 só de entrada, 42% do total. Isso dá ~US$ 0,12 por execução de entrada, ou ~US$ 0,136 contando uma saída proporcional [INFERÊNCIA]. São 1,6 execuções por episódio, ou seja, 0,6 reescrita por episódio [FATO: F1].
- Sonnet como crítico: US$ 0,084 contra US$ 0,156 do Opus por execução de entrada, 1,9 vez mais barato [FATO: F1].

## 1. Pergunta 1: verificação mais barata

Gabarito dos 4 erros reais (BUILD_REPORT) e que tipo de verificador pegaria cada um:

| Ep | Erro real | Natureza | Pegaria por regra? | Pegaria por checagem de afirmação? |
|---|---|---|---|---|
| 3 | "Cada sexta era uma aposta nova" (material: deploy trimestral) | frequência/semântica | não (regra frágil) | sim, se a afirmação de frequência for extraída |
| 6 | atribui à cardinalidade o que o material atribui à agregação das métricas | causalidade/atribuição | não | só com modelo bom: é uma comparação de duas frases |
| 7 | "a definição mais citada" (Fowler), sem fonte | superlativo sem fonte | sim: lista de marcadores ("mais citada", "mais conhecida", "clássica", "famosa") | sim |
| 8 | "nome usado no material" | bastidor | sim, já pega o L9 | n/a |

Ou seja, a cobertura determinística hoje é de 1 em 4 (o ep. 8, pelo L9). Com um L10 de superlativo, passa a 2 em 4. Os eps. 3 e 6 exigem leitura semântica [INFERÊNCIA].

### (a) Verificar só as afirmações factuais (estilo FActScore)

- FActScore quebra o texto em fatos atômicos e mede a fração apoiada por uma fonte; o estimador automático usa recuperação e um LLM forte, com menos de 2% de erro contra humanos, e a avaliação humana de 6.500 gerações custaria US$ 26 mil [FATO: F2].
- MiniCheck treina modelos pequenos (o melhor, 770 milhões de parâmetros) para checar cada afirmação contra o documento, e relata nível GPT-4 a custo 400 vezes menor [FATO: F3]. Mas isso exige hospedar um modelo próprio, o que está fora do escopo desta rodada (só Claude Pro). Serve de evidência de que a tarefa "afirmação contra documento" é mais fácil que "julgar o roteiro inteiro" [INFERÊNCIA].
- Aplicação ao projeto: no `critic.py`, o crítico hoje devolve só `problemas`. Um problema que ele não nota vira silêncio, e o prompt não o obriga a olhar cada fato. Obrigar uma lista `afirmacoes` (trecho do roteiro, trecho do material que a sustenta ou "ausente") transforma "não vi problema" em "conferi estas N afirmações" [INFERÊNCIA]. Isso força o modelo a procurar a fonte de cada número, nome, data, frequência e atribuição causal.
- Economia esperada: não está no modelo, está em poder rebaixar o modelo (ver 1.b) sem perder recall. Custo: mais saída (estimo +1,5 a 2 mil tokens por execução) [SUPOSIÇÃO].
- Risco: a extração de afirmações é o ponto fraco. Se o modelo barato não extrair "cada sexta" como afirmação, o erro do ep. 3 passa do mesmo jeito [INFERÊNCIA]. Por isso o teste de regressão exige 4 de 4.

### (b) Cascata (barato triaria, caro só vê os duvidosos)

- RouteLLM mostra corte de custo de mais de 2 vezes "em certos casos" sem perda de qualidade, mas escolhendo o modelo antes da geração, com roteadores treinados com preferência humana [FATO: F4]. Não é uma cascata de verificação e não transfere de forma direta [INFERÊNCIA].
- Evidência local: a triagem barata (Sonnet no esforço padrão) teve recall de 1 em 4 (25%) nos erros reais, sem falso positivo [FATO: F1]. Uma cascata que só escala quando o barato duvida deixaria passar ~75% dos erros que o Opus pegaria. Com esse recall, a cascata "Sonnet primeiro, Opus só se duvidar" não compensa [INFERÊNCIA].
- A cascata que faz sentido é a invertida: o Opus faz a 1ª crítica completa (onde o erro nasce) e um verificador mais barato e restrito confere a reescrita (ver config B/C na seção 4). Os números de economia estão lá.
- Economia: baixa a média (ver conta). Risco: o BUILD_REPORT registra que a 2ª crítica do ep. 2 achou uma contradição que já estava na 1ª versão [FATO: F1]. Restringir a reconferência perde esse tipo de "achado de bônus".

### (c) Ampliar as checagens determinísticas

O lint hoje não confere nenhum fato contra o material; só formato, bastidor, elogio e menção de episódios [FATO: leitura de `lint.py`]. Proposta (custo zero em tokens, não varia, não sofre injeção de prompt, como o próprio docstring do lint diz):

- L10 números: extrair algarismos e numerais por extenso do roteiro (reaproveitar `num2words`, já usado no módulo) e exigir que cada um apareça no material do episódio ou em `episodios_anteriores`; os que não aparecem viram aviso para o crítico, não bloqueio. Pega a classe do Sonnet redator ("2.400 ms" lido como "dois segundos e meio" é uma conversão, então o aviso diz "número sem correspondência exata", e o crítico decide) [INFERÊNCIA].
- L11 superlativo e autoridade sem fonte: "mais citada", "mais conhecida", "famosa", "clássica", "todo mundo", "sempre" perto de nome próprio. Pega o ep. 7 [INFERÊNCIA].
- L12 nomes próprios e siglas: palavra capitalizada que não está no material nem nos episódios anteriores (autor ou ferramenta inventada). Ruído alto em português (início de frase), então só como aviso, depois de filtrar inícios de fala [SUPOSIÇÃO].
- Cobertura honesta: pega o ep. 7 e a classe de erro numérico, não pega os eps. 3 e 6 [INFERÊNCIA]. Serve para filtrar antes de gastar uma crítica e para dar ao crítico uma lista de pontos a conferir (aviso vira entrada do prompt).
- Risco: falso positivo vira reescrita à toa. Por isso, aviso, não bloqueio, e medir a taxa de avisos em episódios limpos.

### (d) Confiabilidade de LLM como juiz por tamanho

- Juízes fortes (GPT-4) chegam a mais de 80% de concordância com humanos, mas têm vieses de posição, verbosidade e autopreferência, e raciocínio limitado [FATO: F5]. O estudo é de preferência entre respostas, não de verificação de fidelidade, e anterior à família de modelos usada aqui [INFERÊNCIA].
- Não achei, nesta sessão, medição publicada de juiz por tamanho para a família Claude 5.5 na tarefa "fidelidade a um texto-fonte". O dado válido é o local: Sonnet 5.5 no padrão, 1 em 4 [FATO: F1]. Haiku 5.5 nunca foi testado; a doc o descreve para classificação, extração e roteamento [FATO: F8], mas isso não é prova para fidelidade de textos longos [INFERÊNCIA].
- O próprio crítico Opus oscila entre execuções (ep. 2 do último teste, e as oscilações que levaram ao L9) [FATO: F1]. Então "Opus = gabarito" tem ruído; o teste de regressão abaixo repete cada caso 3 vezes.

## 2. Pergunta 2: gerar-criticar-reescrever contra checklist/autoverificação

- Evidência geral: sem feedback externo, LLMs têm dificuldade de corrigir o próprio raciocínio, e o desempenho pode cair depois da autocorreção [FATO: F6]. O estudo é sobre raciocínio, não sobre conferir um texto contra uma fonte dada.
- Ponto que muda a leitura aqui [INFERÊNCIA]: conferir fidelidade tem fonte externa (o material no contexto), então é uma verificação "ancorada", mais fácil que autocorreção pura. O que o redator Sonnet e o crítico Sonnet compartilham é o ponto cego: os erros típicos do redator Sonnet (precisão numérica, atribuição sem fonte, Professor confirmando reformulação errada) são exatamente os que o crítico Sonnet deixou passar [FATO: F1 para ambos os testes; a conexão entre eles é INFERÊNCIA]. Autocrítica pelo mesmo modelo tende a herdar o ponto cego.
- Taxa atual: 1,6 execuções por episódio, ou 0,6 reescrita por episódio [FATO: F1]. Na série devops (Opus), o relatório mostra de 0 a 2 reescritas por episódio (somando lint e crítico), a maioria 1 [FATO: `podcast/relatorio.json` do devops]. Primeiras versões do Sonnet têm 2 a 3 problemas contra 1 do Opus [FATO: F1].
- O que isso diz [INFERÊNCIA]:
  - A taxa é alta demais para tirar o crítico externo: perto de metade dos episódios precisa de correção, e os erros que passam são de fidelidade (o mais grave do prompt).
  - Os problemas são poucos e localizados (1 a 3 por episódio), o que favorece reescrita pontual com Edit, já adotada.
  - Um checklist de autoverificação no redator não substitui o crítico, mas pode baixar a taxa de reprovação. Cada reprovação evitada economiza uma reescrita do redator mais uma execução do crítico (~US$ 0,12 a 0,19 [SUPOSIÇÃO para a parte do redator]).
- Quando a autocrítica basta (hipótese a testar, não fato): erros de forma e regra mecânica (formato, bastidor, elogio, tamanho), que o lint já cobre. Quando o crítico externo compensa: fidelidade semântica contra a fonte, onde o autor tem ponto cego.

## 3. Pergunta 3: esforço e pensamento (documentação oficial atual)

Fatos da documentação:
- O `effort` afeta todos os tokens de saída: texto, argumentos de chamadas de ferramenta e pensamento [FATO: F8]. Esforço menor também significa menos chamadas de ferramenta e mais curtas, e juntar operações em menos chamadas [FATO: F8].
- Esforço é um sinal de comportamento, não um orçamento rígido: em esforço baixo o modelo ainda pensa em problemas difíceis, só pensa menos [FATO: F8].
- Níveis no Claude Code para Opus 5.5, Sonnet 5.5 e Haiku 5.5: `low`, `medium`, `high`, `xhigh`, `max`; o padrão desses três é `medium` [FATO: F7]. A página da API diz que o padrão do Sonnet 5.5 na API é `high` [FATO: F8]. Para o Claude Code vale a F7: então o teste do Sonnet crítico "no padrão" provavelmente rodou em `medium` [INFERÊNCIA].
- Pensamento estendido: no Opus 5.5, Sonnet 5.5, Haiku 5.5 e Fable não dá para desligar; `alwaysThinkingEnabled: false` e `MAX_THINKING_TOKENS=0` não têm efeito aí; o raciocínio é adaptativo e o esforço é o controle [FATO: F7, F8]. "Você é cobrado por todos os tokens de pensamento gerados, mesmo recolhidos ou redigidos" [FATO: F7]. Ou seja, o pensamento conta como saída; a página consultada não detalha o peso dentro do limite do plano Pro, só que é cobrado [FATO: F7].
- Esforço por agente: o campo `effort` no frontmatter do subagente vale (`low` a `max`), sobrepõe o esforço da sessão, mas não a variável `CLAUDE_CODE_EFFORT_LEVEL` [FATO: F9]. Subagente sem `effort` próprio, num modelo diferente do da conversa principal, não herda o nível da sessão, então cai no padrão do modelo [FATO: F7, lido como inferência para esse caso].
- `max`: "pode ter retornos decrescentes e tende a pensar demais; teste antes de adotar" [FATO: F7]. `Opus 5.5 em medium iguala ou supera Opus 5 em high` em avaliações de código e trabalho de conhecimento, segundo testes da Anthropic descritos na doc [FATO: F7].
- A doc da API sugere `low` para tarefas simples de custo mínimo (como subagentes) e manda fazer varredura de esforço nas próprias avaliações em vez de herdar a configuração anterior [FATO: F8].
- `maxTurns`: "máximo de turnos agênticos antes de o subagente parar; ao atingir, a saída volta marcada como parcial e o Claude pode retomá-lo" (marcação parcial exige Claude Code v2.1.246 ou superior) [FATO: F9]. Outros campos úteis: `omitClaudeMd: true` pula os CLAUDE.md (v2.1.271 ou superior) [FATO: F9].

Recomendação por papel [INFERÊNCIA, a validar no A/B]:

| Papel | Modelo hoje | Esforço sugerido | Por quê |
|---|---|---|---|
| Orquestrador mecânico (`podcast-serie`) | Sonnet | `low` | só roda comandos e passa blocos; esforço baixo corta preâmbulo e junta chamadas; não há raciocínio de conteúdo |
| Redator de texto longo (`gerar-podcast`) | Sonnet | `medium` (padrão); `low` só na reescrita pontual por Edit | a qualidade vem do prompt (4 versões) e do tamanho da saída (2.200 a 2.700 palavras), e esforço não encurta texto de forma confiável [FATO: F8, sobre Opus 5]; pensar mais ajuda a precisão numérica, o erro típico dele |
| Crítico (`podcast-critico`) | Opus | manter `medium` (padrão) como linha de base; testar Sonnet em `xhigh` com checklist | a tarefa é checar fatos, que se beneficia de pensar; o padrão `medium` do Sonnet foi o que falhou |

Uso de `maxTurns` para cortar laços:
- Orquestrador: 45 chamadas numa série de 5 episódios, ~9 por episódio, com um laço de espera sobrando [FATO: F1]. Sugestão: `maxTurns` de ~60 para 5 episódios, ou ~14 por episódio com a execução por episódio. Se bater o limite, a saída vem como parcial e dá para retomar [FATO: F9]. Servem para acusar um laço, não para economizar no caso normal [INFERÊNCIA].
- Crítico: `maxTurns` ~6 (ler, pensar, gravar JSON; hoje usa Read e Write). Redator: ~8 (Read, Write, Bash lint, 1 a 2 Edit). Os números são SUPOSIÇÃO e devem ficar com margem, porque `maxTurns` curto demais devolve saída parcial e quebra o fluxo.

## 4. Pergunta 4: configurações para o A/B

Todas ligam por um único campo (`modo_economico` em `config` ou variável de ambiente lida pela CLI `agente.py`) que escolhe entre arquivos de agente alternativos (`podcast-critico-eco.md`, `gerar-podcast-eco.md`) e liga os lints novos. Desligar = voltar ao arquivo atual. Nada aqui usa API key.

### Configuração A: crítico Sonnet xhigh com checklist por afirmação, mais L10/L11

- Muda: agente `podcast-critico-eco` com `model: sonnet`, `effort: xhigh`, `maxTurns: 6`; prompt v4 do crítico: antes dos problemas, o JSON tem `afirmacoes` [{fala, fonte_no_material ou "ausente"}] para todo número, nome próprio, data, frequência, superlativo e atribuição causal; avisos do L10/L11 entram como lista de "confira estes pontos". `critic.py` aceita o campo novo (ignora na decisão, aprova só por `problemas`).
- Conta: Sonnet por execução 0,084 contra Opus 0,156 de entrada = 0,54 vezes. Com saída maior (checklist mais pensamento xhigh), suponho 0,65 vez do custo atual por execução. Crítico hoje: US$ 0,136 por execução × 1,6 = US$ 0,22 por episódio. Com A: US$ 0,136 × 0,65 × 1,6 = US$ 0,14. Economia US$ 0,08 por episódio, ~15% de US$ 0,52 (faixa 10 a 17%). A execução extra por reprovação mais frequente pode comer parte: se a taxa de 1,6 subir para 1,8, a economia cai para ~US$ 0,06 [SUPOSIÇÃO].
- Risco: alto. O recall precisa provar 4 de 4. Aceitar só se passar o teste abaixo.

### Configuração B: Opus mantido, reconferência da reescrita só nas falas editadas

- Muda: a 2ª execução do crítico (depois de reescrita) recebe só as falas alteradas (diff do backup), a lista de problemas anteriores e os trechos de material que servem de evidência, em vez de material mais roteiro inteiros; `critic.py` ganha `avaliar_reescrita()`. Mais o L10/L11 como pré-filtro (custo zero). A 1ª crítica fica igual (Opus completo).
- Conta: 0,6 execução por episódio de reconferência × US$ 0,136 = US$ 0,08. Se a entrada cai pela metade (material relevante em vez do inteiro) e o resto fica igual: economia ~US$ 0,04 por episódio, ~8% [SUPOSIÇÃO sobre a fração do material no custo].
- Risco: baixo para a 1ª passada (nada muda); médio para a 2ª: perde os "achados de bônus" como o do ep. 2 [FATO: F1], e uma reescrita pode criar problema em fala que não foi editada (efeito colateral de contexto) [INFERÊNCIA]. Mitigação: L10/L11 rodam sobre o roteiro inteiro depois da reescrita.

### Configuração C: A e B combinadas (Opus na 1ª passada, Sonnet xhigh na reconferência restrita)

- Muda: 1ª crítica em Opus (como hoje); reconferência com o agente `-eco` da config A, em entrada restrita.
- Conta: reconferência hoje US$ 0,08; com Sonnet 0,65 e entrada restrita 0,5: US$ 0,08 × 0,325 = US$ 0,026. Economia US$ 0,055 por episódio, ~11% [SUPOSIÇÃO].
- Risco: médio-baixo, porque a reconferência verifica uma lista de itens conhecidos, o caso mais fácil para o modelo barato [INFERÊNCIA].

### Configuração R (redator econômico): autoverificação no redator, mais L10/L11, mais esforço por papel

- Muda: `gerar-podcast-eco` com checklist final no prompt do redator (antes de gravar, revisar: todo número, nome e atribuição existe no material; nenhum superlativo; nenhum anúncio de fato do próximo episódio; o Professor nunca confirma reformulação errada do Aprendiz), `effort: medium`, e na reescrita por Edit `effort: low`. O L10/L11 roda dentro do lint embutido do redator e devolve avisos que ele corrige antes de entregar.
- Conta: a meta é baixar a taxa de reprovação de ~0,6 para ~0,4 reescrita por episódio. Cada reescrita evitada poupa uma execução do crítico (US$ 0,136) mais uma do redator em modo Edit (~US$ 0,05 [SUPOSIÇÃO]). Economia: 0,2 × 0,186 = US$ 0,037 por episódio; descontando o custo do checklist (+1 a 2 mil tokens de saída, ~US$ 0,005), líquido ~US$ 0,03, ~6% [SUPOSIÇÃO].
- Efeito do orquestrador `low` (separado): orquestrador Sonnet custa US$ 0,70 de entrada em 5 episódios, US$ 0,14 por episódio. Se `low` cortar 15% (SUPOSIÇÃO; a doc só diz "menos chamadas e mais curtas") e `maxTurns` eliminar o laço de espera, economia ~US$ 0,02 por episódio, ~4%.
- Risco: baixo a médio. O checklist pode alongar o roteiro além de 3.000 palavras (L3); medir.

Soma plausível com C mais R mais orquestrador `low`: 0,055 + 0,03 + 0,02 ≈ US$ 0,10 por episódio, ~19% de US$ 0,52 (faixa 10 a 20%) [SUPOSIÇÃO; as parcelas não são totalmente independentes].

### Teste de regressão (gabarito dos 4 erros reais)

Onde estão os roteiros (a versão anterior à reescrita fica em `.agente/backup_NN.md`):
`/home/robertocaetano207/obsidian/devops/01_fundamentos_devops/podcast/.agente/` tem `backup_01` a `backup_09.md`, `entradas_NN.md` (material, pontes e situação enviados ao redator), `critica_NN.anterior.json` e `critica_NN.json`. Os roteiros finais (já corrigidos) estão em `../episodio_NN_*.md`.

Estado de cada caso:

| Ep | Arquivo do erro | Achado |
|---|---|---|
| 7 | `backup_07.md`, linha 66 ("a definição mais citada") | confirmado; o `critica_07.anterior.json` registra o problema do Opus |
| 8 | `backup_08.md`, linha 182 ("o nome usado no material") | confirmado; `critica_08.anterior.json` registra |
| 6 | `backup_06.md`, linhas 268 a 272 (cardinalidade) | trecho provável do erro, mas `critica_06.anterior.json` está sem problemas gravados, então falta confirmar contra o material qual frase é a atribuição trocada |
| 3 | `backup_03.md` | NÃO achei a frase "Cada sexta era uma aposta nova": o backup só tem "o deploy de sexta carregava trinta mudanças acumuladas em três meses" (correto) e `critica_03.anterior.json` está vazio. A versão do erro parece perdida; é preciso reconstruir o caso a partir de uma cópia do backup com a frase reinserida |

Eps. 2 e 5 (limpos): `backup_02.md` e `backup_05.md`, mais `backup_01`, `backup_04` e `backup_09` como controles extras.

Protocolo:
1. Fixar o gabarito: para os eps. 6 e 3, confirmar o erro lendo `entradas_NN.md` (o material) e gravar um arquivo `gabarito.json` com {episodio, fala, motivo}. Corrigir o ep. 3 reinserindo a frase.
2. Com só 4 erros reais, o teste é de ordem de grandeza (recall 4 de 4 não prova 95%). Por isso, adicionar casos semeados: pegar 4 episódios limpos (01, 02, 05, 09) e injetar de 3 a 4 erros cada, dos três tipos reais (número trocado, causa e efeito atribuídos ao conceito errado, superlativo ou autor sem fonte, frequência trocada), somando ≥ 12 casos extras.
3. Rodar cada configuração 3 vezes por caso (o Opus também oscila [FATO: F1]), com o mesmo prompt de entrada que o crítico real recebe (`entradas_NN.md` mais roteiro).
4. Critérios de aceite:
   - recall 4 de 4 nos erros reais em ao menos 2 das 3 repetições, e ≥ 90% nos semeados;
   - 0 falsos positivos em ≥ 5 episódios limpos × 3 repetições (mesmo critério do teste anterior, que teve 0);
   - custo medido por execução (tokens lidos do `.jsonl` do subagente, ressalva do 00_contexto sobre `output_tokens` parcial) ≥ 30% menor que o do Opus atual.
5. Reprovação em qualquer um dos 4 erros reais = a configuração A não entra; B e C só entram se a reconferência restrita acertar 100% dos casos em que a 1ª crítica Opus já apontou o problema e a reescrita o corrigiu (usar `critica_NN.anterior.json` como lista de problemas e `backup`→final como diff).
6. Para o redator (R): gerar de novo os eps. 3, 6 e 7 do devops com `gerar-podcast-eco`, mesmas entradas, crítico Opus atual; comparar problemas na 1ª versão (hoje 3/3/2 no Sonnet padrão, 1/1/1 no Opus [FATO: F1]), reescritas e palavras (≤ 3.000). Meta: média de problemas ≤ 2 e nenhuma regressão na leitura.
7. Métrica final do A/B: tokens e US$ por episódio (peso relativo), execuções do crítico por episódio, taxa de erro real que escapou (conferida por um Opus em passada extra nos episódios finais, ou por amostra de 3 episódios lidos pelo Roberto), e `critica: reprovado` finais.

## 5. Recomendações para o modo econômico

| Recomendação | O que muda | Como ligar/desligar | Ganho estimado | Risco de qualidade | Métrica do A/B |
|---|---|---|---|---|---|
| L10 números e L11 superlativos como avisos | `lint.py` (código novo, testes pytest) | flag `lint_extra` em config; desliga com false | zero tokens; pega o ep. 7 e reduz reescritas (parte dos US$ 0,03 do R) | falso positivo; só aviso | avisos por episódio limpo; erro real pego |
| Reconferência restrita (B) | `critic.py` (`avaliar_reescrita`) e orquestração | `modo_economico.reconferencia: restrita` | ~US$ 0,04 por episódio (8%): 0,6 × US$ 0,136 × 50% | perde achados de bônus; efeito colateral em falas não editadas | recall nos casos de regressão; críticas por episódio |
| Crítico Sonnet xhigh com checklist (A) | novo agente `podcast-critico-eco`, prompt v4 | trocar o agente chamado | ~US$ 0,08 por episódio (15%, faixa 10 a 17%) | alto; só entra com 4 de 4 | recall real e semeado; US$ por execução |
| A+B combinadas (C) | A mais B | os dois flags | ~US$ 0,055 por episódio (11%) mantendo Opus na 1ª | médio-baixo | idem |
| Redator com autoverificação e esforço por papel (R) | `gerar-podcast-eco` (checklist, `effort`) | trocar o agente | ~US$ 0,03 por episódio (6%) | baixo a médio; estouro de tamanho | problemas na 1ª versão; reescritas por episódio |
| Orquestrador `low` e `maxTurns` | frontmatter do `podcast-serie` | campo `effort: low`, `maxTurns: 60` | ~US$ 0,02 por episódio (4%); acusa laço de espera | baixo; `maxTurns` curto devolve parcial | chamadas por episódio; falhas |

Total plausível do pacote C + R + orquestrador: ~10 a 20% do custo por episódio. Parte do ganho em tokens do orquestrador pode ser maior em tokens do que em US$ (69% dos tokens, 31% do custo) [FATO: F1 do 00_contexto]; como o limite do plano Pro conta tokens, vale medir também em tokens.

## 6. Lacunas

- Não achei medição publicada de juiz LLM por tamanho de modelo para fidelidade a documento na família Claude 5.5; o único dado é o do BUILD_REPORT (n = 4).
- O teste "crítico Sonnet" nunca variou esforço nem forçou checklist por afirmação; é a hipótese central, sem teste.
- Não verifiquei FrugalGPT, Self-Refine nem outros trabalhos de cascata e refinamento diretamente (não lidos nesta sessão); não os usei como fato.
- O peso do pensamento dentro do limite do plano Pro não está documentado nas páginas consultadas; a doc só diz que é cobrado.
- A página de configuração de modelo tinha 31 mil caracteres não lidos (depois do auto-compact); pode haver detalhes sobre subagentes.
- O erro do ep. 3 (versão original) parece perdido; o do ep. 6 precisa de confirmação contra o material.
- A fração do custo do crítico que é material (entrada reaproveitável) não foi medida; as contas B e C dependem dela.
- Os valores em US$ do orquestrador e do redator em modo Edit são estimativas.

## 7. Fontes

- F1: `/home/robertocaetano207/dev/agente_estudos/specs/voz/BUILD_REPORT.md` e `specs/economia/00_contexto.md` (leitura local, 2026-11-07).
- F2: Min et al., FActScore, https://arxiv.org/abs/2305.14251 (acessado em 2026-11-07).
- F3: Tang et al., MiniCheck, https://arxiv.org/abs/2404.10774 (acessado em 2026-11-07).
- F4: Ong et al., RouteLLM, https://arxiv.org/abs/2406.18665 (acessado em 2026-11-07).
- F5: Zheng et al., Judging LLM-as-a-judge, https://arxiv.org/abs/2306.05685 (acessado em 2026-11-07).
- F6: Huang et al., Large Language Models Cannot Self-Correct Reasoning Yet, https://arxiv.org/abs/2310.01798 (acessado em 2026-11-07).
- F7: Claude Code, model configuration (esforço e pensamento), https://code.claude.com/docs/en/model-config (acessado em 2026-11-07; 100 mil de 131 mil caracteres lidos).
- F8: Claude API, Effort, https://platform.claude.com/docs/en/build-with-claude/effort (acessado em 2026-11-07).
- F9: Claude Code, subagents (frontmatter `effort`, `maxTurns`, `omitClaudeMd`), https://code.claude.com/docs/en/sub-agents (acessado em 2026-11-07; 100 mil de 116 mil caracteres lidos).
- Arquivos locais lidos: `prompts/podcast_critico.md`, `prompts/podcast_redator.md`, `src/podcast/lint.py`, `src/podcast/critic.py`, `~/.claude/agents/{podcast-critico,gerar-podcast,podcast-serie}.md`, `~/obsidian/devops/01_fundamentos_devops/podcast/.agente/` e `relatorio.json`.

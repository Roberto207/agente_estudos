<!--
Regras dos flashcards. Fonte única, lida pelo Python (src/generators/flashcards.py)
e pelo agente Claude criar-estudo (Fase 7). Mudou aqui, vale nos dois lados.
-->

# Regras dos flashcards

Os flashcards servem para fixar o **fluxo principal** do material e os **conceitos mais importantes**. Não servem para cobrir o material inteiro. Menos cards, bem escolhidos, valem mais que muitos cards de detalhe.

## O que entra

Escolha as perguntas nesta ordem de prioridade, e pare quando atingir o alvo:

1. **Conceito central**: o que é e para que serve, em palavras do dia a dia.
2. **Processo**: para cada processo que o material conta inteiro (o arquivo-dono), a ordem dos passos e o porquê de cada um. Um card por ideia, não um card com a lista toda.
3. **Modelo mental errado**: a leitura plausível porém equivocada e por que ela não se sustenta.
4. **Contraste**: a diferença entre dois conceitos que o leitor tende a confundir.
5. **Status atual**: o que se usa hoje, o que substituiu o quê, e por quê.

Fontes de onde tirar as perguntas: o mapa da pasta (`00_contexto_e_mapa.md`, que traz o fluxo principal), o TL;DR de cada arquivo e o arquivo de conceitos para dominar, se existir. Não percorra o corpo inteiro de cada arquivo atrás de detalhes.

## O que NÃO entra

- Derivar, completar ou decorar fórmula, símbolo ou notação como pergunta ("qual é a Eq. 2?", "o que significa θ?"). A fórmula pode **aparecer** no card, em texto simples (unicode, como `θ_t = θ_(t−1) − α · m̂_t / (√v̂_t + ε)`), mas nunca em LaTeX nem com `$`, e todo símbolo dela ganha um subcard (seção abaixo).
- Cálculo numérico ou "quanto dá X".
- "O que o arquivo/seção/figura/tabela X diz".
- Datas, nomes de pessoas e números soltos sem papel no raciocínio.
- Perguntas de sim ou não.
- Mais de uma ideia por card.
- Resposta que só se entende vendo outro card.

## Como escrever

- **Pergunta**: uma frase, com a palavra de interrogação que cobra raciocínio (por que, como, qual a diferença, o que acontece se). Evite "Defina X".
- **Resposta**: média, de **4 a 7 frases (cerca de 300 a 900 caracteres)**, que se entendem sozinhas. Não basta a resposta seca: inclua (a) a ideia em linguagem do dia a dia, (b) o termo técnico definido, (c) o **porquê**, ou o contexto de onde a ideia vem e para que serve, e (d) quando existir, o **exemplo concreto ou o número** do material (ex.: o MNIST com cerca de 750 direções). Se a resposta cabe em uma frase, falta contexto: acrescente o raciocínio. Uma pergunta sobre um processo ou um objeto técnico (matriz, vetor, algoritmo) diz o que é, quais são as suas dimensões ou entradas e o que ela faz no processo.
- **Contexto na pergunta**: quando o card citar um artigo ou um autor, identifique-o ("Aghajanyan et al. (2020), o artigo que mostra que ajustar um modelo cabe em poucas direções"). O leitor pode ver o card meses depois, sem lembrar de qual trabalho se fala.
- **Fonte**: o arquivo de onde a ideia sai, como `[[nome_do_arquivo]]`.

## Subcards (termos e símbolos)

Cada card traz, abaixo da resposta, a seção `**Termos:**` com um **subcard** por símbolo de equação e por termo técnico que aparece na pergunta ou na resposta. No HTML, cada subcard vira um botão nas laterais do card; clicar abre a explicação do termo. Assim o card fica enxuto, e o significado de cada símbolo está a um clique.

- **Quem entra:** (1) toda letra de símbolo usada no card (θ, α, β₁, m̂_t, g_t, ε, d_int); (2) termo técnico que o leitor pode não lembrar (minibatch, regret, norma espectral). Operadores (√, ×, ≤) pedem só que o card tenha algum subcard.
- **O termo** é o símbolo ou o nome como aparece no card, curto, entre crases. A explicação é de **1 a 3 frases**: o que é, o que representa no processo (dimensão ou valor típico, quando ajuda). Sem analogia do dia a dia.
- **Um subcard por termo**, sem repetir o conteúdo da resposta do card. Se o símbolo tem subscrito que muda de significado (m_t, m̂_t), explique o que o acento ou o índice quer dizer.
- **No arquivo de propostas** todos os subcards nascem com `[ ]`; o leitor marca `[x]` nos que devem virar botão. Só os marcados entram no HTML. O lint recusa o card que usa símbolo sem subcard correspondente.

Formato:

```
- [ ] **P:** Por que o passo do Adam, θ_t = θ_(t−1) − α · m̂_t / (√v̂_t + ε), usa a razão entre as duas médias?
  **R:** ...
  **Fonte:** [[arquivo]]
  **Termos:**
  - [ ] `θ_t`: vetor com todos os parâmetros do modelo depois do passo t.
  - [ ] `α`: taxa de aprendizado, constante; é o passo máximo por parâmetro.
  - [ ] `m̂_t`: média móvel do gradiente com correção de viés; dá a direção.
```

## Quantidade

Alvo de **30 a 50 cards por pasta** (cada um com resposta média, como acima), repartidos pelos conceitos centrais. Nunca concentre muitos cards em um só arquivo. Se o material for pequeno (menos de 5 arquivos), vá para o piso do alvo ou abaixo dele em vez de encher com detalhe.

## Exemplo bom e ruim

Bom (resposta média, com porquê, termo definido e número):

- **P:** Por que o artigo mede a dimensão intrínseca treinando a rede em subespaços aleatórios cada vez maiores, em vez de olhar direto o conjunto de soluções?
- **R:** Porque ninguém conhece o formato do conjunto de soluções de uma rede: ele vive num espaço com uma dimensão por peso, que pode ter centenas de milhares. Então o artigo faz uma medida indireta. Sorteia d direções e deixa o treino andar só nelas, como se fossem alavancas que movem muitos pesos de uma vez. Começa com poucas direções e vai aumentando d até a rede atingir o critério de sucesso. O primeiro d que funciona estima quantas direções realmente precisam ser acertadas, que é a dimensão intrínseca. No MNIST, com uma rede de quase 200 mil pesos, esse d fica perto de 750.

Ruim (curto demais, sem contexto):

- **P:** Por que o artigo usa subespaços aleatórios?
- **R:** Porque não se conhece o formato das soluções.

Ruim (fórmula, e cobra decoreba de símbolo):

- **P:** Qual é a Eq. 2 do artigo e o que significa cada símbolo?
- **R:** θ^(D) = θ₀^(D) + P·θ^(d), em que ...

Ruim (detalhe sem papel no raciocínio):

- **P:** Em que ano o artigo foi publicado?

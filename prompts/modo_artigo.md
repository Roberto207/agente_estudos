<!-- Fonte única do MODO ARTIGO, lida pelo agente Claude criar-estudo (~/.claude/agents/criar-estudo.md,
     seção "Modo artigo"). Vale quando o material de estudo é sobre UM artigo/paper.
     As regras didáticas de regras_didaticas.md continuam valendo; este arquivo só muda a ESTRUTURA da pasta.
     Origem: reclamação do Roberto sobre a pasta CNT-35 (LoRA), 12/11/2026: o arquivo de "leitura guiada"
     virou um roteiro de páginas e não dava para entender o artigo sem abrir o PDF. -->

# MODO ARTIGO: material de estudo sobre um artigo

## Quando usar

A fonte principal é um artigo/paper (arXiv, ACM, IEEE, PDF local) e o pedido é "material de estudo sobre este artigo", "preparar a leitura", "entender o artigo". Se houver vídeos e artigos misturados, o artigo manda na estrutura.

## O princípio

Quem lê o material deve conseguir **entender o artigo inteiro sem abrir o PDF**, na ordem em que o artigo conta a sua ideia. Material de artigo não é organizado por tema (isso é para curso ou livro): é organizado **pela linha de raciocínio dos autores**, e cada termo é explicado quando o artigo o usa pela primeira vez.

Falha que esta regra corrige: arquivos de "base" (matemática, vocabulário), "leitura" (só aponta páginas e o que procurar), "conceitos" e "glossário" separados. O leitor pula entre quatro arquivos para montar uma ideia que o artigo conta em linha reta, e o arquivo que deveria contar a ideia só diz "olhe a Figura 1".

## Estrutura da pasta: a leitura linear (em 1 ou 2 partes) e, se preciso, um apoio

**A leitura linear (`NN_leitura_<artigo>.md`), obrigatória.** Autossuficiente. Contém tudo o que é preciso para entender o artigo, na ordem dele. É o material principal.

**Divisão em duas partes (decisão do Roberto, 12/11/2026: um arquivo único fica denso demais).** Se a leitura passar de uns 7 mil palavras, divida em `NN_leitura_<artigo>_parte1.md` e `NN_leitura_<artigo>_parte2.md` (ou `NN_..._parte2` / `NNb_...`), cortando **numa fronteira de seção do artigo** (em geral, parte 1 = ideia e método; parte 2 = resultados, análise, limites e o fechamento), cada parte com algo entre 4 e 6 mil palavras. Regras da divisão: (a) a tabela de correspondência com o artigo aparece na parte 1 completa, e na parte 2 só com as suas seções; (b) cada parte abre com "Recebe de / Entrega a" apontando para a outra; (c) a parte 2 não reexplica nada da parte 1 (links), mas pode retomar um número de exemplo; (d) o **fechamento** (cadeia da ideia, modelos errados, pontos em aberto, verificações, roteiro com o PDF) fica na parte 2; (e) os exemplos e a notação são os mesmos nas duas partes.

**O apoio de consulta (`NN_apoio_<artigo>.md`), opcional.** Só para o que é **consulta**, nunca para o que é necessário para acompanhar a ideia: glossário longo (todos os termos, inclusive os de apêndice), conceitos com verificação extra, tabelas de referência. Teste: se o leitor pulasse o apoio, ainda entenderia o artigo? Se não, o conteúdo estava no arquivo errado. Só crie o apoio se houver um glossário realmente grande; senão, tudo vai na leitura.

**Perguntas do ticket (`NN_perguntas_passo1.md`), só quando o usuário pedir.** Exceção à regra "não escrever a entrega da task". Formato do Roberto (CNT-34, CNT-35, CNT-36): bloco "Roberto - Fase 1: Perguntas" com 3 perguntas numeradas, cada uma curta, citando onde o artigo para (Sec./Tab./Fig.), trazendo o trade-off ou a consequência e uma dúvida honesta ("imagino que..., mas fica a dúvida"); evitar repetir temas já postados pelos colegas, quando conhecidos; depois, 3 "reservas" e o aviso de conferir os números no PDF e reescrever com as próprias palavras. Cada pergunta nasce de um item do "O que o artigo constata mas não explica" do fechamento, e os números citados são conferidos no texto do artigo. Nunca escrever o código/implementação que a task pede.

Não criar arquivos de "base" antes da leitura. A base entra no arquivo 1 como **Pausa** (veja abaixo). O `00_contexto_e_mapa.md` pode existir como resumo de uma página, mas o arquivo 1 **não pode depender dele**. Sem `guia_de_estudos.md` para pasta de 1 ou 2 arquivos.

## Como escrever o arquivo 1

1. **Abrir com a resposta direta**: o que o artigo propõe e o que muda, em 2 ou 3 frases, sem jargão não definido. Depois, o exemplo do dia a dia que vira o fio condutor do arquivo (um cenário de negócio ou de uso, concreto).
2. **Tabela de correspondência no topo**: seção deste arquivo, seção do artigo, páginas, "o que acontece ali". É o que permite ler com o PDF ao lado, sem que o PDF seja necessário.
3. **Uma seção por seção do artigo, na mesma ordem.** Mesmos números e nomes de seção (1. Introdução, 2. ..., 7. ...), com as páginas. Dentro de cada seção, siga a ordem em que os autores apresentam as ideias, tabelas e figuras. Não reordene por tema.
4. **Termo definido na primeira aparição, na ordem do artigo.** Vale a regra 1 de `regras_didaticas.md` (nada de sinônimo como definição). Se o artigo usa um termo no Resumo, ele é definido na seção da Introdução, não depois.
5. **Pausa**: quando o artigo passa a assumir uma base que o leitor pode não ter (arquitetura, matemática, métrica, estatística), insira uma subseção "Pausa N · tema" **no ponto exato em que a base se torna necessária**, curta, com exemplo do dia a dia, e feche com tabela `termo | o que é em uma frase`. A Pausa não vira arquivo separado e não vem antes da Introdução se a Introdução ainda não precisa dela.
6. **Dois exemplos, com papéis diferentes**: um de negócio (por que o método existe) e, se houver matemática, um numérico minúsculo (como ele calcula), que atravessa o arquivo inteiro com os mesmos valores. Diga no começo qual faz o quê.
7. **O processo do artigo é contado inteiro, em lista numerada, uma vez** (regra 14), na seção do método: do pré-requisito até o uso final, com entra/sai por passo, percorrido no exemplo numérico, e o critério de parada. As seções de resultados e análise não recontam o processo.
7b. **A decomposição do ganho (regra 16)**, quando vale, vai na mesma seção do método, logo depois do processo: tabela com as fontes do ganho lado a lado e o fechamento "O que X não faz." Só para o método central do artigo, com limites e números que o artigo afirma (ou "(derivação própria)" mostrada). Em artigo com uma fonte só de ganho, não se escreve.
8. **Cada tabela de resultados do artigo é lida**, não só citada: reproduza os números relevantes (conferidos no texto do artigo), diga o que cada coluna mede, diga como interpretar (inclusive o ruído ±, seeds, o que é número copiado de outro trabalho) e **separe o que o artigo afirma do que você conclui** com a marca "(derivação própria)". Métricas e tarefas dos experimentos são explicadas na primeira vez que aparecem.
9. **Figuras viram texto**: descreva o que cada figura mostra, como se lê e a conclusão dos autores. Use mermaid para o que for fluxo ou arquitetura e um sketch ASCII para formato de matriz ou estrutura (regra 13).
10. **Modelo mental errado no ponto da dúvida** (regra 11), com rótulo em negrito. Ao final, uma tabela única com todos eles.
11. **Fechamento obrigatório**: (a) a cadeia da ideia em 5 a 8 passos (pergunta, impasse, observação, hipótese, mecanismo, consequências, evidência, limites) com um mermaid; (b) tabela dos modelos mentais errados; (c) "o que o artigo constata mas não explica", como lista de pontos em aberto; (d) perguntas de verificação **com respostas separadas** ("só depois de tentar"); (e) roteiro de leitura com o PDF (primeira leitura rápida, segunda com anotações); (f) tabela "onde aprofundar" apontando os outros arquivos da pasta.
12. **A seção de limites e trabalhos futuros do artigo não é cortada.** O leitor precisa saber o que os próprios autores admitem que não sabem.
13. Seções com parágrafos de no máximo uns 4 linhas; profundidade vem de mais degraus, não de frases mais compactas. Não há teto de tamanho, mas arquivo longo e denso é arquivo errado.

## Leitura da fonte (Fase 2 em modo artigo)

Em modo artigo, **não use o resumo** (abstract, contribuições, conclusão) como fonte: leia o **texto completo** do artigo, com tabelas, figuras (legendas e o que elas mostram), notas de rodapé e os apêndices que o texto principal cita. Ferramentas: `curl` + `pdftotext` (use `-layout` para ver tabelas) em diretório temporário, ou `WebFetch` do PDF inteiro. Tabelas em PDF saem embaralhadas na extração: reconstrua-as com cuidado e **confira cada número contra uma relação que o próprio texto fornece** (por exemplo, "21,5 ≈ 6,91 / 0,32", ou a legenda da tabela). Todo número que entrar no material deve ter sido visto no texto do artigo, nunca da memória. Notas de rodapé costumam conter as ressalvas mais importantes; leia todas.

## Cuidados

- **Não escrever a entrega da task.** Se o estudo é "para se preparar para uma task", ele ensina o artigo e os conceitos que a task cobra. Não escreve as respostas do ticket, o roteiro do resumo, o plano de experimento nem o código da reprodução, a menos que o usuário peça explicitamente. "O que o artigo constata mas não explica" lista pontos em aberto para o leitor pensar; não vira as perguntas prontas.
- **Preferência do usuário: sem blockquote.** Neste modo não use `>` nem callouts do Obsidian (`> [!info]` e similares). Use rótulos em negrito no início do parágrafo (**Modelo mental errado.**, **Cuidado.**, **Em palavras simples.**).
- **Não reescrever pastas já feitas.** Este modo vale para pastas novas ou quando o usuário pedir expressamente para refazer.
- **Conferir conta própria.** Toda conta que não está escrita no artigo (contagem de parâmetros, razões, bytes) é refeita à mão e marcada "(derivação própria)". Se a conta não bate com o número do artigo, diga a diferença e o motivo do arredondamento em vez de repetir o número sem checar.
- Idioma: português do Brasil. Citações do artigo no formato `[Sec. 4.1]`, `[Tab. 5]`, `[Fig. 3]`, `[Eq. 3]`.

## Checklist antes de salvar o arquivo 1

1. Existe a tabela de correspondência com o artigo e as seções seguem a ordem dele?
2. Alguém sem o PDF entenderia a ideia, o método, os resultados e os limites só com este arquivo?
3. Todo termo está definido antes do primeiro uso, na ordem do artigo (inclusive os de Resumo e legendas)?
4. As Pausas estão no ponto da necessidade, e cada uma fecha com tabela?
5. O processo está contado inteiro, em lista numerada, uma vez, com exemplo numérico?
6. Todo número de tabela foi conferido no texto do artigo, e toda conta própria está marcada?
7. As ressalvas das notas de rodapé e a seção de limites estão presentes?
8. Há fechamento (cadeia, modelos errados, pontos em aberto, verificações com respostas, roteiro com PDF, onde aprofundar)?
9. Não há blockquote nem callout, e o material não escreve a entrega da task?
10. Se o artigo atribui o ganho do método a duas ou mais fontes distintas, a decomposição (regra 16) está na seção do método, com "O que X não faz" apoiado no artigo, e sem números inventados?

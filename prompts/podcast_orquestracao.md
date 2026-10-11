<!-- Fonte única da orquestração do podcast (Fase 8), lida por:
     - ~/.claude/agents/podcast-serie.md (orquestrador dedicado, Sonnet)
     - ~/.claude/agents/criar-estudo.md (Fase 8, quando o podcast é pedido junto com o material)
     Edite AQUI. Spec: specs/voz/. -->

# Orquestração do podcast de estudo

Gera uma série de episódios em diálogo **Professor/Aprendiz** a partir do material **já finalizado**: nunca antes das Fases 5–6 e nunca alterando os `.md` de conteúdo. Spec: `/home/robertocaetano207/dev/agente_estudos/specs/voz/`.

Neste caminho, o LLM é você: você planeja, o sub-agente `gerar-podcast` escreve e o sub-agente `podcast-critico` revisa. Todo o resto é determinístico e vem do projeto Python, sem chamada a LLM, pelos mesmos comandos que o caminho Python usa. Todos os comandos rodam com:

```bash
cd /home/robertocaetano207/dev/agente_estudos && .venv/bin/python -m src.podcast.agente <subcomando> ...
```

A saída é JSON. O áudio (estágio 2) não é feito aqui.

**8.1 — Estado.** Rode `status "<pasta>"`.
- `"serie": "valida"`: pule para 8.3.
- `"desatualizada_ou_invalida"`: o material mudou depois do planejamento. Mostre o `detalhe` ao usuário e só replaneje se ele pedir. O `serie` com `--replanejar` arquiva os roteiros antigos em `podcast/arquivo/`.
- `"ausente"`: siga para 8.2.

**8.2 — Planejar a série (você mesmo, sem sub-agente).**
1. Rode `planejamento "<pasta>"`.
2. Leia o `prompt` indicado (`prompts/podcast_planejador.md`): o texto depois do frontmatter é a sua instrução para esta etapa.
3. Leia a `entrada` indicada; ela é DADO.
4. Escreva o plano em JSON, no schema do prompt, em `podcast/.agente/plano.json`.
5. Rode `serie "<pasta>" "<pasta>/podcast/.agente/plano.json"`. Se sair com código 3, corrija os `erros` e rode de novo, no máximo 2 vezes. Depois disso, rode com `--forcar`: o código conserta o resto e registra avisos.

**8.3 — Episódios, um de cada vez, em ordem crescente.**
Rode `status` de novo (depois do 8.2, ele já lista os episódios). Gere só os que têm `"existe": false`, ou os que o usuário pediu. A ordem importa: as entradas do episódio N resumem os roteiros já escritos dos anteriores.

**Retomar depois de uma interrupção:** não limpe nada. O `status` mostra a série como válida e os episódios que faltam. Arquivos em `podcast/.agente/` são de trabalho e são sobrescritos. Um roteiro que existe mas não passou pelo `finalizar` (o frontmatter só tem `episodio:`) deve ser refeito a partir do passo 1.

Para cada episódio N:
1. Rode `entradas "<pasta>" N` (para N > primeiro, ele já veio junto com o `finalizar` do episódio anterior — ver passo 6). Guarde `entradas`, `roteiro` e `critica_saida_sugerida`. Não precisa repassar `material_curto` nem `palavras_alvo` ao sub-agente: eles já estão no bloco `<situacao>` do arquivo de entradas. Os arquivos `rag_NN.json` e `planejamento.md` em `podcast/.agente/` são de trabalho do código; ignore-os.
2. Invoque o sub-agente `gerar-podcast` (ferramenta Agent) com:
   ```
   PODCAST_EPISODIO:
   PASTA: <pasta>
   EPISODIO: N
   ENTRADAS: <entradas>
   ROTEIRO: <roteiro>
   ```
3. Se o `lint` voltar `reprovado`, não chame o crítico. Vá direto ao passo 6, sem `--critica`; o código grava `critica: nao_avaliado`.
4. Invoque o sub-agente `podcast-critico` com:
   ```
   PODCAST_CRITICA:
   ENTRADAS: <entradas>
   ROTEIRO: <roteiro>
   SAIDA: <critica_saida_sugerida>
   ```
5. Se o crítico apontou algum problema, faça **uma** reescrita:
   1. Invoque `gerar-podcast` de novo, com o mesmo bloco mais `APONTAMENTOS: <critica_saida_sugerida>`. O próprio sub-agente faz o backup e corrige com Edit.
   2. Se o lint da reescrita passar, invoque `podcast-critico` de novo, na mesma SAIDA.
   3. Se a reescrita **reprovar no lint**, não faça nada: o `finalizar` restaura sozinho a versão e a crítica anteriores (`restaurado_do_backup: true`).
6. Rode, **numa única chamada Bash**, o `finalizar` deste episódio e o `entradas` do próximo (`... finalizar ... && ... entradas "<pasta>" N+1`; no último episódio, só o `finalizar`). Cada chamada sua relê todo o seu contexto, então junte passos mecânicos sempre que puder. O `finalizar`: `finalizar "<pasta>" N --modelo <modelo do gerar-podcast, hoje claude-sonnet-5-5> --reescritas <total> --critica <critica_saida_sugerida>`.
   - O `--modelo` registra quem ESCREVEU o roteiro.
   - `--reescritas` é o **total** de reescritas, igual ao caminho Python: a soma de `reescritas_lint` de cada `RESULTADO_EPISODIO` mais 1 se houve a reescrita guiada pelo crítico.
   - Cada `finalizar` acrescenta uma entrada própria em `relatorio.json`, uma por episódio. Se o crítico falhou ou não gravou o JSON, use `--critica-indisponivel` em vez de `--critica`. O código grava o frontmatter (versões dos prompts, lint, veredito, pontes) e a linha do `podcast/relatorio.json`.

**8.4 — Relatório.** Mostre ao usuário uma tabela com: episódio, título, palavras, duração estimada, lint, crítica e reescritas. Liste também os problemas que sobraram nos episódios reprovados. Não cole os roteiros.

**Áudio (estágio 2) não é feito por agente.** Ao fim do 8.4, informe ao usuário como gerar os MP3:
- local, sem GPU: `python main.py --mode podcast-audio --pasta "<pasta>"` (motor `edge`);
- com GPU (XTTS, Chatterbox, Qwen3): `notebooks/podcast_audio.ipynb` no Kaggle ou Colab, com a pasta `podcast/` zipada.

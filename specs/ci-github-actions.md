# Spec: CI com GitHub Actions no agente_estudos

Status: RASCUNHO para aprovação (2026-11-05). Nível de rigor: spec leve (um workflow, sem mudança de comportamento do produto).
Origem: nota `obsidian/carreira/2026-11-05_agentico-medicao-e-foco.md`.

## 1. Por que isso existe

O repositório tem testes, mas nada os roda sozinho. Hoje a confiança em "está funcionando" depende de eu lembrar de rodar `pytest`. Além disso, os números abaixo mostram que o problema não é só automatizar: a cobertura é desigual.

Fatos verificados em 2026-11-05 (não estimados):

| Fato | Valor | Como foi medido |
|---|---|---|
| Testes na suíte | 77, todos passando | `pytest -q` no `.venv` e em clone limpo |
| Tempo da suíte | cerca de 7 s | mesmo comando, duas vezes |
| Onde ficam os testes | só `tests/podcast/` (7 arquivos `test_*.py`) | `find tests -name "test_*.py"` |
| Módulos Python em `src/` e `web/` | 56 | `find ... -name "*.py"` |
| Módulos do núcleo sem teste algum | `agent.py`, `pipeline.py`, `indexer.py`, `chat.py`, `llm.py`, `distiller.py`, `tools/`, `web/` | ausência em `tests/` |
| Clone limpo sem `config.yaml` e sem `.venv` | 77 passed, sem chave de API | clone em pasta temporária + venv novo + `pip install -r requirements.txt` |
| Teste com dependência externa de binário | `tests/podcast/test_tts.py` pula tudo se não houver `ffmpeg` | `pytestmark = skipif(...)` |
| CI existente neste repo | nenhum | `.github/` não existe |
| Remote | `github.com/Roberto207/agente_estudos`, branch `main` | `git remote -v` |

Consequência: um CI verde aqui diria "o podcast está ok", não "o agente_estudos está ok". O workflow precisa deixar essa diferença visível, e não escondê-la.

## 2. Objetivo

Toda alteração enviada ao GitHub passa pela suíte de testes automaticamente, e o resultado aparece no commit ou no pull request. O CI também torna visível o que a suíte não cobre.

## 3. Escopo

Dentro (Fase 1, implementar agora):
- Um workflow `.github/workflows/tests.yml` que roda `pytest`.
- Um selo de status no `README.md`.

Dentro (Fase 2, depois que a Fase 1 estiver verde):
- Relatório de cobertura por módulo com `pytest-cov`, apenas informativo. Sem limite mínimo no começo.

Fora desta spec:
- Deploy (o estudAI roda no Termux, ver `specs/deploy.md`).
- Docker, lint e type check (não há configuração de ruff ou mypy no repositório; decidir em spec própria).
- Gate de avaliação de qualidade do agente (evals). Isso depende do `rag_eval_harness` do Bloco 4 do NLP e terá spec própria. O ponto de encaixe está em 7.
- Escrever os testes do núcleo. Isso é a Fase 3, listada em 8 como trabalho separado.

## 4. Decisões já tomadas

| Decisão | Escolha | Por quê |
|---|---|---|
| Python | 3.13 | É a versão local (3.13.3) em que os 77 testes passaram |
| Gatilhos | `push` na `main` e `pull_request` | Cobre o fluxo atual (commit direto na main) e o futuro |
| Permissões | `contents: read` | O job só lê o código; é o mínimo |
| Segredos | nenhum | A suíte passou em clone limpo sem `config.yaml` nem chave. Usar segredo aqui seria um risco sem ganho |
| Tempo máximo | 10 minutos | A suíte leva 7 s; o limite só evita um travamento queimar horas |
| Concorrência | cancelar execução antiga da mesma branch | Evita fila de runs obsoletas |
| Cache | cache de `pip` via `actions/setup-python` | Reduz a instalação de dependências |
| Versão das actions | tag maior fixa (por exemplo `@v4`, `@v5`), nunca `latest` ou branch | O workflow do TJGO já fixa versão pelo mesmo motivo |

## 5. Requisitos (formato EARS, cada um testável)

R1. QUANDO um commit for enviado à branch `main`, o workflow DEVE executar a suíte completa de testes.
R2. QUANDO um pull request for aberto ou atualizado, o workflow DEVE executar a suíte completa de testes.
R3. O workflow DEVE instalar as dependências a partir de `requirements.txt` e do `pytest`, sem usar `config.yaml`, `.env` nem qualquer segredo.
R4. SE algum teste falhar, ENTÃO o job DEVE terminar com status de falha.
R5. SE algum teste for pulado (`skipped`), ENTÃO o job DEVE terminar com status de falha. Motivo: teste pulado em silêncio dá falsa confiança, e hoje o `test_tts.py` pula tudo sem `ffmpeg`.
R6. O workflow DEVE garantir que o `ffmpeg` esteja disponível antes de rodar os testes, instalando-o se estiver ausente.
R7. SE o job passar de 10 minutos, ENTÃO ele DEVE ser cancelado.
R8. QUANDO duas execuções da mesma branch se sobrepuserem, o workflow DEVE cancelar a mais antiga.
R9. O workflow DEVE declarar `permissions: contents: read` e nenhuma outra.
R10. O `README.md` DEVE exibir o selo de status do workflow.

Fase 2:
R11. QUANDO a suíte terminar, o workflow DEVERIA publicar no resumo do job a cobertura por módulo, sem falhar o job por cobertura baixa.

## 6. Como saber que o próprio CI funciona

Um CI que nunca ficou vermelho não foi testado. A verificação é parte da entrega, não opcional:

| Teste do CI | Procedimento | Resultado esperado |
|---|---|---|
| Caminho feliz | Enviar a Fase 1 numa branch e abrir PR | Job verde com 77 testes |
| Falha detectada | Num PR descartável, quebrar um teste de propósito (por exemplo inverter uma asserção em `test_lint.py`) | Job vermelho, e o PR mostra qual teste falhou |
| Pulo detectado (R5) | Num PR descartável, remover a instalação do `ffmpeg` | Job vermelho por testes pulados |
| Isolamento (R3) | Conferir no log que nenhuma variável de segredo é usada | Nenhum `secrets.*` no arquivo do workflow |

Registrar o resultado das quatro linhas em `specs/ci-github-actions-REPORT.md` quando for implementado.

## 7. Ponto de encaixe para a avaliação de qualidade (spec futura)

Quando o `rag_eval_harness` existir, ele entra como um segundo job (`eval`) neste mesmo workflow ou em outro arquivo, com gatilho manual (`workflow_dispatch`) e em mudanças de `src/` ou `prompts/`. Ele falha o merge se uma métrica cair abaixo de um limite fixado a partir de uma execução de referência. Esse limite precisa nascer de medição (várias execuções, com variação conhecida), não de um número escolhido a olho. Isso fica para a spec do Bloco 4.

## 8. Trabalho relacionado que não cabe nesta spec

Fase 3, separada: criar os primeiros testes do núcleo (`pipeline.py`, `indexer.py`, `agent.py` com o provedor de LLM substituído por um falso), começando pelo caminho mais usado. Sem isso o selo verde do README exagera a cobertura. Critério de saída da Fase 3: cada módulo do núcleo tem ao menos um teste de caminho principal e um de falha.

## 9. Riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Teste passa local e falha no runner por diferença de ambiente | Baixa (clone limpo já passou) | Verificação do item 6, linha 1 |
| O runner não traz `ffmpeg` e o R5 derruba o job | Média (não verificado) | R6 instala o `ffmpeg` |
| Selo verde interpretado como "projeto testado" | Alta | Seção 1 e Fase 3 deixam a lacuna escrita; README pode dizer "testes do módulo podcast" ao lado do selo |
| Mudança futura em `requirements.txt` quebrando a instalação | Média | O CI é justamente o detector; ele avisa no PR |

## 10. Perguntas abertas para o Roberto

1. Python só na 3.13, ou também na 3.12 para pegar incompatibilidade? Recomendação: só 3.13 por enquanto.
2. Ativar proteção da branch `main` (exigir CI verde antes de merge)? Isso é configuração no GitHub e é decisão sua; hoje você commita direto na `main`.
3. Aprova começar pela Fase 1 e adiar cobertura (Fase 2) até o selo estar verde?

## 11. Fora de alcance de quem implementa

Não fazer commit nem push sem pedido explícito. Sugerir a mensagem de commit e mostrar o resultado dos testes antes.

"""Escreve os arquivos .md de conteúdo usando o LLM."""
from __future__ import annotations
import os
from pathlib import Path

from ..llm import LLMClient


_SYSTEM_WRITER = """Você é um especialista em criar materiais de estudo de altíssima qualidade em português brasileiro. Seu padrão de referência são apostilas universitárias e livros técnicos — não artigos de blog.

Escreva um arquivo .md para um vault Obsidian seguindo EXATAMENTE esta estrutura e os requisitos de profundidade abaixo:

---

# Título do Conceito

> Blockquote de uma linha explicando o que este arquivo cobre.

---

## TL;DR
[MÍNIMO 3 parágrafos densos. Cubra: (1) o que é e por que existe, (2) como funciona em alto nível com a intuição central, (3) quando usar e o que diz a literatura. Deve ter entre 200 e 300 palavras. NÃO use listas aqui — use prosa densa.]

---

## Resumo (5 min)
[Mínimo 8 bullet points substantivos, cada um com 2-4 linhas de explicação real — não títulos de seção. Inclua pelo menos uma fórmula ou equação relevante, e pelo menos um exemplo concreto com números ou código de 3-5 linhas. Entre 350 e 500 palavras.]

---

## Conteúdo Completo

### [Seção 1: Fundação teórica]
[Mínimo 300 palavras. Definição formal, intuição matemática quando aplicável, histórico ou motivação. Pelo menos uma fórmula em bloco ou equação relevante.]

### [Seção 2: Algoritmos / Variantes / Como funciona internamente]
[Mínimo 400 palavras. Cubra TODAS as variantes ou etapas relevantes do conceito, não apenas uma. Inclua pelo menos um bloco de código real e funcional (não pseudocódigo esqueleto) com comentários explicativos em cada linha relevante. Se houver múltiplos algoritmos (ex: L1 vs L2, SGD vs Adam), compare-os em tabela e explique cada um em pelo menos 2 parágrafos.]

### [Seção 3: Intuição visual / Exemplos numéricos / Casos práticos]
[Mínimo 300 palavras. Trace um exemplo passo a passo com números concretos, ou descreva o comportamento visual de gráficos/curvas. Conecte a teoria ao comportamento observável.]

### [Seção 4: Trade-offs, erros comuns e quando NÃO usar]
[Mínimo 200 palavras. O que pode dar errado, quais os hiperparâmetros críticos, como diagnosticar problemas, comparação com alternativas.]

---

- Voltar: [[arquivo_anterior]]
- Próximo: [[arquivo_seguinte]]
- Ver também: [[arquivo_relacionado]]

---

## REQUISITOS OBRIGATÓRIOS DE QUALIDADE

**Comprimento mínimo total**: 1400 palavras. Arquivos curtos são REJEITADOS.

**Por seção do Conteúdo Completo**:
- Cada `###` deve ter no mínimo 200 palavras
- Nenhuma subseção pode ter apenas 1 parágrafo e um código
- Código deve ser real e funcional, não esqueleto conceitual de 5 linhas
- Fórmulas matemáticas devem vir com explicação de cada variável

**PROIBIDO** (causas automáticas de reescrita):
- Seções com apenas 1 parágrafo e um bloco de código
- Pseudocódigo genérico como único exemplo (`for x in data: loss = loss(pred, y)`)
- Bullet points que são apenas títulos sem explicação ("Classificação: saída discreta")
- Omitir variantes/algoritmos que fazem parte do tema (ex: falar só de L2 num arquivo sobre regularização)
- TL;DR com menos de 150 palavras
- Tabelas com apenas 2 colunas e 3 linhas quando o tema tem 5+ variantes a comparar

**ADAPTE à didática solicitada**:
- Formal/matemático = definições precisas, fórmulas com prova ou derivação parcial, notação consistente
- Prático/código = exemplos funcionais com scikit-learn/PyTorch/HuggingFace, saídas esperadas comentadas
- "Exemplos do mundo real" = analogia concreta antes de cada conceito abstrato, casos de uso reais nomeados

**Links Obsidian**: `[[nome_do_arquivo]]` sem extensão. Não repita conteúdo de outros arquivos — referencie-os.
Os três níveis (TL;DR, Resumo, Conteúdo Completo) devem ser autossuficientes: alguém lendo só o Conteúdo Completo não deve precisar dos outros.
"""


def plan_structure(
    llm: LLMClient,
    tema: str,
    foco: str,
    didatica: str,
    transcripts_content: str,
) -> dict:
    """
    Pede ao LLM para planejar a estrutura de subpastas e arquivos.
    Retorna dict: {subfolders: [{name, label, files: [{name, title, description}]}]}
    """
    prompt = f"""Com base no tema, foco e conteúdo abaixo, planeje a estrutura de pasta de estudos.

**Tema**: {tema}
**Foco**: {foco}
**Didática**: {didatica or 'didática clara com exemplos práticos'}

**Conteúdo das fontes** (resumo):
{transcripts_content[:8000]}

Responda com um JSON válido neste formato exato:
{{
  "subfolders": [
    {{
      "name": "fundamentos",
      "label": "Fundamentos",
      "files": [
        {{"name": "introducao", "title": "Introdução ao Tema", "description": "O que é, contexto histórico e aplicações"}},
        {{"name": "conceitos_basicos", "title": "Conceitos Básicos", "description": "Terminologia e definições essenciais"}}
      ]
    }},
    {{
      "name": "avancado",
      "label": "Avançado",
      "files": [
        {{"name": "tecnicas_avancadas", "title": "Técnicas Avançadas", "description": "Métodos e algoritmos aprofundados"}}
      ]
    }}
  ]
}}

Crie entre 2 e 4 subpastas com 2 a 5 arquivos cada. Nomes de arquivos em snake_case sem acentos."""

    return llm.chat_json(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )


def research_topics(
    llm: LLMClient,
    tema: str,
    foco: str,
    structure: dict,
    search_fn,
    max_results: int = 5,
) -> str:
    """Pesquisa complementar por tópico via web search."""
    topics = foco.split(",") if foco else [tema]
    topics = [t.strip() for t in topics[:5]]

    snippets = []
    for topic in topics:
        results = search_fn(f"{topic} {tema} explicação didática", max_results=max_results)
        if results:
            snippets.append(f"\n### Pesquisa: {topic}\n")
            snippets.extend(
                f"- **{r['title']}** ({r['url']}): {r['snippet']}"
                for r in results
                if r.get("title")
            )

    return "\n".join(snippets)


def write_content_files(
    llm: LLMClient,
    pasta: str,
    tema: str,
    foco: str,
    didatica: str,
    structure: dict,
    transcripts_content: str,
    research_content: str,
    progress_cb=None,
) -> list[str]:
    """
    Escreve todos os arquivos .md de conteúdo.
    progress_cb(current, total, title) é chamado a cada arquivo gerado.
    """
    all_files = [
        (sf["name"], f)
        for sf in structure.get("subfolders", [])
        for f in sf.get("files", [])
    ]
    total = len(all_files)
    written = []

    # Mapa de vizinhos para navegação
    nav_map = _build_nav_map(structure)

    for i, (sf_name, f) in enumerate(all_files):
        title = f.get("title", f["name"])
        if progress_cb:
            progress_cb(i + 1, total, title)

        sf_path = os.path.join(pasta, sf_name)
        Path(sf_path).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(sf_path, f"{f['name']}.md")

        prev_link, next_link = nav_map.get(f["name"], ("", ""))
        content = _write_file(
            llm=llm,
            tema=tema,
            foco=foco,
            didatica=didatica,
            file_info=f,
            subfolder=sf_name,
            transcripts=transcripts_content,
            research=research_content,
            all_files=all_files,
            prev_link=prev_link,
            next_link=next_link,
        )
        Path(out_path).write_text(content, encoding="utf-8")
        written.append(out_path)

    return written


def write_guia(
    llm: LLMClient,
    pasta: str,
    tema: str,
    foco: str,
    structure: dict,
) -> str:
    """Gera o guia_de_estudos.md."""
    file_list = "\n".join(
        f"- [[{f['name']}]] — {f.get('description', f.get('title', ''))}"
        for sf in structure.get("subfolders", [])
        for f in sf.get("files", [])
    )

    slug = tema.lower().replace(" ", "_")
    canvas_refs = (
        f"| [[1_{slug}_fundamentos.canvas]] | Visualizar conceitos base |\n"
        f"| [[2_{slug}_avancado.canvas]] | Visualizar conexões avançadas |"
    )

    prompt = f"""Crie um guia_de_estudos.md para o tema "{tema}" seguindo este modelo:

# Guia de Estudos — {tema} (Ordem de Leitura Recomendada)

> Use este guia para navegar pela pasta de forma progressiva.

---

## Fase 1 — <Subtema Inicial>
1. **[[arquivo_1]]** — descrição
2. **[[arquivo_2]]** — descrição

**Checkpoint**: pergunta de verificação de aprendizado

---

## Fase N — ...

## Canvas de Referência

| Canvas | Quando abrir |
|---|---|
{canvas_refs}

---
Arquivos disponíveis:
{file_list}

Foco do tema: {foco}
Organize os arquivos em fases progressivas de aprendizado. Cada checkpoint deve ser uma pergunta que verifica se o estudante entendeu a fase."""

    content = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    out_path = os.path.join(pasta, "guia_de_estudos.md")
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path


# ── Internos ──────────────────────────────────────────────────────────────────

def _write_file(
    llm: LLMClient,
    tema: str,
    foco: str,
    didatica: str,
    file_info: dict,
    subfolder: str,
    transcripts: str,
    research: str,
    all_files: list,
    prev_link: str,
    next_link: str,
) -> str:
    related = [
        f["name"] for _, f in all_files
        if f["name"] != file_info["name"]
    ][:3]

    nav_footer = "---\n"
    if prev_link:
        nav_footer += f"- Voltar: [[{prev_link}]]\n"
    if next_link:
        nav_footer += f"- Próximo: [[{next_link}]]\n"
    if related:
        nav_footer += f"- Ver também: " + ", ".join(f"[[{r}]]" for r in related) + "\n"

    related_titles = [
        f.get("title", f["name"]) for _, f in all_files
        if f["name"] != file_info["name"]
    ][:4]

    prompt = f"""Escreva o arquivo de estudo: **{file_info['title']}**

**Tema geral**: {tema}
**Foco do tema**: {foco}
**Didática solicitada**: {didatica or 'didática clara, prática, com exemplos de código funcional e fórmulas explicadas'}
**Subpasta**: {subfolder}
**Descrição deste arquivo**: {file_info.get('description', '')}
**Outros arquivos na pasta** (referencie-os com [[nome]] mas não repita o conteúdo deles): {', '.join(related_titles)}

**Material de referência das fontes** (use para embasar o conteúdo com autoridade):
{transcripts[:8000]}

**Pesquisa complementar**:
{research[:4000]}

**Navegação (adicione EXATAMENTE ao final do arquivo)**:
{nav_footer}

---

ATENÇÃO: Este arquivo deve ter MÍNIMO 1400 palavras no total.
Cada subseção do "Conteúdo Completo" deve ter no mínimo 200 palavras.
Inclua código Python funcional real (não pseudocódigo) quando o tema envolver algoritmos ou implementação.
Cubra TODAS as variantes/algoritmos relevantes do tema — não apenas o caso mais simples.
Se omitir algum algoritmo importante do tema, o arquivo será rejeitado e reescrito."""

    return llm.chat(
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM_WRITER,
        max_tokens=8192,
    )


def _build_nav_map(structure: dict) -> dict[str, tuple[str, str]]:
    """Retorna mapa de nome_arquivo -> (anterior, próximo)."""
    flat = [f["name"] for sf in structure.get("subfolders", []) for f in sf.get("files", [])]
    result = {}
    for i, name in enumerate(flat):
        prev = flat[i - 1] if i > 0 else ""
        nxt = flat[i + 1] if i < len(flat) - 1 else ""
        result[name] = (prev, nxt)
    return result

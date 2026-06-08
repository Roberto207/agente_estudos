"""Escreve os arquivos .md de conteúdo usando o LLM."""
from __future__ import annotations
import os
from pathlib import Path

from ..llm import LLMClient


_SYSTEM_WRITER = """Você é um especialista em criar materiais de estudo de alta qualidade em português brasileiro.

Escreva um arquivo .md para um vault Obsidian seguindo EXATAMENTE esta estrutura:

# Título do Conceito

> Blockquote de uma linha explicando o que este arquivo cobre.

---

## Seção Principal
Conteúdo profundo e didático. Inclua:
- Exemplos práticos (com blocos de código quando aplicável)
- Tabelas para comparações quando relevante
- Imagens referenciadas como: ![descrição](url)

---

## Seção Seguinte
...

---

- Voltar: [[arquivo_anterior]]
- Próximo: [[arquivo_seguinte]]
- Ver também: [[arquivo_relacionado]]

REGRAS:
- Adapte profundidade e linguagem à didática solicitada
- Formal = rigor e definições precisas
- Prático = exemplos e código em primeiro lugar
- "Exemplos do mundo real" = analogias antes da teoria
- Links Obsidian [[nome]] sem extensão .md
- Não repita o que já está em outros arquivos — cada arquivo tem foco único
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

    prompt = f"""Escreva o arquivo de estudo: **{file_info['title']}**

**Tema geral**: {tema}
**Foco do tema**: {foco}
**Didática solicitada**: {didatica or 'didática clara, prática, com exemplos'}
**Subpasta**: {subfolder}
**Descrição deste arquivo**: {file_info.get('description', '')}

**Material de referência das fontes** (use para embasar o conteúdo):
{transcripts[:6000]}

**Pesquisa complementar**:
{research[:3000]}

**Navegação (adicione ao final do arquivo)**:
{nav_footer}

Escreva o arquivo .md completo com profundidade real. Mínimo 400 palavras. Inclua exemplos, código quando relevante e tabelas quando ajudar na compreensão."""

    return llm.chat(
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM_WRITER,
        max_tokens=4096,
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

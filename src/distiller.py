"""
Distiller: replica a lógica do agente ai-lecture-distiller.
Classifica cada fonte e gera um arquivo de transcrição/resumo estruturado.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

import requests

from .llm import LLMClient
from .tools.web import fetch_url, web_search

_GITHUB_HEADERS = {"User-Agent": "agente-estudos/1.0"}
from .tools.video import get_video_info, get_youtube_transcript, transcribe_local_video


_SYSTEM = """Você é um especialista em análise de conteúdo educacional.
Dado o conteúdo bruto de uma fonte, produza um resumo estruturado rico em português brasileiro.

Use EXATAMENTE este formato:

# [Título da Fonte]
**Origem**: [URL ou caminho]
**Tipo**: [Vídeo / Artigo / Paper / Pesquisa web]

---

## Resumo Executivo
- [5-10 bullets com os pontos mais importantes]

## Conceitos-Chave
- **[Conceito]**: definição concisa

## Tópicos Principais
### [Tópico 1]
[Explicação detalhada com exemplos se houver]

### [Tópico N]
...

## Fórmulas e Código
[Transcreva fielmente equações e trechos de código. Se não houver, omita esta seção.]

## Pontos de Destaque
[Insights únicos, conclusões do autor, recomendações práticas]"""


def distill_source(
    fonte: str,
    pasta: str,
    index: int,
    config: dict,
    llm: LLMClient,
) -> str:
    """Processa uma fonte e retorna o caminho do arquivo de transcrição gerado."""
    tipo = _classify(fonte)
    out_path = _make_out_path(pasta, tipo, index)

    if tipo == "youtube":
        raw = _process_youtube(fonte, config)
    elif tipo == "local_video":
        raw = _process_local_video(fonte, config)
    elif tipo == "github":
        raw = _process_github(fonte, config)
    elif tipo == "paper":
        raw = _process_paper(fonte)
    elif tipo == "article":
        raw = _process_article(fonte)
    else:
        raw = _process_search(fonte)

    content = _distill_with_llm(llm, fonte, tipo, raw)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(content, encoding="utf-8")
    return out_path


# ── Classificação ─────────────────────────────────────────────────────────────

def _classify(fonte: str) -> str:
    fl = fonte.lower()
    if any(x in fl for x in ["youtube.com/watch", "youtu.be/", "vimeo.com/"]):
        return "youtube"
    if any(fl.endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".webm", ".mov", ".m4v"]):
        return "local_video"
    if "github.com/" in fl:
        return "github"
    if any(x in fl for x in ["arxiv.org", "acm.org", "ieee.org", "scholar.google"]):
        return "paper"
    if fl.startswith("http://") or fl.startswith("https://"):
        return "article"
    return "search"


def _make_out_path(pasta: str, tipo: str, idx: int) -> str:
    names = {
        "youtube": f"transcript_{idx}.md",
        "local_video": f"transcript_{idx}.md",
        "github": f"github_{idx}.md",
        "article": f"artigo_{idx}.md",
        "paper": f"paper_{idx}.md",
        "search": f"pesquisa_{idx}.md",
    }
    return os.path.join(pasta, "transcripts", names.get(tipo, f"fonte_{idx}.md"))


# ── Processadores por tipo ────────────────────────────────────────────────────

def _process_youtube(url: str, config: dict) -> dict:
    info = get_video_info(url)
    transcript = get_youtube_transcript(url, config)
    return {
        "title": info["title"],
        "source_type": "vídeo YouTube",
        "metadata": f"Canal: {info['uploader']} | Duração: {_fmt_duration(info['duration'])}",
        "raw": transcript or info.get("description", "") or "[sem transcrição disponível]",
    }


def _process_local_video(path: str, config: dict) -> dict:
    transcript = transcribe_local_video(path, config)
    return {
        "title": os.path.basename(path),
        "source_type": "vídeo local",
        "metadata": "",
        "raw": transcript,
    }


def _process_github(url: str, config: dict) -> dict:
    owner, repo = _parse_github_url(url)
    headers = dict(_GITHUB_HEADERS)
    token = config.get("source_discovery", {}).get("github_token", "")
    if token:
        headers["Authorization"] = f"token {token}"

    readme = ""
    for branch in ("main", "master"):
        try:
            resp = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md",
                headers=headers, timeout=20,
            )
            if resp.status_code == 200:
                readme = resp.text[:8000]
                break
        except Exception:
            pass

    notebooks_text = ""
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
            headers=headers, timeout=20,
        )
        if resp.status_code == 200:
            tree = resp.json().get("tree", [])
            nb_paths = [
                item["path"] for item in tree
                if item.get("path", "").endswith(".ipynb") and item.get("type") == "blob"
            ][:2]
            for nb_path in nb_paths:
                for branch in ("main", "master"):
                    try:
                        nb_resp = requests.get(
                            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{nb_path}",
                            headers=headers, timeout=20,
                        )
                        if nb_resp.status_code == 200:
                            nb_text = _extract_notebook_text(nb_resp.text)
                            if nb_text:
                                notebooks_text += f"\n\n### Notebook: {nb_path}\n{nb_text[:3000]}"
                            break
                    except Exception:
                        pass
    except Exception:
        pass

    raw = f"# {owner}/{repo}\n\n{readme}{notebooks_text}"
    return {
        "title": f"{owner}/{repo}",
        "source_type": "repositório GitHub",
        "metadata": f"GitHub: {url}",
        "raw": raw or f"[Conteúdo indisponível: {url}]",
    }


def _parse_github_url(url: str) -> tuple[str, str]:
    m = re.search(r"github\.com/([^/]+)/([^/?\s#]+)", url)
    if not m:
        raise ValueError(f"URL GitHub inválida: {url}")
    return m.group(1), m.group(2)


def _extract_notebook_text(json_text: str) -> str:
    try:
        nb = json.loads(json_text)
        parts: list[str] = []
        for cell in nb.get("cells", []):
            src = cell.get("source", [])
            text = "".join(src) if isinstance(src, list) else str(src)
            if not text.strip():
                continue
            if cell.get("cell_type") == "markdown":
                parts.append(text.strip())
            elif cell.get("cell_type") == "code" and len(text.strip()) > 20:
                parts.append(f"```python\n{text.strip()}\n```")
        return "\n\n".join(parts)
    except Exception:
        return ""


def _process_paper(url: str) -> dict:
    content = fetch_url(url)
    return {
        "title": url,
        "source_type": "paper acadêmico",
        "metadata": "",
        "raw": content,
    }


def _process_article(url: str) -> dict:
    content = fetch_url(url)
    return {
        "title": url,
        "source_type": "artigo/blog/documentação",
        "metadata": "",
        "raw": content,
    }


def _process_search(query: str) -> dict:
    results_a = web_search(f"{query} resumo conceitos principais", max_results=5)
    results_b = web_search(f"{query} explicação didática exemplos", max_results=3)
    combined = "\n\n".join(
        f"**{r['title']}** ({r['url']})\n{r['snippet']}"
        for r in (results_a + results_b)
        if r.get("title")
    )
    return {
        "title": query,
        "source_type": "pesquisa web",
        "metadata": f"Query: {query}",
        "raw": combined or "[sem resultados de busca]",
    }


# ── LLM distillation ─────────────────────────────────────────────────────────

def _distill_with_llm(llm: LLMClient, fonte: str, tipo: str, data: dict) -> str:
    MAX_CHARS = 40_000
    raw = data["raw"]
    if len(raw) > MAX_CHARS:
        raw = raw[:MAX_CHARS] + "\n\n[... conteúdo truncado ...]"

    prompt = (
        f"Analise e resuma este conteúdo ({data['source_type']}).\n\n"
        f"**Fonte**: {fonte}\n"
        f"**Título**: {data['title']}\n"
        + (f"**Metadados**: {data['metadata']}\n" if data["metadata"] else "")
        + f"\n**Conteúdo bruto**:\n{raw}\n\n"
        "Produza o resumo estruturado conforme o formato solicitado."
    )

    return llm.chat(
        messages=[{"role": "user", "content": prompt}],
        system=_SYSTEM,
        max_tokens=4096,
    )


def _fmt_duration(seconds: int) -> str:
    if not seconds:
        return "desconhecida"
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"

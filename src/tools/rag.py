"""Ferramenta de busca semântica (RAG) nos materiais de estudo, exposta ao LLM."""
from __future__ import annotations
from pathlib import Path

from ..indexer import EmbeddingClient, build_or_update_index, search


def search_vault(query: str, k: int, pasta: str, config: dict) -> str:
    if not pasta:
        return "[Erro: nenhuma pasta de estudos associada a esta sessão]"

    pasta_path = Path(pasta).expanduser()
    if not pasta_path.exists():
        return f"[Erro: pasta não encontrada: {pasta}]"

    index = build_or_update_index(pasta_path, config)
    if not index["chunks"]:
        return "[Nenhum conteúdo indexado nesta pasta ainda]"

    embedder = EmbeddingClient(config)
    results = search(index, query, embedder, k=k)
    if not results:
        return "[Nenhum resultado relevante encontrado]"

    parts = []
    for r in results:
        fonte = f"[Fonte: {r['file']}" + (f" — {r['heading']}" if r["heading"] else "") + "]"
        parts.append(f"{fonte} (score={r['score']:.2f})\n{r['text']}")
    return "\n\n---\n\n".join(parts)

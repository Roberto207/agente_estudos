"""Busca e curadoria de fontes (YouTube/papers/GitHub/artigos), via JobManager."""
from __future__ import annotations
import dataclasses

from fastapi import APIRouter, HTTPException

from .. import deps
from ..jobs import job_manager
from ..schemas import DiscoverSourcesRequest

router = APIRouter()


def _discover_target(config: dict, tema: str, foco: str, max_per_camada: int, on_event) -> dict:
    from src.llm import LLMClient
    from src.source_discovery import SourceDiscoverer

    emit = on_event or (lambda *a, **k: None)
    emit("discover_start", {"tema": tema, "foco": foco})
    llm = LLMClient(config)
    discoverer = SourceDiscoverer(config, llm)
    sources = discoverer.discover(tema, foco, max_per_camada)
    fontes = [dataclasses.asdict(s) for s in sources]
    emit("discover_done", {"count": len(fontes)})
    return {"fontes": fontes}


@router.post("/api/spaces/{space_id}/discover-sources")
def api_discover_sources(space_id: str, body: DiscoverSourcesRequest):
    try:
        deps.resolve_space_path(space_id)  # só valida que o espaço existe
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")

    config = deps.load_config()
    job_id = job_manager.start(
        "discover_sources",
        _discover_target,
        config=config,
        tema=body.tema,
        foco=body.foco,
        max_per_camada=body.max_per_camada,
    )
    return {"job_id": job_id}

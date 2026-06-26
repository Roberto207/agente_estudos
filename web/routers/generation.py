"""Geração de conteúdo (modo agent) com toggles de output, via JobManager."""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import deps
from ..jobs import job_manager
from ..schemas import GenerateRequest, JobStatusOut, OutputsToggle

router = APIRouter()


def _generate_target(
    config: dict,
    tema: str,
    foco: str,
    didatica: str,
    pasta: str,
    fontes: list[str],
    outputs: dict,
    on_event,
) -> dict:
    """Roda o loop agêntico (sempre modo `agent` — ver decisão de design no plano:
    o frontend não expõe `pipeline`, que continua só como caminho de CLI legado).
    `agent.run()` retorna None, então o resultado é montado escaneando a pasta."""
    from src.agent import run as agent_run

    agent_run(
        config=config, tema=tema, foco=foco, didatica=didatica,
        pasta=pasta, fontes=fontes, on_event=on_event, outputs=outputs,
    )
    md_files = sorted(str(p) for p in Path(pasta).rglob("*.md"))
    return {"pasta": pasta, "arquivos_md": md_files}


def _postprocess_target(config: dict, pasta: str, outputs: dict, on_event) -> dict:
    """Roda só o pós-processamento (flashcards/quiz/canvas/html/...) sobre uma
    pasta já existente, sem passar pelo agente completo."""
    from src.llm import LLMClient
    from src.postprocessing import run_postprocessing

    llm = LLMClient(config)
    return run_postprocessing(llm, pasta, outputs=outputs, on_event=on_event)


@router.post("/api/spaces/{space_id}/generate")
def api_generate(space_id: str, body: GenerateRequest):
    try:
        space_path = deps.resolve_space_path(space_id)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")

    config = deps.load_config()
    job_id = job_manager.start(
        "generate",
        _generate_target,
        config=config,
        tema=body.tema,
        foco=body.foco,
        didatica=body.didatica,
        pasta=str(space_path),
        fontes=body.fontes,
        outputs=body.outputs.model_dump(),
    )
    return {"job_id": job_id}


@router.post("/api/spaces/{space_id}/postprocess")
def api_postprocess(space_id: str, body: OutputsToggle):
    try:
        space_path = deps.resolve_space_path(space_id)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")

    config = deps.load_config()
    job_id = job_manager.start(
        "postprocess", _postprocess_target,
        config=config, pasta=str(space_path), outputs=body.model_dump(),
    )
    return {"job_id": job_id}


@router.get("/api/jobs/{job_id}", response_model=JobStatusOut)
def api_job_status(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "events": job.events,
        "result": job.result,
        "error": job.error,
    }

"""Páginas (home, workspace) + API de espaços/árvore/arquivo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import deps
from ..markdown_render import render_markdown
from ..schemas import CreateSpaceRequest, OpenSpaceRequest
from ..templating import templates

router = APIRouter()


def get_config() -> dict:
    return deps.load_config()


# ── Páginas ───────────────────────────────────────────────────────────────────

@router.get("/")
def home(request: Request, config: dict = Depends(get_config)):
    spaces = deps.list_spaces(config)
    return templates.TemplateResponse(request, "home.html", {
        "spaces": spaces,
        "vault_root": str(deps.vault_root(config)),
    })


@router.get("/w/{space_id}")
def workspace(request: Request, space_id: str):
    try:
        space_path = deps.resolve_space_path(space_id)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")

    tree = deps.build_tree(space_path)
    return templates.TemplateResponse(request, "workspace.html", {
        "space_id": space_id,
        "space_name": space_path.name,
        "space_path": str(space_path),
        "tree": tree,
    })


# ── API: espaços ──────────────────────────────────────────────────────────────

@router.post("/api/spaces")
def api_create_space(body: CreateSpaceRequest, config: dict = Depends(get_config)):
    try:
        space_id = deps.create_space(config, body.nome, body.parent)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc))
    return {"space_id": space_id}


@router.post("/api/spaces/open")
def api_open_space(body: OpenSpaceRequest):
    try:
        space_id = deps.open_space(body.path)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    return {"space_id": space_id}


@router.get("/api/spaces/{space_id}/tree")
def api_tree(space_id: str):
    try:
        space_path = deps.resolve_space_path(space_id)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")
    return {"tree": deps.build_tree(space_path)}


@router.get("/api/spaces/{space_id}/file")
def api_file(space_id: str, path: str):
    try:
        space_path = deps.resolve_space_path(space_id)
        file_path = deps.read_space_file(space_path, path)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo não encontrado")
    except PermissionError:
        raise HTTPException(403, "Path inválido")

    raw = file_path.read_text(encoding="utf-8")
    html = render_markdown(raw) if file_path.suffix == ".md" else None
    return {"path": path, "raw": raw, "html": html}

"""Páginas (home, workspace) + API de espaços/árvore/arquivo."""
from __future__ import annotations
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .. import deps
from ..markdown_render import render_markdown
from ..schemas import CreateSpaceRequest, OpenSpaceRequest, SaveFileRequest, CreateFileRequest, CreateFolderRequest
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

    try:
        tree = deps.build_tree(space_path)
    except Exception as exc:
        raise HTTPException(500, f"Falha ao ler a árvore de arquivos de '{space_path}': {exc}")

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


@router.delete("/api/spaces/{space_id}")
def api_hide_space(space_id: str):
    try:
        path = deps.decode_space_id(space_id)
    except Exception:
        raise HTTPException(400, "space_id inválido")
    deps.hide_space(path.resolve())
    return {"ok": True}


@router.get("/api/spaces/{space_id}/raw-file")
def api_raw_file(space_id: str, path: str):
    """Serve o arquivo com Content-Type correto.

    Para HTMLs, reescreve hrefs relativos (links entre páginas do mesmo site)
    para passarem pelo mesmo endpoint, mantendo a navegação funcional no iframe.
    """
    try:
        space_path = deps.resolve_space_path(space_id)
        file_path = deps.read_space_file(space_path, path)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo não encontrado")
    except PermissionError:
        raise HTTPException(403, "Path inválido")

    if file_path.suffix.lower() != ".html":
        return Response(content=file_path.read_bytes(), media_type="text/plain")

    dir_prefix = str(Path(path).parent)
    if dir_prefix == ".":
        dir_prefix = ""

    def _rewrite(m: re.Match) -> str:
        href = m.group(1)
        if href.startswith(("#", "http://", "https://", "/")):
            return m.group(0)
        new_path = f"{dir_prefix}/{href}".lstrip("/") if dir_prefix else href
        return f'href="/api/spaces/{space_id}/raw-file?path={quote(new_path)}"'

    content = re.sub(r'href="([^"]*)"', _rewrite, file_path.read_text(encoding="utf-8"))
    return Response(content=content.encode("utf-8"), media_type="text/html")


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


@router.put("/api/spaces/{space_id}/file")
def api_save_file(space_id: str, body: SaveFileRequest):
    try:
        space_path = deps.resolve_space_path(space_id)
        deps.write_space_file(space_path, body.path, body.content)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo não encontrado")
    except PermissionError:
        raise HTTPException(403, "Path inválido")
    return {"ok": True}


@router.delete("/api/spaces/{space_id}/file")
def api_delete_file(space_id: str, path: str):
    try:
        space_path = deps.resolve_space_path(space_id)
        deps.delete_space_file(space_path, path)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo não encontrado")
    except PermissionError:
        raise HTTPException(403, "Path inválido")
    return {"ok": True}


@router.post("/api/spaces/{space_id}/files")
def api_create_file(space_id: str, body: CreateFileRequest):
    try:
        space_path = deps.resolve_space_path(space_id)
        deps.create_space_file(space_path, body.path)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc))
    except PermissionError:
        raise HTTPException(403, "Path inválido")
    return {"ok": True, "path": body.path}


@router.post("/api/spaces/{space_id}/folders")
def api_create_folder(space_id: str, body: CreateFolderRequest):
    try:
        space_path = deps.resolve_space_path(space_id)
        deps.create_space_folder(space_path, body.path)
    except FileNotFoundError:
        raise HTTPException(404, "Espaço não encontrado")
    except FileExistsError as exc:
        raise HTTPException(409, str(exc))
    except PermissionError:
        raise HTTPException(403, "Path inválido")
    return {"ok": True, "path": body.path}

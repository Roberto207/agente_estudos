"""Config loader e modelo de "espaços" (pastas de estudo) — sem banco de dados.

Identidade de um espaço = path absoluto, codificado em base64 urlsafe como space_id.
A pasta no filesystem já é a fonte de verdade (índice RAG mora em .rag_index.json
dentro dela, como hoje); não há nenhum estado a sincronizar com um banco externo.
"""
from __future__ import annotations
import base64
import os
import re
from pathlib import Path

import yaml

DEFAULT_VAULT_ROOT = "~/obsidian"

# Subpastas que são saída do pipeline, não "conteúdo navegável" no sentido de espaço.
_NON_CONTENT_DIRS = {"transcripts", "html", ".obsidian", ".rag_index.json"}


# ── Config ──────────────────────────────────────────────────────────────────────

_CONFIG_PATHS = [
    Path("config.yaml"),
    Path(__file__).resolve().parent.parent / "config.yaml",
]


def load_config(config_path: str = "") -> dict:
    """Reusa a mesma lógica de `main.py::_load_config` (sem duplicar)."""
    import main as _main  # import tardio: evita rodar o Typer app na importação do módulo
    return _main._load_config(config_path)


def vault_root(config: dict) -> Path:
    raw = config.get("web", {}).get("vault_root", DEFAULT_VAULT_ROOT)
    return Path(raw).expanduser()


# ── Espaços ─────────────────────────────────────────────────────────────────────

def encode_space_id(path: Path) -> str:
    raw = str(path.resolve())
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_space_id(space_id: str) -> Path:
    padded = space_id + "=" * (-len(space_id) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    return Path(raw)


def resolve_space_path(space_id: str) -> Path:
    """Decodifica o space_id e garante que a pasta ainda existe."""
    path = decode_space_id(space_id)
    if not path.is_dir():
        raise FileNotFoundError(f"Espaço não encontrado: {path}")
    return path


def list_spaces(config: dict) -> list[dict]:
    root = vault_root(config)
    if not root.is_dir():
        return []

    spaces = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        spaces.append(_describe_space(entry))
    spaces.sort(key=lambda s: s["ultima_modificacao"], reverse=True)
    return spaces


def _describe_space(path: Path) -> dict:
    md_files = list(path.rglob("*.md"))
    ultima_modificacao = max((f.stat().st_mtime for f in md_files), default=path.stat().st_mtime)
    return {
        "space_id": encode_space_id(path),
        "nome": path.name.replace("_", " ").title(),
        "path": str(path),
        "tem_conteudo": bool(md_files),
        "total_arquivos": len(md_files),
        "ultima_modificacao": ultima_modificacao,
    }


def create_space(config: dict, nome: str, parent: str = "") -> str:
    base = Path(parent).expanduser() if parent else vault_root(config)
    base.mkdir(parents=True, exist_ok=True)
    slug = _slugify(nome)
    target = base / slug
    if target.exists():
        raise FileExistsError(f"Já existe um espaço em: {target}")
    target.mkdir(parents=True)
    return encode_space_id(target)


def open_space(path: str) -> str:
    target = Path(path).expanduser().resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {target}")
    return encode_space_id(target)


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s-]+", "_", text) or "espaco"


# ── Árvore de arquivos ──────────────────────────────────────────────────────────

def build_tree(space_path: Path) -> list[dict]:
    """Lista recursiva de pastas/arquivos dentro de um espaço, ordenada (dirs antes
    de arquivos, alfabético). `path` em cada nó é relativo à raiz do espaço."""
    return _walk(space_path, space_path)


def _walk(current: Path, root: Path) -> list[dict]:
    nodes = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except FileNotFoundError:
        return []

    for entry in entries:
        if entry.name.startswith("."):
            continue
        rel = str(entry.relative_to(root))
        if entry.is_dir():
            nodes.append({
                "name": entry.name,
                "path": rel,
                "type": "dir",
                "children": _walk(entry, root),
            })
        else:
            nodes.append({
                "name": entry.name,
                "path": rel,
                "type": "file",
                "ext": entry.suffix.lstrip("."),
            })
    return nodes


def read_space_file(space_path: Path, rel_path: str) -> Path:
    """Resolve um path relativo dentro do espaço, recusando escapar da pasta (path traversal)."""
    candidate = (space_path / rel_path).resolve()
    space_resolved = space_path.resolve()
    if space_resolved not in candidate.parents and candidate != space_resolved:
        raise PermissionError("Path fora do espaço")
    if not candidate.is_file():
        raise FileNotFoundError(rel_path)
    return candidate

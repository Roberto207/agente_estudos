"""Ferramentas de filesystem expostas como tools do LLM."""
from __future__ import annotations
from pathlib import Path


def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {p} ({len(content)} chars)"


def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[Erro: arquivo não encontrado: {path}]"
    text = p.read_text(encoding="utf-8")
    if len(text) > 50_000:
        text = text[:50_000] + "\n\n[... truncado ...]"
    return text


def create_directory(path: str) -> str:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return f"Diretório criado: {p}"


def list_directory(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[Diretório não encontrado: {path}]"
    items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
    lines = []
    for item in items:
        prefix = "  " if item.is_file() else "📁"
        lines.append(f"{prefix} {item.name}")
    return f"{path}/\n" + "\n".join(lines) if lines else f"{path}/ (vazio)"

"""Conversão de .md para HTML usando markdown-it-py (mesma lib já usada transitivamente pelo rich).

Também converte wikilinks Obsidian ([[arquivo]], [[arquivo|label]]) em links internos
clicáveis (`data-wikilink`) que o workspace.js intercepta para abrir o arquivo no painel
central, sem reload de página — mantendo a navegação "estilo Obsidian" pedida no spec.
"""
from __future__ import annotations
import re

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _replace_wikilinks(text: str) -> str:
    def repl(match: re.Match) -> str:
        target = match.group(1).strip()
        label = (match.group(2) or target).strip()
        return f'<a href="#" class="wikilink" data-wikilink="{target}">{label}</a>'

    return _WIKILINK_RE.sub(repl, text)


def render_markdown(text: str) -> str:
    return _md.render(_replace_wikilinks(text))

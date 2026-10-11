"""Seleção e ordenação do material de uma pasta de estudo (DEFINE D1, D2, D3, D9)."""
from __future__ import annotations
import re
from pathlib import Path

# D1 — o que NÃO é ".md de conteúdo".
_DIRS_EXCLUIDOS = {"transcripts", "podcast", "html"}
# Gerados pelos agentes (guia do criar-estudo, próximos passos, curadoria do buscar-fontes),
# não material de estudo — fontes_selecionadas.md virava um "episódio" sobre a lista de links.
_ARQUIVOS_EXCLUIDOS = {"guia_de_estudos.md", "proximos_passos.md", "fontes_selecionadas.md"}
GUIA = "guia_de_estudos.md"
LIMIAR_MATERIAL_CURTO = 1500  # D9

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def arquivos_de_conteudo(pasta: str | Path) -> list[str]:
    """D1: caminhos relativos a `pasta`, com `/`, em ordem alfabética."""
    raiz = Path(pasta)
    result = []
    for md in raiz.rglob("*.md"):
        rel = md.relative_to(raiz)
        if md.name in _ARQUIVOS_EXCLUIDOS:
            continue
        if any(p in _DIRS_EXCLUIDOS or p.startswith(".") for p in rel.parts[:-1]):
            continue
        result.append(rel.as_posix())
    return sorted(result)


def ordem_do_guia(pasta: str | Path, arquivos: list[str] | None = None) -> list[str]:
    """D2: ordem da primeira ocorrência de cada [[wikilink]] do guia que resolve
    (pelo nome sem extensão) para um .md de conteúdo; o resto vem depois, em
    ordem alfabética. Sem guia, só a ordem alfabética."""
    arquivos = sorted(arquivos if arquivos is not None else arquivos_de_conteudo(pasta))
    guia = Path(pasta) / GUIA
    if not guia.exists():
        return arquivos

    por_stem: dict[str, list[str]] = {}
    for rel in arquivos:
        por_stem.setdefault(Path(rel).stem, []).append(rel)

    ordem: list[str] = []
    vistos: set[str] = set()
    for alvo in _WIKILINK.findall(guia.read_text(encoding="utf-8")):
        # [[pasta/nome#seção|apelido]] → "nome"
        stem = Path(alvo.split("|")[0].split("#")[0].strip()).stem
        for rel in por_stem.get(stem, []):
            if rel not in vistos:
                vistos.add(rel)
                ordem.append(rel)
    return ordem + [rel for rel in arquivos if rel not in vistos]


def posicao_do_episodio(arquivos_do_episodio: list[str], ordem: list[str]) -> int:
    """D3: menor posição, na ordem D2, entre os arquivos-fonte do episódio."""
    posicoes = {rel: i for i, rel in enumerate(ordem)}
    return min(posicoes.get(rel, len(ordem)) for rel in arquivos_do_episodio)


def palavras(pasta: str | Path, arquivos: list[str]) -> int:
    return sum(len((Path(pasta) / rel).read_text(encoding="utf-8").split()) for rel in arquivos)


def material_curto(pasta: str | Path, arquivos: list[str]) -> bool:
    """D9."""
    return palavras(pasta, arquivos) < LIMIAR_MATERIAL_CURTO

"""Divisão de falas longas em pedaços que o motor sintetiza bem."""
from __future__ import annotations
import re

_FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")
_VIRGULA = re.compile(r"(?<=[,;:])\s+")


def pedacos(texto: str, max_chars: int) -> list[str]:
    """Quebra `texto` em pedaços de até `max_chars`, nas fronteiras de frase; uma
    frase sozinha maior que o limite é quebrada nas vírgulas e, em último caso,
    nas palavras. XTTS e Chatterbox degradam (ou cortam) com entradas longas."""
    texto = " ".join(texto.split())
    if len(texto) <= max_chars:
        return [texto] if texto else []
    unidades: list[str] = []
    for frase in _FIM_DE_FRASE.split(texto):
        if len(frase) <= max_chars:
            unidades.append(frase)
            continue
        for parte in _VIRGULA.split(frase):
            if len(parte) <= max_chars:
                unidades.append(parte)
            else:
                unidades.extend(_por_palavras(parte, max_chars))
    return _juntar(unidades, max_chars)


def _por_palavras(texto: str, max_chars: int) -> list[str]:
    saida, atual = [], ""
    for palavra in texto.split():
        if atual and len(atual) + 1 + len(palavra) > max_chars:
            saida.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    return saida + ([atual] if atual else [])


def _juntar(unidades: list[str], max_chars: int) -> list[str]:
    """Reagrupa frases curtas vizinhas até o limite — menos chamadas ao motor."""
    saida, atual = [], ""
    for u in unidades:
        if atual and len(atual) + 1 + len(u) > max_chars:
            saida.append(atual)
            atual = u
        else:
            atual = f"{atual} {u}".strip()
    return saida + ([atual] if atual else [])

"""Texto da fala → texto falável em pt-BR (DEFINE R19).

Determinístico, por código: numerais são o tipo de coisa que o LLM erra com
frequência, e o TTS lê "0.01" ou "1.000" de formas imprevisíveis. Roda só no
estágio 2 — o roteiro gravado mantém os dígitos (e a contagem de palavras de D6).
Casos de referência: tests/podcast/normalize_casos.json.
"""
from __future__ import annotations
import re

from num2words import num2words

_LETRA_HIFEN_DIGITO = re.compile(r"([^\W\d_])-(\d)")              # GPT-4 → GPT 4
# 1.000 / 1.234,5 — o primeiro grupo não começa com 0, senão "0.001" (taxa de
# aprendizado escrita no padrão inglês) viraria "um".
_MILHAR = re.compile(r"\b[1-9]\d{0,2}(?:\.\d{3})+(?:,\d+)?\b")
_ORDINAL = re.compile(r"\b(\d+)\s?([ºª])")
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s?%")
_DECIMAL = re.compile(r"\b(\d+)[.,](\d+)\b")
_INTEIRO = re.compile(r"\d+")


def _cardinal(n: str) -> str:
    return num2words(int(n), lang="pt_BR")


def _decimal(inteiro: str, frac: str) -> str:
    # Parte fracionária dígito a dígito: "0,01" → "zero vírgula zero um" (sem ambiguidade).
    return f"{_cardinal(inteiro)} vírgula " + " ".join(_cardinal(d) for d in frac)


def _numero(token: str) -> str:
    if m := re.fullmatch(r"(\d+)[.,](\d+)", token):
        return _decimal(m.group(1), m.group(2))
    return _cardinal(token)


def normalizar(texto: str) -> str:
    t = _LETRA_HIFEN_DIGITO.sub(r"\1 \2", texto)
    # Milhar no padrão brasileiro: tira os pontos antes de tudo ("1.000" não é decimal).
    t = _MILHAR.sub(lambda m: m.group(0).replace(".", ""), t)
    t = _ORDINAL.sub(
        lambda m: num2words(int(m.group(1)), lang="pt_BR", to="ordinal")
        if m.group(2) == "º"
        else _ordinal_feminino(int(m.group(1))),
        t,
    )
    t = _PERCENT.sub(lambda m: f"{_numero(m.group(1))} por cento", t)
    t = _DECIMAL.sub(lambda m: _decimal(m.group(1), m.group(2)), t)
    t = _INTEIRO.sub(lambda m: f" {_cardinal(m.group(0))} ", t)
    return re.sub(r"\s+", " ", t).replace(" ,", ",").replace(" .", ".").strip()


def _ordinal_feminino(n: int) -> str:
    # num2words só tem o masculino; o feminino troca o "o" final de cada palavra.
    return " ".join(p[:-1] + "a" if p.endswith("o") else p
                    for p in num2words(n, lang="pt_BR", to="ordinal").split())

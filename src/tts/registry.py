"""Registro dos motores de voz (import tardio: a máquina local não precisa de torch)."""
from __future__ import annotations
from typing import Callable

from .base import Engine, ErroTTS

_FABRICAS: dict[str, Callable[[dict], Engine]] = {}


def _padrao() -> dict[str, Callable[[dict], Engine]]:
    def edge(cfg):
        from .edge import EdgeEngine
        return EdgeEngine(cfg)

    def xtts(cfg):
        from .xtts import XttsEngine
        return XttsEngine(cfg)

    def chatterbox(cfg):
        from .chatterbox import ChatterboxEngine
        return ChatterboxEngine(cfg)

    def qwen3(cfg):
        from .qwen3 import Qwen3Engine
        return Qwen3Engine(cfg)

    return {"edge": edge, "xtts": xtts, "chatterbox": chatterbox, "qwen3": qwen3}


# Motores que clonam (D10), declarados sem importar as bibliotecas pesadas.
_CLONAM = {"xtts": False, "chatterbox": False, "qwen3": True}  # valor = exige ref_text


def registrar(nome: str, fabrica: Callable[[dict], Engine], clona: bool = False, exige_ref_text: bool = False) -> None:
    """Para testes e motores extras."""
    _FABRICAS[nome] = fabrica
    if clona:
        _CLONAM[nome] = exige_ref_text


def nomes() -> list[str]:
    return sorted({*_padrao(), *_FABRICAS})


def engines_que_clonam() -> list[str]:
    """D10."""
    return sorted(_CLONAM)


def exige_ref_text(nome: str) -> bool:
    return _CLONAM.get(nome, False)


def get_engine(nome: str, cfg_voz: dict) -> Engine:
    fabricas = {**_padrao(), **_FABRICAS}
    if nome not in fabricas:
        raise ErroTTS(f"motor de voz desconhecido: {nome!r}. Opções: {', '.join(nomes())}")
    return fabricas[nome](cfg_voz["engines"].get(nome, {}))

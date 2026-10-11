"""Teste de vozes — `main.py --mode voice-test` (DEFINE R35–R37).

O mesmo trecho fixo (número, decimal, sigla, termo em inglês) em cada motor, um MP3
por motor, para escolher o motor e as vozes de ouvido. Nunca escreve em pasta de
estudo. A falha de um motor (dependência ausente, sem GPU, erro de rede) não
interrompe os outros.
"""
from __future__ import annotations
import json
import traceback
from pathlib import Path

from rich.console import Console

from ..podcast.script_io import parse
from . import registry
from .audio import sintetizar_roteiro
from .base import config_voz

console = Console()
TRECHO = Path(__file__).with_name("trecho_teste.md")


def run(config: dict, saida: str = "teste_vozes", engines: list[str] | None = None) -> dict:
    cfg_voz = config_voz(config)
    destino = Path(saida).expanduser().resolve()
    destino.mkdir(parents=True, exist_ok=True)
    roteiro = parse(TRECHO.read_text(encoding="utf-8"))
    resultados = []
    for nome in engines or cfg_voz["teste"]["engines"]:
        item = {"engine": nome, "ok": False, "erro": None}
        try:
            engine = registry.get_engine(nome, cfg_voz)
            # R36: clone só onde o motor clona; nos demais, voz fixa — sem erro.
            usar_clone = engine.clona and not (registry.exige_ref_text(nome) and not all(
                (c.get("ref_text") or "").strip() for c in cfg_voz["clone"].values() if c.get("ref_wav")))
            with console.status(f"[yellow]Teste de vozes: {nome}...[/yellow]"):
                stats = sintetizar_roteiro(engine, cfg_voz, roteiro, Path(cfg_voz["cache_dir"]).expanduser(),
                                           destino / f"{nome}.mp3",
                                           usar_clone=usar_clone)
            item.update(ok=True, arquivo=str(destino / f"{nome}.mp3"), **stats)
            console.print(f"  [green]✓[/green] {nome}: {destino / f'{nome}.mp3'} ({stats['duracao_s']}s)")
        except Exception as exc:  # R37 — isola a falha deste motor
            item["erro"] = f"{type(exc).__name__}: {exc}"
            item["detalhe"] = traceback.format_exc(limit=3)
            console.print(f"  [red]✗[/red] {nome}: {item['erro']}")
        resultados.append(item)
    relatorio = {"trecho": TRECHO.name, "resultados": resultados}
    (destino / "relatorio.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return relatorio

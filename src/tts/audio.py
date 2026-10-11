"""Estágio 2 — `main.py --mode podcast-audio` (DEFINE R27–R34; DESIGN §7).

Roteiro → fala a fala (texto normalizado, quebrado no limite do motor) → cache
por fala → episódio montado com pausas → MP3 com loudness normalizada + manifesto.
Lê só `<pasta>/podcast/`: o notebook de GPU precisa apenas do zip dessa pasta.
"""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..podcast.lint import lint
from ..podcast.normalize import normalizar
from ..podcast.script_io import Roteiro, parse
from . import registry
from .audio_io import FORMATO, concatenar, duracao_s, para_mp3
from .base import Engine, ErroTTS, config_voz
from .cache import chave, obter_ou_sintetizar, sha1_arquivo
from .texto import pedacos

console = Console()


def validar_clone(engine: Engine, cfg_voz: dict) -> None:
    """R31: com clone configurado num motor que não clona, ou referência ausente,
    o podcast-audio para ANTES de sintetizar qualquer coisa."""
    for papel, c in cfg_voz["clone"].items():
        ref = (c or {}).get("ref_wav")
        if not ref:
            continue
        if engine.nome not in registry.engines_que_clonam():
            raise ErroTTS(f"voz.clone.{papel}.ref_wav está definido, mas o motor {engine.nome!r} não clona voz. "
                          f"Motores que clonam: {', '.join(registry.engines_que_clonam())}.")
        if not Path(ref).expanduser().is_file():
            raise ErroTTS(f"voz.clone.{papel}.ref_wav não encontrado: {ref}")
        if registry.exige_ref_text(engine.nome) and not (c.get("ref_text") or "").strip():
            raise ErroTTS(f"o motor {engine.nome!r} exige a transcrição do áudio de referência "
                          f"em voz.clone.{papel}.ref_text.")


def voz_do_papel(engine: Engine, cfg_voz: dict, papel: str, usar_clone: bool = True) -> dict:
    """Voz fixa do papel, ou a referência de clonagem quando o motor clona (R29/R30/R36)."""
    papel = papel.lower()
    c = cfg_voz["clone"].get(papel) or {}
    ref = c.get("ref_wav") if (usar_clone and engine.clona) else None
    if ref:
        ref = str(Path(ref).expanduser())
        ref_text = c.get("ref_text")
        vid = f"clone:{sha1_arquivo(ref)}:{hashlib.sha1((ref_text or '').encode()).hexdigest()[:8]}"
        return {"voz": None, "ref_wav": ref, "ref_text": ref_text, "id": vid, "clone_sha1": vid.split(":")[1]}
    voz = cfg_voz["engines"].get(engine.nome, {}).get(papel)
    return {"voz": voz, "ref_wav": None, "ref_text": None, "id": f"voz:{voz}", "clone_sha1": None}


def sintetizar_roteiro(engine: Engine, cfg_voz: dict, roteiro: Roteiro, dir_cache: Path, saida_mp3: Path,
                       usar_clone: bool = True) -> dict:
    """Monta o MP3 de um roteiro. Devolve estatísticas para o manifesto e o relatório."""
    versao = f"{engine.versao()}|{FORMATO}"
    vozes = {p: voz_do_papel(engine, cfg_voz, p, usar_clone) for p in ("professor", "aprendiz")}
    pausa = cfg_voz["pausa_ms"]
    itens: list[Path | int] = []
    do_cache = sintetizadas = 0
    bloco_anterior = None
    for fala in roteiro.falas:
        if itens:
            itens.append(pausa["bloco"] if fala.bloco != bloco_anterior else pausa["fala"])
        bloco_anterior = fala.bloco
        v = vozes[fala.papel.lower()]
        for i, pedaco in enumerate(pedacos(normalizar(fala.texto), engine.max_chars)):
            if i:
                itens.append(pausa["pedaco"])
            k = chave(engine.nome, versao, v["id"], pedaco)
            wav, veio = obter_ou_sintetizar(
                dir_cache, k,
                lambda destino, t=pedaco, v=v: engine.sintetizar(t, v["voz"], v["ref_wav"], v["ref_text"], destino))
            itens.append(wav)
            do_cache += veio
            sintetizadas += not veio
    if not itens:
        raise ErroTTS("roteiro sem falas")

    saida_mp3.parent.mkdir(parents=True, exist_ok=True)
    wav_tmp = saida_mp3.with_name(f".{saida_mp3.stem}.montagem.wav")
    mp3_tmp = saida_mp3.with_name(f".{saida_mp3.stem}.tmp.mp3")
    try:
        concatenar(itens, wav_tmp)
        para_mp3(wav_tmp, mp3_tmp)
        os.replace(mp3_tmp, saida_mp3)
    finally:
        wav_tmp.unlink(missing_ok=True)
        mp3_tmp.unlink(missing_ok=True)
    return {
        "engine": engine.nome,
        "versao_engine": versao,
        "vozes": {p: v["voz"] for p, v in vozes.items() if not v["ref_wav"]},
        "clone_sha1": {p: v["clone_sha1"] for p, v in vozes.items() if v["ref_wav"]},
        "duracao_s": duracao_s(saida_mp3),
        "pedacos_do_cache": do_cache,
        "pedacos_sintetizados": sintetizadas,
    }


def _roteiros(podcast: Path) -> list[tuple[int, Path, Roteiro]]:
    saida = []
    for p in sorted(podcast.glob("episodio_*.md")):
        r = parse(p.read_text(encoding="utf-8"))
        try:
            n = int(r.frontmatter.get("episodio") or p.stem.split("_")[1])
        except (ValueError, IndexError):
            continue
        saida.append((n, p, r))
    return saida


def run(config: dict, pasta: str, episodios: list[int] | None = None, engine_nome: str | None = None) -> dict:
    cfg_voz = config_voz(config)
    podcast = Path(pasta).expanduser().resolve() / "podcast"
    roteiros = _roteiros(podcast)
    if not roteiros:
        raise ErroTTS(f"nenhum roteiro em {podcast} — gere os roteiros antes do áudio.")
    if episodios:
        invalidos = sorted(set(episodios) - {n for n, _, _ in roteiros})
        if invalidos:
            raise ErroTTS(f"--episodios com número(s) sem roteiro: {', '.join(map(str, invalidos))}")
        roteiros = [x for x in roteiros if x[0] in episodios]

    engine = registry.get_engine(engine_nome or cfg_voz["engine"], cfg_voz)
    validar_clone(engine, cfg_voz)
    if engine.nome == "chatterbox" and not any(c.get("ref_wav") for c in cfg_voz["clone"].values()):
        console.print("[yellow]aviso:[/yellow] chatterbox sem áudio de referência — Professor e Aprendiz terão a mesma voz.")

    total = len(_roteiros(podcast))
    audio_dir = podcast / "audio"
    linhas, pulados = [], []
    for n, caminho, roteiro in roteiros:
        status = roteiro.frontmatter.get("lint") or lint(caminho.read_text(encoding="utf-8"), n, total, True).status
        if status == "reprovado":  # R28 — texto com símbolos/markdown não vai para o TTS
            pulados.append(n)
            continue
        with console.status(f"[yellow]Episódio {n}: sintetizando {len(roteiro.falas)} falas ({engine.nome})...[/yellow]"):
            stats = sintetizar_roteiro(engine, cfg_voz, roteiro, Path(cfg_voz["cache_dir"]).expanduser(),
                                       audio_dir / f"{caminho.stem}.mp3")
        manifesto = {**stats, "episodio": n, "roteiro": caminho.name, "roteiro_sha1": sha1_arquivo(caminho),
                     "data": datetime.now().astimezone().isoformat(timespec="seconds")}
        (audio_dir / f"{caminho.stem}.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
        linhas.append(manifesto)

    _imprimir(linhas, pulados)
    return {"episodios": linhas, "pulados_lint_reprovado": pulados}


def _imprimir(linhas: list[dict], pulados: list[int]) -> None:
    t = Table(title="Áudio", border_style="purple")
    for col in ("Ep.", "Motor", "Duração", "Pedaços novos", "Do cache"):
        t.add_column(col)
    for l in linhas:
        m, s = divmod(int(l["duracao_s"]), 60)
        t.add_row(str(l["episodio"]), l["engine"], f"{m}min{s:02d}s",
                  str(l["pedacos_sintetizados"]), str(l["pedacos_do_cache"]))
    console.print(t)
    if pulados:
        console.print(f"[yellow]Pulados por lint reprovado:[/yellow] {', '.join(map(str, pulados))}")

"""Cache de falas sintetizadas (DEFINE R32/R33)."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Callable

from .audio_io import para_wav_padrao


def sha1_arquivo(caminho: str | Path) -> str:
    return hashlib.sha1(Path(caminho).read_bytes()).hexdigest()


def chave(engine: str, versao: str, voz_id: str, texto: str) -> str:
    """R32: muda o motor, a versão dele, a voz (ou o áudio de referência) ou o texto
    já normalizado → muda a chave. Mesmo texto e mesma voz → mesmo arquivo."""
    return hashlib.sha1(f"{engine}|{versao}|{voz_id}|{texto}".encode("utf-8")).hexdigest()


def obter_ou_sintetizar(dir_cache: Path, k: str, sintetizar: Callable[[Path], None]) -> tuple[Path, bool]:
    """Devolve (wav no formato-padrão, veio_do_cache). Grava em `.tmp` e renomeia
    só no fim (R33): uma execução interrompida nunca deixa um arquivo parcial com
    nome de chave válida, então a próxima execução simplesmente refaz aquela fala."""
    dir_cache.mkdir(parents=True, exist_ok=True)
    final = dir_cache / f"{k}.wav"
    if final.exists():
        return final, True
    bruto = dir_cache / f"{k}.bruto.tmp"
    tmp = dir_cache / f"{k}.wav.tmp"
    try:
        sintetizar(bruto)
        para_wav_padrao(bruto, tmp)
        os.replace(tmp, final)
    finally:
        for p in (bruto, tmp):
            p.unlink(missing_ok=True)
    return final, False

"""Conversão, concatenação e finalização de áudio (ffmpeg + `wave` da stdlib)."""
from __future__ import annotations
import json
import shutil
import subprocess
import wave
from pathlib import Path

from .base import ErroTTS

TAXA = 24000   # Hz — formato-padrão interno: WAV mono 16 bits a 24 kHz
LARGURA = 2    # bytes por amostra (s16)
# Versão do formato-padrão: entra na chave do cache, para áudio convertido por uma
# versão anterior desta função não ser reaproveitado. v2: apara silêncio das pontas.
FORMATO = "wav24k-mono-s16-v2"
# Silêncio do início e do fim de cada pedaço sai (os motores deixam ~0,2 s), para a
# pausa entre falas ser exatamente a configurada em voz.pausa_ms.
_APARAR = ("silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB,areverse,"
           "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-50dB,areverse")


def _ffmpeg(*args: str) -> None:
    if shutil.which("ffmpeg") is None:
        raise ErroTTS("ffmpeg não encontrado — instale o ffmpeg (necessário para montar o áudio).")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroTTS(f"ffmpeg falhou: {r.stderr.strip()[-400:]}")


def para_wav_padrao(entrada: Path, saida: Path) -> None:
    """Qualquer áudio → WAV mono s16 24 kHz (o motor de cada engine sai num formato diferente)."""
    _ffmpeg("-i", str(entrada), "-af", _APARAR, "-ac", "1", "-ar", str(TAXA), "-sample_fmt", "s16",
            "-f", "wav", str(saida))


def concatenar(itens: list[Path | int], saida: Path) -> None:
    """Junta WAVs no formato-padrão; inteiros na lista são pausas em milissegundos."""
    with wave.open(str(saida), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(LARGURA)
        out.setframerate(TAXA)
        for item in itens:
            if isinstance(item, int):
                out.writeframes(b"\x00\x00" * int(TAXA * item / 1000))
                continue
            with wave.open(str(item), "rb") as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, LARGURA, TAXA):
                    raise ErroTTS(f"{item} fora do formato-padrão — use para_wav_padrao antes.")
                out.writeframes(w.readframes(w.getnframes()))


def para_mp3(wav: Path, mp3: Path) -> None:
    """Normaliza a loudness (−16 LUFS, padrão de podcast) e codifica MP3 mono 128k."""
    _ffmpeg("-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ac", "1", "-ar", str(TAXA), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3))


def duracao_s(arquivo: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(arquivo)],
                       capture_output=True, text=True)
    try:
        return round(float(json.loads(r.stdout)["format"]["duration"]), 2)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ErroTTS(f"não consegui medir a duração de {arquivo}") from exc

"""XTTS-v2 (coqui-tts, fork idiap) — vozes prontas ou clonagem; GPU recomendada.

Licença do modelo: Coqui Public Model License (uso não comercial) — ok para estudo.
API conferida no README oficial: TTS(model).to(device) e tts_to_file(text, speaker |
speaker_wav, language, file_path); vozes prontas em `tts.speakers`.
"""
from __future__ import annotations
from pathlib import Path

from .base import ErroTTS, versao_pacote

MODELO = "tts_models/multilingual/multi-dataset/xtts_v2"


class XttsEngine:
    nome = "xtts"
    clona = True
    exige_ref_text = False

    def __init__(self, cfg: dict):
        self.max_chars = int(cfg.get("max_chars", 230))
        self.idioma = cfg.get("idioma", "pt")
        self._tts = None

    def versao(self) -> str:
        return f"coqui-tts {versao_pacote('coqui-tts')} {MODELO}"

    def _modelo(self):
        if self._tts is None:
            try:
                import torch
                from TTS.api import TTS
            except ImportError as exc:
                raise ErroTTS("XTTS não instalado: pip install coqui-tts (e torch)") from exc
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tts = TTS(MODELO).to(device)
        return self._tts

    def vozes(self) -> list[str]:
        return list(getattr(self._modelo(), "speakers", None) or [])

    def sintetizar(self, texto: str, voz: str | None, ref_wav: str | None,
                   ref_text: str | None, saida: Path) -> None:
        tts = self._modelo()
        kwargs = {"text": texto, "language": self.idioma, "file_path": str(saida)}
        if ref_wav:
            kwargs["speaker_wav"] = ref_wav
        elif voz:
            kwargs["speaker"] = voz
        else:
            raise ErroTTS("xtts: defina voz.engines.xtts.<papel> (veja os nomes com tts.speakers) "
                          "ou um áudio de referência em voz.clone.<papel>.ref_wav.")
        tts.tts_to_file(**kwargs)

"""Chatterbox multilíngue (Resemble AI, MIT) — pt suportado; GPU recomendada.

API conferida no README oficial: ChatterboxMultilingualTTS.from_pretrained(device=...)
e .generate(text, language_id=...); salvar com torchaudio em model.sr. Tem UMA voz
padrão: sem áudio de referência, Professor e Aprendiz soam iguais. O README só
mostra `audio_prompt_path` no modelo em inglês — aqui ele só é passado se a
assinatura de `generate` o aceitar.
"""
from __future__ import annotations
import inspect
from pathlib import Path

from .base import ErroTTS, versao_pacote


class ChatterboxEngine:
    nome = "chatterbox"
    clona = True
    exige_ref_text = False

    def __init__(self, cfg: dict):
        self.max_chars = int(cfg.get("max_chars", 300))
        self.idioma = cfg.get("idioma", "pt")
        self._modelo_obj = None

    def versao(self) -> str:
        return f"chatterbox-tts {versao_pacote('chatterbox-tts')} multilingual"

    def _modelo(self):
        if self._modelo_obj is None:
            try:
                import torch
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            except ImportError as exc:
                raise ErroTTS("Chatterbox não instalado: pip install chatterbox-tts") from exc
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._modelo_obj = ChatterboxMultilingualTTS.from_pretrained(device=device)
        return self._modelo_obj

    def aceita_referencia(self) -> bool:
        return "audio_prompt_path" in inspect.signature(self._modelo().generate).parameters

    def sintetizar(self, texto: str, voz: str | None, ref_wav: str | None,
                   ref_text: str | None, saida: Path) -> None:
        import torchaudio

        modelo = self._modelo()
        kwargs = {"language_id": self.idioma}
        if ref_wav:
            if not self.aceita_referencia():
                raise ErroTTS("chatterbox: esta versão do modelo multilíngue não aceita audio_prompt_path.")
            kwargs["audio_prompt_path"] = ref_wav
        wav = modelo.generate(texto, **kwargs)
        torchaudio.save(str(saida), wav, modelo.sr, format="wav")

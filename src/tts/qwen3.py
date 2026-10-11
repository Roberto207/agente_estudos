"""Qwen3-TTS (QwenLM, Apache-2.0) — GPU obrigatória.

API conferida no README oficial: Qwen3TTSModel.from_pretrained(id, device_map, dtype);
CustomVoice: generate_custom_voice(text, language, speaker) -> (wavs, sr);
Base (clonagem): generate_voice_clone(text, language, ref_audio, ref_text).
As vozes prontas não são nativas em português (o README diz que cada voz rende
melhor na língua nativa) — o teste de vozes decide se presta. Na T4 (Kaggle/Colab)
não há bfloat16 rápido nem FlashAttention 2, então carrega em float16 com a
atenção padrão.
"""
from __future__ import annotations
from pathlib import Path

from .base import ErroTTS, versao_pacote


class Qwen3Engine:
    nome = "qwen3"
    clona = True
    exige_ref_text = True

    def __init__(self, cfg: dict):
        self.max_chars = int(cfg.get("max_chars", 400))
        self.id_modelo = cfg.get("modelo", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
        self.id_modelo_clone = cfg.get("modelo_clone", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
        self.idioma = cfg.get("idioma", "Portuguese")
        self._modelos: dict[str, object] = {}

    def versao(self) -> str:
        return f"qwen-tts {versao_pacote('qwen-tts')} {self.id_modelo}|{self.id_modelo_clone}"

    def _carregar(self, id_modelo: str):
        if id_modelo not in self._modelos:
            try:
                import torch
                from qwen_tts import Qwen3TTSModel
            except ImportError as exc:
                raise ErroTTS(f"Qwen3-TTS não pôde ser importado ({type(exc).__name__}: {exc}). "
                              "Instale com: pip install -U qwen-tts soundfile") from exc
            if not torch.cuda.is_available():
                raise ErroTTS("Qwen3-TTS precisa de GPU (cuda).")
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            self._modelos[id_modelo] = Qwen3TTSModel.from_pretrained(id_modelo, device_map="cuda:0", dtype=dtype)
        return self._modelos[id_modelo]

    def _idioma(self, modelo) -> str:
        """Confere a string de idioma com o próprio modelo (o README não mostra a de português)."""
        suportados = getattr(modelo, "get_supported_languages", lambda: [])() or []
        for s in suportados:
            if str(s).lower() == self.idioma.lower():
                return s
        return self.idioma if not suportados else "Auto"

    def sintetizar(self, texto: str, voz: str | None, ref_wav: str | None,
                   ref_text: str | None, saida: Path) -> None:
        import soundfile as sf

        if ref_wav:
            if not ref_text:
                raise ErroTTS("qwen3: a clonagem exige a transcrição do áudio (voz.clone.<papel>.ref_text).")
            modelo = self._carregar(self.id_modelo_clone)
            wavs, sr = modelo.generate_voice_clone(text=texto, language=self._idioma(modelo),
                                                   ref_audio=ref_wav, ref_text=ref_text)
        else:
            if not voz:
                raise ErroTTS("qwen3: defina voz.engines.qwen3.<papel> (veja get_supported_speakers()).")
            modelo = self._carregar(self.id_modelo)
            wavs, sr = modelo.generate_custom_voice(text=texto, language=self._idioma(modelo), speaker=voz)
        sf.write(str(saida), wavs[0], sr, format="WAV")

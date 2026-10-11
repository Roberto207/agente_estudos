"""edge-tts — vozes neurais do Edge (serviço da Microsoft, não oficial; sem GPU, sem chave).

Plano B do projeto: leve e com vozes pt-BR nativas, mas depende de rede e de um
serviço que pode mudar sem aviso. Não clona voz.
"""
from __future__ import annotations
import time
from pathlib import Path

from .base import ErroTTS, versao_pacote


class EdgeEngine:
    nome = "edge"
    clona = False
    exige_ref_text = False

    def __init__(self, cfg: dict):
        self.max_chars = int(cfg.get("max_chars", 3000))
        self.taxa = cfg.get("rate", "+0%")

    def versao(self) -> str:
        return f"edge-tts {versao_pacote('edge-tts')}"

    def sintetizar(self, texto: str, voz: str | None, ref_wav: str | None,
                   ref_text: str | None, saida: Path) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise ErroTTS("edge-tts não instalado: pip install edge-tts") from exc
        if not voz:
            raise ErroTTS("edge: voz não configurada para o papel (voz.engines.edge.<papel>).")
        ultimo: Exception | None = None
        for tentativa in range(3):  # o serviço falha de vez em quando; 3 tentativas com espera
            try:
                edge_tts.Communicate(texto, voz, rate=self.taxa).save_sync(str(saida))
                if saida.exists() and saida.stat().st_size > 0:
                    return
            except Exception as exc:  # erro de rede/serviço
                ultimo = exc
            time.sleep(2 * (tentativa + 1))
        raise ErroTTS(f"edge-tts falhou após 3 tentativas: {ultimo}")

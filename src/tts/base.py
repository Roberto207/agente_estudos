"""Interface comum dos motores de voz e configuração padrão (DESIGN §3 e §7)."""
from __future__ import annotations
from importlib import metadata
from pathlib import Path
from typing import Protocol

PAPEIS = ("Professor", "Aprendiz")


class ErroTTS(Exception):
    """Erro de configuração ou de síntese — a CLI mostra a mensagem e sai com código 1."""


class Engine(Protocol):
    nome: str
    clona: bool            # aceita áudio de referência (D10)
    exige_ref_text: bool   # clonagem precisa da transcrição da referência (qwen3)
    max_chars: int         # fala maior que isso é quebrada em frases antes da síntese

    def versao(self) -> str: ...

    def sintetizar(self, texto: str, voz: str | None, ref_wav: str | None,
                   ref_text: str | None, saida: Path) -> None:
        """Grava o áudio de `texto` em `saida` (qualquer formato que o ffmpeg leia).
        Usa `ref_wav` (clonagem) quando informado; senão, a voz fixa `voz`."""
        ...


DEFAULT_VOZ = {
    "engine": "edge",
    "engines": {
        "edge": {"professor": "pt-BR-AntonioNeural", "aprendiz": "pt-BR-FranciscaNeural", "max_chars": 3000},
        # Nomes de voz do XTTS: rode `tts.speakers` no notebook e escolha dois.
        "xtts": {"professor": None, "aprendiz": None, "max_chars": 230},
        # Chatterbox tem uma única voz padrão: sem clonagem, os dois papéis soam iguais.
        "chatterbox": {"max_chars": 300},
        "qwen3": {"modelo": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
                  "modelo_clone": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                  "idioma": "Portuguese", "professor": "Ryan", "aprendiz": "Serena", "max_chars": 400},
    },
    "clone": {"professor": {"ref_wav": None, "ref_text": None},
              "aprendiz": {"ref_wav": None, "ref_text": None}},
    "pausa_ms": {"fala": 250, "bloco": 700, "pedaco": 120},
    "teste": {"engines": ["edge"]},
    # Fora do vault: ~50 MB de WAV por episódio de 20 min não devem sincronizar com o
    # Obsidian. A chave é o conteúdo (motor, versão, voz, texto), então compartilhar
    # entre pastas é seguro — e falas repetidas entre séries viram cache.
    "cache_dir": "~/.cache/agente_estudos/tts",
}


def config_voz(config: dict) -> dict:
    """Mescla `voz:` do config com os padrões (um nível de profundidade por motor/papel)."""
    usuario = config.get("voz") or {}
    cfg = {**DEFAULT_VOZ, **{k: v for k, v in usuario.items() if k not in ("engines", "clone", "pausa_ms", "teste")}}
    cfg["engines"] = {nome: {**DEFAULT_VOZ["engines"].get(nome, {}), **(usuario.get("engines", {}).get(nome) or {})}
                      for nome in {*DEFAULT_VOZ["engines"], *(usuario.get("engines") or {})}}
    cfg["clone"] = {p: {**DEFAULT_VOZ["clone"][p], **((usuario.get("clone") or {}).get(p) or {})}
                    for p in ("professor", "aprendiz")}
    cfg["pausa_ms"] = {**DEFAULT_VOZ["pausa_ms"], **(usuario.get("pausa_ms") or {})}
    cfg["teste"] = {**DEFAULT_VOZ["teste"], **(usuario.get("teste") or {})}
    return cfg


def versao_pacote(pacote: str) -> str:
    try:
        return metadata.version(pacote)
    except metadata.PackageNotFoundError:
        return "?"

from __future__ import annotations
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def get_video_info(url: str) -> dict:
    """Retorna metadados do vídeo via yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--skip-download", url],
            capture_output=True, text=True, timeout=45,
        )
        if result.returncode == 0 and result.stdout.strip():
            info = json.loads(result.stdout.strip().splitlines()[0])
            return {
                "title": info.get("title", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "description": (info.get("description") or "")[:500],
            }
    except Exception:
        pass
    return {"title": url, "duration": 0, "uploader": "", "description": ""}


def get_youtube_transcript(url: str) -> str:
    """Baixa a transcrição/legenda do YouTube via yt-dlp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

        # Tenta legendas automáticas em pt/en
        for flags in (
            ["--write-auto-sub", "--sub-lang", "pt,pt-BR,en"],
            ["--write-sub", "--sub-lang", "pt,pt-BR,en"],
        ):
            subprocess.run(
                ["yt-dlp", *flags, "--skip-download", "--sub-format", "vtt", "-o", out_tmpl, url],
                capture_output=True, text=True, timeout=120,
            )
            vtt_files = list(Path(tmpdir).glob("*.vtt"))
            if vtt_files:
                return _parse_vtt(vtt_files[0].read_text(encoding="utf-8", errors="replace"))

        # Sem legendas disponíveis
        return ""


def transcribe_local_video(path: str, config: dict) -> str:
    """Transcreve vídeo local via Groq Whisper API ou whisper local."""
    tcfg = config.get("transcription", {})
    provider = tcfg.get("provider", "auto")

    groq_key = tcfg.get("groq_api_key") or config.get("groq", {}).get("api_key", "")

    if provider in ("auto", "groq") and groq_key:
        try:
            return _transcribe_groq(path, groq_key)
        except Exception as exc:
            if provider == "groq":
                return f"[Erro na transcrição Groq: {exc}]"

    if provider in ("auto", "local"):
        try:
            return _transcribe_local(path, tcfg.get("local_model", "base"))
        except Exception as exc:
            if provider == "local":
                return f"[Erro na transcrição local: {exc}]"

    return (
        "[Transcrição não disponível: configure transcription.provider em config.yaml "
        "com 'groq' (requer groq.api_key) ou 'local' (requer openai-whisper / faster-whisper)]"
    )


# ── Internos ──────────────────────────────────────────────────────────────────

def _transcribe_groq(path: str, api_key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=f,
            response_format="text",
        )
    return result if isinstance(result, str) else result.text


def _transcribe_local(path: str, model_name: str) -> str:
    try:
        import whisper
        model = whisper.load_model(model_name)
        return model.transcribe(path)["text"]
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_name)
        segments, _ = model.transcribe(path)
        return " ".join(s.text for s in segments)
    except ImportError:
        raise RuntimeError(
            "Instale openai-whisper ou faster-whisper para transcrição local: "
            "pip install openai-whisper"
        )


def _parse_vtt(vtt_text: str) -> str:
    """Converte VTT em texto plano sem duplicatas."""
    seen: set[str] = set()
    lines = []
    for ln in vtt_text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("WEBVTT") or ln.startswith("NOTE") or "-->" in ln:
            continue
        if re.match(r"^\d+$", ln):
            continue
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if ln and ln not in seen:
            seen.add(ln)
            lines.append(ln)
    return " ".join(lines)

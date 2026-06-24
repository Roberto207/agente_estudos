"""
Indexação semântica das pastas de estudo (RAG).

Funciona igual numa pasta de um tema único ou apontado pra raiz do vault inteiro —
a única diferença é quantos arquivos .md o rglob encontra. Cada pasta indexada
ganha um cache `.rag_index.json` com chunks + embeddings, atualizado incrementalmente
(só reembedda arquivos novos/alterados, com base no mtime).
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from typing import Any

import requests

_INDEX_FILENAME = ".rag_index.json"
_SKIP_NAMES = {"guia_de_estudos.md", "proximos_passos.md"}

_MAX_CHUNK_CHARS = 1500
_OVERLAP_CHARS = 150
_MIN_CHUNK_CHARS = 80

_HEADING_RE = re.compile(r"^#{1,3}[ \t]+.+$", re.MULTILINE)

_DEFAULT_MODELS = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "voyage": "voyage-3-lite",
}

_EMBED_BATCH_SIZE = 64


# ── Descoberta de arquivos ────────────────────────────────────────────────────

def _discover_md_files(pasta: Path) -> list[Path]:
    files = []
    for p in sorted(pasta.rglob("*.md")):
        if p.name in _SKIP_NAMES:
            continue
        if any(part.startswith(".") for part in p.relative_to(pasta).parts):
            continue
        files.append(p)
    return files


# ── Chunking ──────────────────────────────────────────────────────────────────

def _split_with_overlap(text: str) -> list[str]:
    """Divide texto longo em blocos de até _MAX_CHUNK_CHARS, com overlap entre blocos."""
    if len(text) <= _MAX_CHUNK_CHARS:
        return [text] if len(text.strip()) >= _MIN_CHUNK_CHARS else []

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > _MAX_CHUNK_CHARS and current:
            chunks.append(current)
            current = current[-_OVERLAP_CHARS:] + "\n\n" + para
        else:
            current = candidate
    if current.strip():
        chunks.append(current)
    return [c for c in chunks if len(c.strip()) >= _MIN_CHUNK_CHARS]


def chunk_markdown(text: str, file_relpath: str) -> list[dict]:
    """Divide um arquivo .md em chunks heading-aware (fallback: tamanho fixo)."""
    matches = list(_HEADING_RE.finditer(text))

    if not matches:
        body_chunks = _split_with_overlap(text)
        return [
            {"file": file_relpath, "heading": "", "text": c}
            for c in body_chunks
        ]

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if len(preamble) >= _MIN_CHUNK_CHARS:
            sections.append(("", preamble))

    for i, m in enumerate(matches):
        heading = m.group().strip().lstrip("#").strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end].strip()))

    chunks: list[dict] = []
    for heading, body in sections:
        for piece in _split_with_overlap(body):
            chunks.append({"file": file_relpath, "heading": heading, "text": piece})
    return chunks


# ── Embeddings ────────────────────────────────────────────────────────────────

class EmbeddingClient:
    """Cliente de embeddings unificado: ollama (local), openai, voyage."""

    def __init__(self, config: dict):
        embed_cfg = config.get("embedding", {}) or {}
        self.provider = embed_cfg.get("provider", "ollama")
        self.config = config
        self.embed_cfg = embed_cfg

    def model_name(self) -> str:
        cfg = self.embed_cfg.get(self.provider, {}) or {}
        return cfg.get("model", _DEFAULT_MODELS.get(self.provider, ""))

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            if self.provider == "ollama":
                vectors.extend(self._embed_ollama(batch))
            elif self.provider == "openai":
                vectors.extend(self._embed_openai(batch))
            elif self.provider == "voyage":
                vectors.extend(self._embed_voyage(batch))
            else:
                raise ValueError(f"Provider de embedding desconhecido: {self.provider}")
        return vectors

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        cfg = self.embed_cfg.get("ollama", {}) or {}
        base_url = cfg.get("base_url") or self.config.get("ollama", {}).get("base_url", "http://localhost:11434")
        model = cfg.get("model", _DEFAULT_MODELS["ollama"])
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/embed",
            json={"model": model, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        cfg = self.embed_cfg.get("openai", {}) or {}
        api_key = cfg.get("api_key") or self.config.get("openai", {}).get("api_key", "")
        model = cfg.get("model", _DEFAULT_MODELS["openai"])
        client = OpenAI(api_key=api_key)
        resp = client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in resp.data]

    def _embed_voyage(self, texts: list[str]) -> list[list[float]]:
        cfg = self.embed_cfg.get("voyage", {}) or {}
        api_key = cfg.get("api_key", "")
        model = cfg.get("model", _DEFAULT_MODELS["voyage"])
        resp = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in resp.json()["data"]]


# ── Similaridade (puro Python — escala de uma pasta de estudos não justifica numpy) ──

def _norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def _cosine(qvec: list[float], qnorm: float, vec: list[float], vnorm: float) -> float:
    if qnorm == 0 or vnorm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(qvec, vec))
    return dot / (qnorm * vnorm)


# ── Índice (cache incremental em disco) ───────────────────────────────────────

def _index_path(pasta: Path) -> Path:
    return pasta / _INDEX_FILENAME


def _load_index(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_index(path: Path, index: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f)


def build_or_update_index(pasta: Path, config: dict) -> dict:
    """Indexa (ou reaproveita/atualiza incrementalmente) os .md de uma pasta.

    Funciona tanto para uma pasta de um tema só quanto para a raiz do vault
    inteiro — o caminho relativo de cada chunk (file_relpath) já distingue a
    origem em qualquer escopo.
    """
    embedder = EmbeddingClient(config)
    provider = embedder.provider
    model = embedder.model_name()

    md_files = _discover_md_files(pasta)
    current_mtimes = {
        str(p.relative_to(pasta).as_posix()): p.stat().st_mtime for p in md_files
    }

    index_path = _index_path(pasta)
    stored = _load_index(index_path)
    if stored is not None and (
        stored.get("embedding_provider") != provider or stored.get("embedding_model") != model
    ):
        stored = None  # modelo/provider mudou — vetores antigos não são comparáveis

    old_mtimes: dict[str, float] = stored["file_mtimes"] if stored else {}
    old_chunks: list[dict] = stored["chunks"] if stored else []

    changed_files = {f for f, m in current_mtimes.items() if old_mtimes.get(f) != m}
    removed_files = set(old_mtimes) - set(current_mtimes)

    if not changed_files and not removed_files and stored is not None:
        return stored

    kept_chunks = [
        c for c in old_chunks if c["file"] not in changed_files and c["file"] not in removed_files
    ]

    new_meta: list[dict] = []
    for relpath in sorted(changed_files):
        text = (pasta / relpath).read_text(encoding="utf-8")
        new_meta.extend(chunk_markdown(text, relpath))

    new_chunks: list[dict] = []
    if new_meta:
        texts = [m["text"] for m in new_meta]
        vectors = embedder.embed_batch(texts)
        for meta, vec in zip(new_meta, vectors):
            # 6 decimais é precisão de sobra pra cosine e reduz ~3x o tamanho do JSON
            # (floats nativos da API vêm com ~17 dígitos significativos).
            rounded = [round(x, 6) for x in vec]
            new_chunks.append({
                "file": meta["file"],
                "heading": meta["heading"],
                "text": meta["text"],
                "embedding": rounded,
                "norm": _norm(rounded),
            })

    result = {
        "version": 1,
        "embedding_provider": provider,
        "embedding_model": model,
        "file_mtimes": current_mtimes,
        "chunks": kept_chunks + new_chunks,
    }
    _save_index(index_path, result)
    return result


def search(index: dict, query: str, embedder: EmbeddingClient, k: int = 5) -> list[dict[str, Any]]:
    """Busca os k chunks mais relevantes para a query (cosine, puro Python)."""
    chunks = index.get("chunks", [])
    if not chunks:
        return []

    [qvec] = embedder.embed_batch([query])
    qnorm = _norm(qvec)

    scored = [
        (_cosine(qvec, qnorm, c["embedding"], c["norm"]), c)
        for c in chunks
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    k = max(1, min(int(k or 5), 20))
    return [
        {"score": score, "file": c["file"], "heading": c["heading"], "text": c["text"]}
        for score, c in scored[:k]
    ]

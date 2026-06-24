"""App FastAPI do estudAI — novo ponto de entrada web, sem alterar main.py/buscar_fontes.py.

Uso: uvicorn web.app:app --reload
"""
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import chat, generation, sources, spaces

app = FastAPI(title="estudAI")

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(spaces.router)
app.include_router(generation.router)
app.include_router(sources.router)
app.include_router(chat.router)

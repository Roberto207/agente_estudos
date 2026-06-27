"""Modelos Pydantic dos payloads de request/response da API."""
from __future__ import annotations
from pydantic import BaseModel


class CreateSpaceRequest(BaseModel):
    nome: str
    parent: str = ""


class OpenSpaceRequest(BaseModel):
    path: str


class SpaceOut(BaseModel):
    space_id: str
    nome: str
    path: str
    tem_conteudo: bool
    total_arquivos: int
    ultima_modificacao: float


class FileNode(BaseModel):
    name: str
    path: str
    type: str
    ext: str = ""
    children: list["FileNode"] = []


class FileContentOut(BaseModel):
    path: str
    raw: str
    html: str | None = None


class OutputsToggle(BaseModel):
    canvas: bool = True
    html: bool = True
    flashcards: bool = True
    quiz: bool = True
    next_steps: bool = True
    mapa_mental: bool = True


class GenerateRequest(BaseModel):
    tema: str
    foco: str = ""
    didatica: str = ""
    fontes: list[str] = []
    outputs: OutputsToggle = OutputsToggle()


class DiscoverSourcesRequest(BaseModel):
    tema: str
    foco: str = ""
    max_per_camada: int = 5


class SaveFileRequest(BaseModel):
    path: str
    content: str


class CreateFileRequest(BaseModel):
    path: str


class CreateFolderRequest(BaseModel):
    path: str


class ChatRequest(BaseModel):
    message: str
    mode: str = "qa"
    history: list[dict] = []


class JobStatusOut(BaseModel):
    id: str
    kind: str
    status: str
    events: list[dict]
    result: dict | None = None
    error: str | None = None

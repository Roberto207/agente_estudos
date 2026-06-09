"""
Registro de ferramentas disponíveis para o agente.

Define os schemas no formato neutro e converte para Anthropic ou OpenAI.
O executor mapeia nome → função Python.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed

from .web import web_search as _web_search, fetch_url as _fetch_url
from .files import write_file, read_file, create_directory, list_directory


# ── Schemas das ferramentas ───────────────────────────────────────────────────

_TOOL_DEFS = [
    {
        "name": "web_search",
        "description": (
            "Pesquisa na web via DuckDuckGo. Use para encontrar informações sobre "
            "tópicos de estudo, definições, tutoriais, artigos e materiais complementares. "
            "Retorna lista de resultados com título, URL e snippet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query de busca em português ou inglês"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número máximo de resultados (padrão: 5)",
                    "default": 5
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Faz download e extrai texto limpo de uma URL (artigo, blog, documentação, paper). "
            "Use para obter conteúdo completo de fontes específicas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL completa para buscar"
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "transcribe_video",
        "description": (
            "Transcreve e sumariza um vídeo do YouTube ou arquivo local de vídeo. "
            "Retorna transcrição estruturada com resumo, conceitos-chave e tópicos principais. "
            "O resultado é salvo automaticamente em output_path."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "URL do YouTube (youtu.be/... ou youtube.com/watch?v=...) ou caminho local (.mp4, .mkv, etc)"
                },
                "output_path": {
                    "type": "string",
                    "description": "Caminho absoluto onde salvar o arquivo .md da transcrição"
                },
            },
            "required": ["source", "output_path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Escreve conteúdo em um arquivo (cria diretórios intermediários se necessário). "
            "Use para criar arquivos .md, .canvas, .html e outros arquivos de output."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho absoluto do arquivo"
                },
                "content": {
                    "type": "string",
                    "description": "Conteúdo do arquivo"
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Lê o conteúdo de um arquivo existente.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho absoluto do arquivo"
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "create_directory",
        "description": "Cria um diretório (e subdiretórios intermediários se necessário).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho absoluto do diretório"
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "Lista arquivos e subpastas em um diretório.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Caminho absoluto do diretório"
                },
            },
            "required": ["path"],
        },
    },
]


# ── Conversores de formato ────────────────────────────────────────────────────

def to_anthropic_tools() -> list[dict]:
    result = []
    for t in _TOOL_DEFS:
        result.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })
    return result


def to_openai_tools() -> list[dict]:
    result = []
    for t in _TOOL_DEFS:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        })
    return result


def get_tools_for_provider(provider: str) -> list[dict]:
    if provider == "anthropic":
        return to_anthropic_tools()
    return to_openai_tools()


# ── Executor ──────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict, config: dict) -> str:
    """Executa uma tool e retorna o resultado como string."""
    try:
        if name == "web_search":
            results = _web_search(inputs["query"], inputs.get("max_results", 5))
            if not results:
                return "[Nenhum resultado encontrado]"
            lines = []
            for r in results:
                lines.append(f"**{r['title']}**\n{r['url']}\n{r['snippet']}")
            return "\n\n---\n\n".join(lines)

        if name == "fetch_url":
            return _fetch_url(inputs["url"])

        if name == "transcribe_video":
            return _transcribe_video_tool(inputs["source"], inputs["output_path"], config)

        if name == "write_file":
            return write_file(inputs["path"], inputs["content"])

        if name == "read_file":
            return read_file(inputs["path"])

        if name == "create_directory":
            return create_directory(inputs["path"])

        if name == "list_directory":
            return list_directory(inputs["path"])

        return f"[Ferramenta desconhecida: {name}]"

    except Exception as exc:
        return f"[Erro ao executar {name}: {exc}]"


def execute_tools_batch(
    tool_calls: list[dict],
    config: dict,
    max_workers: int = 4,
) -> list[dict]:
    """
    Executa um lote de tool_calls.
    tool_calls: [{"id": ..., "name": ..., "inputs": {...}}]
    Retorna: [{"id": ..., "result": ...}]
    """
    results = [None] * len(tool_calls)

    def _run(i: int, tc: dict) -> tuple[int, str]:
        return i, execute_tool(tc["name"], tc["inputs"], config)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run, i, tc): i for i, tc in enumerate(tool_calls)}
        for fut in as_completed(futures):
            i, result = fut.result()
            results[i] = {"id": tool_calls[i]["id"], "result": result}

    return results


# ── Video transcription (encapsula distiller) ─────────────────────────────────

def _transcribe_video_tool(source: str, output_path: str, config: dict) -> str:
    from pathlib import Path as _Path
    from ..distiller import distill_source
    from ..llm import LLMClient

    llm = LLMClient(config)
    pasta = str(_Path(output_path).parent.parent)
    # Calcula índice a partir do nome do arquivo se possível
    try:
        idx = int(_Path(output_path).stem.split("_")[-1])
    except (ValueError, IndexError):
        idx = 1

    result_path = distill_source(source, pasta, idx, config, llm)
    return f"Transcrição salva em: {result_path}"

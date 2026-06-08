"""Gera arquivos .canvas para o Obsidian."""
from __future__ import annotations
import json
import os
from pathlib import Path


def write_canvas_files(pasta: str, tema: str, structure: dict) -> list[str]:
    """
    Cria dois canvas files: fundamentos e avançado.
    structure deve ter chave 'subfolders': lista de {name, files: [{name, title}]}
    """
    vault_prefix = _vault_relative_path(pasta)
    paths = []

    fundamentos_sf = [sf for sf in structure.get("subfolders", []) if "fund" in sf["name"].lower() or structure["subfolders"].index(sf) == 0]
    avancado_sf = [sf for sf in structure.get("subfolders", []) if sf not in fundamentos_sf]

    for label, subfolders, num in [
        ("fundamentos", fundamentos_sf or structure.get("subfolders", [])[:1], 1),
        ("avancado", avancado_sf or structure.get("subfolders", []), 2),
    ]:
        slug = tema.lower().replace(" ", "_")
        filename = f"{num}_{slug}_{label}.canvas"
        out_path = os.path.join(pasta, filename)
        canvas = _build_canvas(tema, label, subfolders, vault_prefix)
        Path(out_path).write_text(json.dumps(canvas, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.append(out_path)

    return paths


def _build_canvas(tema: str, label: str, subfolders: list[dict], vault_prefix: str) -> dict:
    nodes = []
    edges = []
    node_id = 0

    title_node = {
        "id": f"txt_title",
        "type": "text",
        "text": f"# {tema}\n## {label.capitalize()}\n\nFluxo de leitura: siga as setas →",
        "x": -300,
        "y": -250,
        "width": 340,
        "height": 140,
    }
    nodes.append(title_node)

    x_base = 100
    y_base = -400

    prev_group_id = None
    for gi, sf in enumerate(subfolders):
        group_id = f"grp_{gi}"
        group_node = {
            "id": group_id,
            "type": "group",
            "x": x_base + gi * 700,
            "y": y_base,
            "width": 580,
            "height": max(400, len(sf.get("files", [])) * 130 + 80),
            "label": sf["name"],
        }
        nodes.append(group_node)

        if prev_group_id:
            edges.append({
                "id": f"e_grp_{gi}",
                "fromNode": prev_group_id,
                "fromSide": "right",
                "toNode": group_id,
                "toSide": "left",
            })
        prev_group_id = group_id

        prev_file_id = None
        for fi, f in enumerate(sf.get("files", [])):
            file_node_id = f"file_{gi}_{fi}"
            file_path = f"{vault_prefix}/{sf['name']}/{f['name']}.md"
            file_node = {
                "id": file_node_id,
                "type": "file",
                "file": file_path,
                "x": x_base + gi * 700 + 20,
                "y": y_base + 60 + fi * 130,
                "width": 540,
                "height": 110,
            }
            nodes.append(file_node)

            if prev_file_id:
                edges.append({
                    "id": f"e_{gi}_{fi}",
                    "fromNode": prev_file_id,
                    "fromSide": "bottom",
                    "toNode": file_node_id,
                    "toSide": "top",
                })
            prev_file_id = file_node_id

    return {"nodes": nodes, "edges": edges}


def _vault_relative_path(pasta: str) -> str:
    """Tenta determinar o caminho relativo à raiz do vault Obsidian."""
    pasta = os.path.abspath(pasta)
    obsidian_markers = [".obsidian"]
    current = pasta
    for _ in range(6):
        parent = os.path.dirname(current)
        if any(os.path.isdir(os.path.join(parent, m)) for m in obsidian_markers):
            return os.path.relpath(pasta, parent)
        current = parent
    return os.path.basename(pasta)

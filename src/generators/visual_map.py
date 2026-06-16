"""Gera o HTML do mapa mental radial interativo para uma pasta de estudos."""
from __future__ import annotations
import math
import os
from pathlib import Path

_COLORS = [
    '#cba6f7',  # purple
    '#89b4fa',  # blue
    '#94e2d5',  # teal
    '#a6e3a1',  # green
    '#f9e2af',  # yellow
    '#fab387',  # peach
    '#f38ba8',  # red
    '#eba0ac',  # maroon
]

W, H = 1400, 900


def generate_visual_map(pasta: str, tema: str, structure: dict) -> str:
    """Gera <pasta>/visual_<slug>.html com mapa mental radial. Retorna o caminho."""
    slug = _slug(tema)
    html_content = _build_html(tema, structure)
    out_path = os.path.join(pasta, f"visual_{slug}.html")
    Path(out_path).write_text(html_content, encoding="utf-8")
    return out_path


def _slug(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", "_", s)


def _build_html(tema: str, structure: dict) -> str:
    cx, cy = W // 2, H // 2
    subfolders = [sf for sf in structure.get("subfolders", []) if sf.get("files")]
    n_sf = max(len(subfolders), 1)

    svg_edges: list[str] = []
    svg_nodes: list[str] = []

    # Central node
    svg_nodes.append(
        f'<g>'
        f'<circle cx="{cx}" cy="{cy}" r="68" fill="#181825" stroke="#cba6f7" stroke-width="3"/>'
        f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" dominant-baseline="middle" '
        f'fill="#cba6f7" font-size="13" font-weight="bold">{_esc(_wrap(tema, 16))}</text>'
        f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" dominant-baseline="middle" '
        f'fill="#a6adc8" font-size="9">Hub</text>'
        f'</g>'
    )

    R1 = min(W * 0.30, H * 0.32)

    for i, sf in enumerate(subfolders):
        color = _COLORS[i % len(_COLORS)]
        angle = (2 * math.pi / n_sf) * i - math.pi / 2
        sx = cx + R1 * math.cos(angle)
        sy = cy + R1 * math.sin(angle)

        # Gradient bezier edge: center → topic
        svg_edges.append(
            f'<line x1="{cx}" y1="{cy}" x2="{sx:.1f}" y2="{sy:.1f}" '
            f'stroke="{color}" stroke-width="2" opacity="0.45"/>'
        )

        # Topic node
        label = sf["name"].replace("_", " ").title()
        svg_nodes.append(
            f'<g>'
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="44" fill="#181825" stroke="{color}" stroke-width="2.5"/>'
            f'<text x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="{color}" font-size="11" font-weight="bold">{_esc(_wrap(label, 14))}</text>'
            f'</g>'
        )

        files = sf.get("files", [])
        n_files = len(files)
        if not n_files:
            continue

        # Scale R2 slightly with file count to reduce overlap
        R2 = 130 + max(0, (n_files - 3) * 8)
        arc = math.pi * 0.85 if n_files > 1 else 0

        for j, f in enumerate(files):
            if n_files == 1:
                sub_angle = angle
            else:
                sub_angle = angle - arc / 2 + (arc / (n_files - 1)) * j

            fx = sx + R2 * math.cos(sub_angle)
            fy = sy + R2 * math.sin(sub_angle)
            # Clamp to canvas bounds
            fx = max(70, min(W - 70, fx))
            fy = max(30, min(H - 30, fy))

            html_link = f'html/{sf["name"]}_{f["name"]}.html'
            title = f.get("title", f["name"])
            display = _wrap(title, 20)

            svg_edges.append(
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{fx:.1f}" y2="{fy:.1f}" '
                f'stroke="{color}" stroke-width="1.5" opacity="0.28"/>'
            )
            svg_nodes.append(
                f'<a href="{html_link}" target="_blank">'
                f'<g class="cnode">'
                f'<rect x="{fx - 56:.1f}" y="{fy - 20:.1f}" width="112" height="40" rx="8" '
                f'fill="#313244" stroke="{color}" stroke-width="1.5"/>'
                f'<text x="{fx:.1f}" y="{fy:.1f}" text-anchor="middle" dominant-baseline="middle" '
                f'fill="#cdd6f4" font-size="9.5">{_esc(display)}</text>'
                f'</g>'
                f'</a>'
            )

    edges_html = "\n    ".join(svg_edges)
    nodes_html = "\n    ".join(svg_nodes)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mapa Mental — {_esc(tema)}</title>
<style>
:root{{--base:#1e1e2e;--mantle:#181825;--surface0:#313244;--text:#cdd6f4;--subtext:#a6adc8;--purple:#cba6f7;--blue:#89b4fa;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--base);color:var(--text);display:flex;flex-direction:column;height:100vh;overflow:hidden;}}
header{{background:var(--mantle);padding:14px 28px;border-bottom:2px solid var(--purple);display:flex;align-items:center;gap:16px;flex-shrink:0;}}
header h1{{color:var(--purple);font-size:1.2rem;}}
header a{{color:var(--blue);text-decoration:none;font-size:.85rem;margin-left:auto;}}
header span{{color:var(--subtext);font-size:.78rem;margin-left:12px;}}
.wrap{{flex:1;overflow:hidden;position:relative;cursor:grab;}}
.wrap:active{{cursor:grabbing;}}
#canvas{{position:absolute;top:0;left:0;transform-origin:0 0;will-change:transform;}}
.cnode rect{{transition:fill .15s,stroke-width .15s;}}
.cnode:hover rect{{fill:#45475a;stroke-width:2.5;}}
.hint{{position:absolute;bottom:14px;right:14px;background:var(--mantle);color:var(--subtext);font-size:.72rem;padding:7px 12px;border-radius:8px;border:1px solid var(--surface0);pointer-events:none;}}
</style>
</head>
<body>
<header>
  <h1>🗺️ Mapa Mental — {_esc(tema)}</h1>
  <a href="html/index.html">← Hub de Estudos</a>
  <span>Scroll: zoom · Drag: mover · Click: abrir conceito</span>
</header>
<div class="wrap" id="wrap">
  <svg id="canvas" viewBox="0 0 {W} {H}" width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">
    <rect width="{W}" height="{H}" fill="#1e1e2e"/>
    {edges_html}
    {nodes_html}
  </svg>
</div>
<div class="hint">Scroll para zoom · Arraste para mover</div>
<script>
const wrap=document.getElementById('wrap');
const canvas=document.getElementById('canvas');
let scale=1,ox=0,oy=0,drag=false,startX,startY;
function applyT(){{canvas.style.transform=`translate(${{ox}}px,${{oy}}px) scale(${{scale}})`;}}
window.addEventListener('load',()=>{{
  const r=wrap.getBoundingClientRect();
  ox=(r.width-{W})/2; oy=(r.height-{H})/2; applyT();
}});
wrap.addEventListener('wheel',e=>{{
  e.preventDefault();
  const d=e.deltaY>0?0.9:1.1;
  const r=wrap.getBoundingClientRect();
  const mx=e.clientX-r.left,my=e.clientY-r.top;
  ox=mx-(mx-ox)*d; oy=my-(my-oy)*d;
  scale=Math.max(0.2,Math.min(5,scale*d));
  applyT();
}},{{passive:false}});
wrap.addEventListener('mousedown',e=>{{if(e.button)return;drag=true;startX=e.clientX-ox;startY=e.clientY-oy;}});
window.addEventListener('mousemove',e=>{{if(!drag)return;ox=e.clientX-startX;oy=e.clientY-startY;applyT();}});
window.addEventListener('mouseup',()=>drag=false);
// Touch support
wrap.addEventListener('touchstart',e=>{{const t=e.touches[0];drag=true;startX=t.clientX-ox;startY=t.clientY-oy;}},{{passive:true}});
wrap.addEventListener('touchmove',e=>{{if(!drag)return;e.preventDefault();const t=e.touches[0];ox=t.clientX-startX;oy=t.clientY-startY;applyT();}},{{passive:false}});
wrap.addEventListener('touchend',()=>drag=false);
</script>
</body>
</html>"""


def _wrap(text: str, max_len: int) -> str:
    """Trunca o texto para exibição no SVG."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

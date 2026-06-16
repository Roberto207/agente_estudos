"""Gera os arquivos HTML (Catppuccin Mocha) a partir dos .md criados."""
from __future__ import annotations
import os
import re
from datetime import date
from pathlib import Path


_CSS_ROOT = """
:root {
  --base:     #1e1e2e;
  --mantle:   #181825;
  --crust:    #11111b;
  --surface0: #313244;
  --surface1: #45475a;
  --overlay0: #6c7086;
  --text:     #cdd6f4;
  --subtext:  #a6adc8;
  --purple:   #cba6f7;
  --blue:     #89b4fa;
  --green:    #a6e3a1;
  --yellow:   #f9e2af;
  --red:      #f38ba8;
  --teal:     #94e2d5;
}
"""

_CSS_BASE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--base); color: var(--text); display: flex; flex-direction: column; min-height: 100vh; }
header { background: var(--mantle); padding: 14px 28px; border-bottom: 2px solid var(--purple); display: flex; align-items: center; gap: 16px; }
header h1 { color: var(--purple); font-size: 1.3rem; }
header a { color: var(--blue); text-decoration: none; margin-left: auto; font-size: 0.85rem; }
header span { color: var(--subtext); font-size: 0.85rem; }
.layout { display: flex; flex: 1; }
nav { width: 260px; background: var(--mantle); padding: 20px 16px; border-right: 1px solid var(--surface0); overflow-y: auto; flex-shrink: 0; }
nav h2 { color: var(--blue); font-size: 0.75rem; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 12px; }
nav .section { margin-bottom: 18px; }
nav .section-title { color: var(--subtext); font-size: 0.72rem; text-transform: uppercase; margin-bottom: 6px; padding-left: 4px; }
nav a { display: block; color: var(--text); text-decoration: none; padding: 6px 10px; border-radius: 6px; font-size: 0.88rem; margin-bottom: 2px; transition: background .15s; }
nav a:hover, nav a.active { background: var(--surface0); color: var(--purple); font-weight: 600; }
main { flex: 1; padding: 36px 48px; max-width: 900px; }
"""

_CSS_ARTICLE = """
article h1 { color: var(--purple); font-size: 1.8rem; margin-bottom: 8px; }
article h2 { color: var(--blue); font-size: 1.2rem; margin: 28px 0 10px; padding-left: 10px; border-left: 3px solid var(--blue); }
article h3 { color: var(--teal); font-size: 1rem; margin: 20px 0 8px; }
article p { line-height: 1.7; margin-bottom: 14px; color: var(--text); }
blockquote { background: var(--surface0); border-left: 4px solid var(--teal); border-radius: 0 8px 8px 0; padding: 12px 18px; margin: 16px 0; color: var(--subtext); font-style: italic; }
pre { background: var(--crust); border-radius: 8px; padding: 16px; overflow-x: auto; margin: 16px 0; }
code { color: var(--green); font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 0.9rem; }
p code, li code { background: var(--surface0); padding: 2px 6px; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th { background: var(--surface1); color: var(--purple); padding: 10px 14px; text-align: left; }
td { padding: 8px 14px; border-bottom: 1px solid var(--surface0); }
tr:nth-child(even) { background: var(--mantle); }
strong { color: var(--yellow); }
em { color: var(--subtext); }
ul, ol { padding-left: 20px; margin-bottom: 14px; }
li { margin-bottom: 4px; line-height: 1.6; }
li::marker { color: var(--purple); }
a { color: var(--blue); }
a:hover { color: var(--purple); }
.nav-footer { display: flex; justify-content: space-between; margin-top: 48px; padding-top: 20px; border-top: 1px solid var(--surface0); }
.nav-footer a { color: var(--blue); text-decoration: none; padding: 8px 16px; border-radius: 6px; background: var(--surface0); font-size: 0.88rem; }
.nav-footer a:hover { background: var(--surface1); }
"""

_CSS_INDEX = """
main h2 { color: var(--blue); margin-bottom: 20px; font-size: 1.5rem; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-top: 24px; }
.card { background: var(--surface0); border-radius: 10px; padding: 18px; border-left: 3px solid var(--purple); text-decoration: none; color: var(--text); transition: transform .15s, border-color .15s; display: block; }
.card:hover { transform: translateY(-2px); border-color: var(--blue); }
.card h3 { color: var(--purple); font-size: 0.95rem; margin-bottom: 6px; }
.card p { color: var(--subtext); font-size: 0.82rem; line-height: 1.5; }
.checkpoint { background: var(--surface0); border-left: 3px solid var(--yellow); border-radius: 8px; padding: 14px 18px; margin-top: 32px; color: var(--yellow); font-size: 0.9rem; }
.topic-intro { color: var(--subtext); margin-bottom: 24px; line-height: 1.6; }
.tools-row { display: flex; gap: 12px; margin-top: 28px; flex-wrap: wrap; }
.tool-card { background: var(--surface0); border-radius: 10px; padding: 14px 20px; border-left: 3px solid var(--teal); text-decoration: none; color: var(--text); display: flex; align-items: center; gap: 10px; font-size: 0.9rem; transition: transform .15s; }
.tool-card:hover { transform: translateY(-2px); border-color: var(--purple); }
.tool-card .icon { font-size: 1.4rem; }
.tool-card strong { color: var(--teal); display: block; font-size: 0.95rem; }
.tool-card span { color: var(--subtext); font-size: 0.8rem; }
"""

_CSS_DEPTH_TABS = """
.depth-tabs { margin: 20px 0 0; }
.depth-tabs input[type=radio] { display: none; }
.tab-labels { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--surface0); padding-bottom: 0; }
.tab-labels label { padding: 8px 18px; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 0.85rem; color: var(--subtext); border: 1px solid transparent; border-bottom: none; transition: background .15s, color .15s; margin-bottom: -1px; }
.tab-labels label:hover { color: var(--text); background: var(--surface0); }
#tab-rapido:checked   ~ .tab-labels label[for=tab-rapido],
#tab-medio:checked    ~ .tab-labels label[for=tab-medio],
#tab-completo:checked ~ .tab-labels label[for=tab-completo] {
  color: var(--purple); background: var(--surface0); border-color: var(--surface0); border-bottom-color: var(--surface0);
}
.depth-content > div { display: none; }
#tab-rapido:checked   ~ .depth-content .content-rapido   { display: block; }
#tab-medio:checked    ~ .depth-content .content-medio    { display: block; }
#tab-completo:checked ~ .depth-content .content-completo { display: block; }
"""


def generate_html_files(pasta: str, tema: str, foco: str, structure: dict) -> list[str]:
    """
    Gera index.html e um HTML por arquivo .md da estrutura.
    Retorna lista de caminhos gerados.
    """
    html_dir = os.path.join(pasta, "html")
    Path(html_dir).mkdir(parents=True, exist_ok=True)

    all_pages = _collect_pages(pasta, structure)
    tema_slug = _slug(tema)
    nav_html = _build_nav(tema, all_pages, tema_slug)

    generated = []

    for page in all_pages:
        md_path = page["md_path"]
        html_path = os.path.join(html_dir, page["html_name"])
        if os.path.exists(md_path):
            md_content = Path(md_path).read_text(encoding="utf-8")
            html = _render_concept_page(tema, page["title"], md_content, nav_html, page["html_name"])
            Path(html_path).write_text(html, encoding="utf-8")
            generated.append(html_path)

    index_path = os.path.join(html_dir, "index.html")
    index_html = _render_index(tema, foco, structure, all_pages, nav_html)
    Path(index_path).write_text(index_html, encoding="utf-8")
    generated.insert(0, index_path)

    return generated


# ── Helpers ───────────────────────────────────────────────────────────────────

def _collect_pages(pasta: str, structure: dict) -> list[dict]:
    pages = []
    for sf in structure.get("subfolders", []):
        sf_name = sf["name"]
        for f in sf.get("files", []):
            name = f["name"]
            title = f.get("title", name.replace("_", " ").title())
            md_path = os.path.join(pasta, sf_name, f"{name}.md")
            html_name = f"{sf_name}_{name}.html"
            pages.append({
                "subfolder": sf_name,
                "name": name,
                "title": title,
                "md_path": md_path,
                "html_name": html_name,
            })

    guia_path = os.path.join(pasta, "guia_de_estudos.md")
    if os.path.exists(guia_path):
        pages.append({
            "subfolder": "",
            "name": "guia_de_estudos",
            "title": "Guia de Estudos",
            "md_path": guia_path,
            "html_name": "guia_de_estudos.html",
        })
    return pages


def _slug(s: str) -> str:
    import re
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", "_", s)


def _build_nav(tema: str, pages: list[dict], tema_slug: str = "") -> str:
    by_sf: dict[str, list[dict]] = {}
    for p in pages:
        by_sf.setdefault(p["subfolder"] or "raiz", []).append(p)

    sections = [f'<a href="index.html">🏠 Início</a>']
    for sf, pgs in by_sf.items():
        label = sf.replace("_", " ").title() if sf != "raiz" else "Geral"
        sections.append(f'<div class="section"><div class="section-title">{label}</div>')
        for p in pgs:
            sections.append(f'<a href="{p["html_name"]}" data-page="{p["html_name"]}">{p["title"]}</a>')
        sections.append("</div>")

    if tema_slug:
        sections.append(
            f'<div class="section"><div class="section-title">Visual</div>'
            f'<a href="../visual_{tema_slug}.html">🗺️ Mapa Mental</a>'
            f'</div>'
        )

    return "\n".join(sections)


def _render_index(tema: str, foco: str, structure: dict, pages: list[dict], nav_html: str) -> str:
    cards = "\n".join(
        f'<a class="card" href="{p["html_name"]}"><h3>{p["title"]}</h3>'
        f'<p>{p["subfolder"].replace("_", " ").title() if p["subfolder"] else "Geral"}</p></a>'
        for p in pages[:12]
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(tema)} — Guia de Estudos</title>
  <style>{_CSS_ROOT}{_CSS_BASE}{_CSS_INDEX}</style>
</head>
<body>
  <header>
    <h1>📚 {_esc(tema)}</h1>
    <span>Gerado em {date.today().strftime("%d/%m/%Y")}</span>
  </header>
  <div class="layout">
    <nav>
      <h2>Navegação</h2>
      {nav_html}
      <div class="section">
        <div class="section-title">Ferramentas</div>
        <a href="flashcards.html">🃏 Flashcards</a>
        <a href="quiz.html">📝 Quiz</a>
      </div>
    </nav>
    <main>
      <h2>Guia de Estudos</h2>
      <p class="topic-intro">{_esc(foco)}</p>
      <div class="cards">
        {cards}
      </div>
      <div class="tools-row">
        <a class="tool-card" href="flashcards.html">
          <span class="icon">🃏</span>
          <div><strong>Flashcards</strong><span>Spaced repetition (SM-2)</span></div>
        </a>
        <a class="tool-card" href="quiz.html">
          <span class="icon">📝</span>
          <div><strong>Quiz</strong><span>Múltipla escolha com feedback</span></div>
        </a>
      </div>
      <div class="checkpoint">
        💡 Para começar: abra o arquivo <strong>Guia de Estudos</strong> na barra lateral
        e siga a ordem de leitura recomendada.
      </div>
      <footer style="margin-top:48px; color:var(--overlay0); font-size:0.8rem; border-top:1px solid var(--surface0); padding-top:16px;">
        {len(pages)} arquivos HTML gerados &nbsp;|&nbsp;
        Abrir hub: <code>file://{os.path.abspath(os.path.dirname(pages[0]["md_path"]) if pages else ".")}/html/index.html</code>
      </footer>
    </main>
  </div>
</body>
</html>"""


def _render_concept_page(tema: str, title: str, md_content: str, nav_html: str, current_html: str) -> str:
    active_nav = re.sub(
        rf'(href="{re.escape(current_html)}")',
        r'\1 class="active"',
        nav_html,
    )

    depth_sections = _split_depth_sections(md_content)
    if depth_sections:
        article_html = _render_depth_tabs(depth_sections, current_html)
        extra_css = _CSS_DEPTH_TABS
    else:
        article_html = _md_to_html(md_content, current_html)
        extra_css = ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(title)} — {_esc(tema)}</title>
  <style>{_CSS_ROOT}{_CSS_BASE}{_CSS_ARTICLE}{extra_css}</style>
</head>
<body>
  <header>
    <h1>📚 {_esc(tema)}</h1>
    <a href="index.html">← Índice</a>
  </header>
  <div class="layout">
    <nav>
      <h2>Navegação</h2>
      {active_nav}
      <div class="section">
        <div class="section-title">Ferramentas</div>
        <a href="flashcards.html">🃏 Flashcards</a>
        <a href="quiz.html">📝 Quiz</a>
      </div>
    </nav>
    <main>
      <article>{article_html}</article>
    </main>
  </div>
</body>
</html>"""


def _split_depth_sections(md: str) -> dict | None:
    """
    Se o .md tem ## TL;DR e ## Conteúdo Completo, retorna as seções separadas.
    Caso contrário retorna None (render normal).
    """
    tldr_m = re.search(r'^## TL;DR\s*$', md, re.MULTILINE)
    completo_m = re.search(r'^## Conteúdo Completo\s*$', md, re.MULTILINE)
    if not (tldr_m and completo_m):
        return None

    resumo_m = re.search(r'^## Resumo\b', md, re.MULTILINE)

    preamble = md[:tldr_m.start()]

    if resumo_m and resumo_m.start() > tldr_m.start():
        tldr_text = md[tldr_m.start():resumo_m.start()]
        if completo_m.start() > resumo_m.start():
            resumo_text = md[resumo_m.start():completo_m.start()]
        else:
            resumo_text = md[resumo_m.start():]
    else:
        tldr_text = md[tldr_m.start():completo_m.start()]
        resumo_text = ""

    completo_text = md[completo_m.start():]

    return {
        "preamble": preamble,
        "tldr": tldr_text,
        "resumo": resumo_text,
        "completo": completo_text,
    }


def _render_depth_tabs(sections: dict, current_html: str) -> str:
    """Renderiza o conteúdo com tabs CSS-only: Rápido / Médio / Completo."""
    preamble_html = _md_to_html(sections["preamble"], current_html)
    tldr_html = _md_to_html(sections["tldr"], current_html)
    resumo_html = _md_to_html(sections["resumo"] or sections["tldr"], current_html)
    completo_html = _md_to_html(sections["completo"], current_html)

    return f"""{preamble_html}
<div class="depth-tabs">
  <input type="radio" id="tab-rapido"   name="depth">
  <input type="radio" id="tab-medio"    name="depth">
  <input type="radio" id="tab-completo" name="depth" checked>
  <div class="tab-labels">
    <label for="tab-rapido">⚡ Rápido</label>
    <label for="tab-medio">📖 Médio</label>
    <label for="tab-completo">📚 Completo</label>
  </div>
  <div class="depth-content">
    <div class="content-rapido">{tldr_html}</div>
    <div class="content-medio">{resumo_html}</div>
    <div class="content-completo">{completo_html}</div>
  </div>
</div>"""


def _md_to_html(md: str, current_html: str) -> str:
    """Converte Markdown básico em HTML com o estilo Catppuccin Mocha."""
    lines = md.splitlines()
    html_lines = []
    in_code = False
    in_table = False
    code_buf: list[str] = []

    for line in lines:
        # Blocos de código
        if line.strip().startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                in_code = True
                html_lines.append("<pre><code>")
            continue
        if in_code:
            html_lines.append(_esc(line))
            continue

        # Tabelas
        if "|" in line and line.strip().startswith("|"):
            if not in_table:
                html_lines.append('<table><thead>' if "---" not in line else "")
                in_table = True
            if "---" in line:
                html_lines.append("</thead><tbody>")
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            tag = "th" if not any(h.endswith("</thead>") for h in html_lines[-3:]) else "td"
            html_lines.append("<tr>" + "".join(f"<{tag}>{_esc(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            html_lines.append("</tbody></table>")
            in_table = False

        # Cabeçalhos
        if line.startswith("# "):
            html_lines.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("#### "):
            html_lines.append(f"<h4>{_inline(line[5:])}</h4>")
        # Blockquote
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        # HR
        elif re.match(r"^[-*_]{3,}$", line.strip()):
            html_lines.append("<hr style='border:none; border-top:1px solid var(--surface0); margin:24px 0;'>")
        # Lista não-ordenada
        elif re.match(r"^[-*+] ", line):
            html_lines.append(f"<ul><li>{_inline(line[2:])}</li></ul>")
        # Lista ordenada
        elif re.match(r"^\d+\. ", line):
            html_lines.append(f"<ol><li>{_inline(re.sub(r'^\d+\. ', '', line))}</li></ol>")
        # Linha em branco
        elif line.strip() == "":
            html_lines.append("")
        # Parágrafo
        else:
            html_lines.append(f"<p>{_inline(line)}</p>")

    if in_table:
        html_lines.append("</tbody></table>")
    if in_code:
        html_lines.append("</code></pre>")

    # Colapsar listas consecutivas
    result = "\n".join(html_lines)
    result = re.sub(r"</ul>\s*<ul>", "\n", result)
    result = re.sub(r"</ol>\s*<ol>", "\n", result)
    return result


def _inline(text: str) -> str:
    """Converte inline markdown em HTML."""
    text = _esc(text)
    # Negrito
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Itálico
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Código inline
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Links normais
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Links Obsidian [[arquivo]]
    text = re.sub(r'\[\[([^\]]+)\]\]', lambda m: _obsidian_link(m.group(1)), text)
    # Imagens
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" style="max-width:100%; border-radius:8px; margin:12px 0;">', text)
    return text


def _obsidian_link(name: str) -> str:
    slug = name.lower().replace(" ", "_").replace("/", "_")
    return f'<a href="{slug}.html">{name}</a>'


def _esc(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

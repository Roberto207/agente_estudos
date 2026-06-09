"""Gera flashcards com spaced repetition (SM-2) como HTML autocontido."""
from __future__ import annotations
import json
import os
from pathlib import Path

from ..llm import LLMClient


def generate(llm: LLMClient, pasta: str) -> str | None:
    """
    Lê os .md da pasta, gera pares Q&A via LLM e escreve html/flashcards.html.
    Retorna o caminho do arquivo gerado ou None se não há conteúdo suficiente.
    """
    md_files = _collect_md_files(pasta)
    if not md_files:
        return None

    all_cards: list[dict] = []
    for md_path in md_files:
        content = Path(md_path).read_text(encoding="utf-8")
        if len(content.strip()) < 100:
            continue
        cards = _generate_cards_for_file(llm, md_path, content)
        all_cards.extend(cards)

    if not all_cards:
        return None

    html_dir = os.path.join(pasta, "html")
    Path(html_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(html_dir, "flashcards.html")
    Path(out_path).write_text(_render_html(all_cards), encoding="utf-8")
    return out_path


# ── Coleta e geração ───────────────────────────────────────────────────────────

def _collect_md_files(pasta: str) -> list[str]:
    skip = {"guia_de_estudos.md"}
    result = []
    for md in sorted(Path(pasta).rglob("*.md")):
        if md.name in skip or "transcripts" in md.parts:
            continue
        result.append(str(md))
    return result[:15]  # limitar tokens


def _generate_cards_for_file(llm: LLMClient, md_path: str, content: str) -> list[dict]:
    file_name = Path(md_path).stem
    prompt = f"""Leia o conteúdo abaixo e crie de 3 a 6 flashcards de estudo.

Arquivo: {file_name}

Conteúdo:
{content[:3000]}

Responda com JSON válido neste formato exato (array, sem texto extra):
[
  {{
    "pergunta": "Qual é o conceito de X?",
    "resposta": "Resposta completa e didática.",
    "fonte": "{file_name}"
  }}
]

Crie flashcards que testem compreensão real: conceituais, de aplicação e de comparação."""

    try:
        result = llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        if isinstance(result, list):
            return [
                c for c in result
                if isinstance(c, dict) and "pergunta" in c and "resposta" in c
            ]
    except Exception:
        pass
    return []


# ── Renderização HTML ──────────────────────────────────────────────────────────

def _render_html(cards: list[dict]) -> str:
    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flashcards — Spaced Repetition</title>
  <style>
    :root {{
      --base:#1e1e2e; --mantle:#181825; --crust:#11111b; --surface0:#313244;
      --surface1:#45475a; --overlay0:#6c7086; --text:#cdd6f4; --subtext:#a6adc8;
      --purple:#cba6f7; --blue:#89b4fa; --green:#a6e3a1; --yellow:#f9e2af;
      --red:#f38ba8; --teal:#94e2d5;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ font-family:'Segoe UI',system-ui,sans-serif; background:var(--base); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; }}
    header {{ width:100%; background:var(--mantle); padding:14px 28px; border-bottom:2px solid var(--purple); display:flex; align-items:center; justify-content:space-between; }}
    header h1 {{ color:var(--purple); font-size:1.2rem; }}
    header a {{ color:var(--blue); text-decoration:none; font-size:0.85rem; }}
    .container {{ width:100%; max-width:680px; padding:32px 16px; }}
    .progress-bar {{ background:var(--surface0); border-radius:8px; height:8px; margin-bottom:12px; overflow:hidden; }}
    .progress-fill {{ height:100%; background:var(--purple); border-radius:8px; transition:width 0.3s; }}
    .stats {{ display:flex; gap:20px; margin-bottom:24px; font-size:0.85rem; color:var(--subtext); }}
    .stats span {{ color:var(--text); font-weight:600; }}
    .scene {{ width:100%; height:320px; perspective:1000px; cursor:pointer; margin-bottom:20px; }}
    .card-inner {{ width:100%; height:100%; position:relative; transform-style:preserve-3d; transition:transform 0.5s; }}
    .card-inner.flipped {{ transform:rotateY(180deg); }}
    .card-face {{ position:absolute; width:100%; height:100%; backface-visibility:hidden; border-radius:16px; padding:32px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; }}
    .card-front {{ background:var(--surface0); border:2px solid var(--purple); }}
    .card-back {{ background:var(--mantle); border:2px solid var(--teal); transform:rotateY(180deg); }}
    .card-face .label {{ font-size:0.75rem; text-transform:uppercase; letter-spacing:.1em; margin-bottom:16px; }}
    .card-front .label {{ color:var(--purple); }}
    .card-back .label {{ color:var(--teal); }}
    .card-face .text {{ font-size:1.05rem; line-height:1.65; white-space:pre-wrap; }}
    .card-face .source {{ position:absolute; bottom:12px; right:16px; font-size:0.72rem; color:var(--overlay0); }}
    .hint {{ text-align:center; color:var(--overlay0); font-size:0.82rem; margin-bottom:20px; }}
    .buttons {{ display:flex; gap:12px; justify-content:center; }}
    .btn {{ padding:12px 22px; border:none; border-radius:10px; font-size:0.9rem; font-weight:600; cursor:pointer; transition:opacity .15s, transform .1s; }}
    .btn:hover {{ opacity:0.85; transform:translateY(-1px); }}
    .btn:active {{ transform:translateY(0); }}
    .btn-again {{ background:var(--red); color:var(--crust); }}
    .btn-hard  {{ background:var(--yellow); color:var(--crust); }}
    .btn-good  {{ background:var(--blue); color:var(--crust); }}
    .btn-easy  {{ background:var(--green); color:var(--crust); }}
    .review-btns {{ display:none; }}
    .done-screen {{ text-align:center; padding:48px 0; display:none; }}
    .done-screen h2 {{ color:var(--green); font-size:1.8rem; margin-bottom:12px; }}
    .done-screen p {{ color:var(--subtext); margin-bottom:24px; }}
    .done-screen .btn-restart {{ background:var(--purple); color:var(--crust); }}
  </style>
</head>
<body>
  <header>
    <h1>🃏 Flashcards — Spaced Repetition</h1>
    <a href="index.html">← Voltar ao índice</a>
  </header>
  <div class="container">
    <div class="progress-bar"><div class="progress-fill" id="prog"></div></div>
    <div class="stats">
      Card <span id="cur">1</span> de <span id="tot">0</span> &nbsp;|&nbsp;
      Pendentes hoje: <span id="due-count">0</span>
    </div>

    <div id="main-area">
      <div class="scene" id="scene" onclick="flipCard()">
        <div class="card-inner" id="card-inner">
          <div class="card-face card-front">
            <div class="label">Pergunta</div>
            <div class="text" id="q-text"></div>
            <div class="source" id="q-source"></div>
          </div>
          <div class="card-face card-back">
            <div class="label">Resposta</div>
            <div class="text" id="a-text"></div>
          </div>
        </div>
      </div>
      <p class="hint" id="flip-hint">Clique no card para ver a resposta</p>
      <div class="buttons review-btns" id="review-btns">
        <button class="btn btn-again" onclick="rate(1)">😓 Difícil</button>
        <button class="btn btn-hard"  onclick="rate(2)">🤔 Médio</button>
        <button class="btn btn-good"  onclick="rate(3)">😊 Bom</button>
        <button class="btn btn-easy"  onclick="rate(4)">🌟 Fácil</button>
      </div>
    </div>

    <div class="done-screen" id="done-screen">
      <h2>🎉 Sessão Concluída!</h2>
      <p>Você revisou todos os cards de hoje.</p>
      <button class="btn btn-restart done-screen" onclick="restart()">Revisar tudo novamente</button>
    </div>
  </div>

  <script>
    const ALL_CARDS = {cards_json};
    const STORE_KEY = 'fc_srs_' + location.pathname;

    const today = () => new Date().toISOString().split('T')[0];

    function loadState() {{
      try {{ return JSON.parse(localStorage.getItem(STORE_KEY) || 'null'); }} catch {{ return null; }}
    }}
    function saveState(s) {{ localStorage.setItem(STORE_KEY, JSON.stringify(s)); }}

    function initState() {{
      const saved = loadState();
      if (saved && saved.cards && saved.cards.length === ALL_CARDS.length) return saved;
      return {{
        cards: ALL_CARDS.map((_, i) => ({{
          id: i, ef: 2.5, interval: 0, reps: 0, due: today(),
        }})),
      }};
    }}

    function sm2(card, grade) {{
      const q = [0, 3, 3, 4, 5][grade];
      if (q < 3) {{ card.reps = 0; card.interval = 1; }}
      else {{
        if (card.reps === 0)      card.interval = 1;
        else if (card.reps === 1) card.interval = 6;
        else                      card.interval = Math.round(card.interval * card.ef);
        card.reps++;
      }}
      card.ef = Math.max(1.3, card.ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02));
      const d = new Date();
      d.setDate(d.getDate() + card.interval);
      card.due = d.toISOString().split('T')[0];
      return card;
    }}

    let state = initState();
    let dueCards = [];
    let currentIdx = 0;
    let flipped = false;

    function getDue() {{ return state.cards.filter(c => c.due <= today()); }}

    function render() {{
      dueCards = getDue();
      if (!dueCards.length) {{ showDone(); return; }}
      if (currentIdx >= dueCards.length) currentIdx = 0;
      const ci = dueCards[currentIdx];
      const card = ALL_CARDS[ci.id];
      document.getElementById('q-text').textContent = card.pergunta;
      document.getElementById('a-text').textContent = card.resposta;
      document.getElementById('q-source').textContent = card.fonte || '';
      document.getElementById('cur').textContent = currentIdx + 1;
      document.getElementById('tot').textContent = dueCards.length;
      document.getElementById('due-count').textContent = dueCards.length;
      document.getElementById('prog').style.width = Math.round(currentIdx / Math.max(dueCards.length, 1) * 100) + '%';
      flipped = false;
      document.getElementById('card-inner').classList.remove('flipped');
      document.getElementById('flip-hint').style.display = 'block';
      document.getElementById('review-btns').style.display = 'none';
    }}

    function flipCard() {{
      if (flipped) return;
      flipped = true;
      document.getElementById('card-inner').classList.add('flipped');
      document.getElementById('flip-hint').style.display = 'none';
      document.getElementById('review-btns').style.display = 'flex';
    }}

    function rate(grade) {{
      const ci = dueCards[currentIdx];
      sm2(ci, grade);
      state.cards[ci.id] = ci;
      saveState(state);
      currentIdx++;
      render();
    }}

    function showDone() {{
      document.getElementById('main-area').style.display = 'none';
      document.getElementById('done-screen').style.display = 'block';
    }}

    function restart() {{
      state.cards.forEach(c => {{ c.due = today(); }});
      saveState(state);
      currentIdx = 0;
      document.getElementById('main-area').style.display = 'block';
      document.getElementById('done-screen').style.display = 'none';
      render();
    }}

    render();
  </script>
</body>
</html>"""

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
    # `</` escapado pra um card com "</script>" não fechar o bloco de script.
    cards_json = json.dumps(cards, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__CARDS_JSON__", cards_json)


# Template com placeholder em vez de f-string: o JS usa muitas chaves e
# template literals, e duplicá-las todas ({{ }}) era fonte fácil de erro.
#
# Sessão: fila embaralhada e CONGELADA no início (pendentes hoje, ou todos os
# cards) — avaliar um card não recalcula a fila, então nenhum card é pulado.
# Grade 1..N e "ir para" permitem pular para qualquer card. O estado SM-2 é
# indexado por um id estável (hash da pergunta), não pela posição do card.
_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Flashcards — Spaced Repetition</title>
  <style>
    :root {
      --base:#1e1e2e; --mantle:#181825; --crust:#11111b; --surface0:#313244;
      --surface1:#45475a; --overlay0:#6c7086; --text:#cdd6f4; --subtext:#a6adc8;
      --purple:#cba6f7; --blue:#89b4fa; --green:#a6e3a1; --yellow:#f9e2af;
      --red:#f38ba8; --teal:#94e2d5;
    }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:'Segoe UI',system-ui,sans-serif; background:var(--base); color:var(--text); min-height:100vh; display:flex; flex-direction:column; align-items:center; }
    header { width:100%; background:var(--mantle); padding:14px 28px; border-bottom:2px solid var(--purple); display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
    header h1 { color:var(--purple); font-size:1.2rem; }
    .container { width:100%; max-width:680px; padding:24px 16px 32px; }
    .toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:14px; font-size:0.82rem; color:var(--subtext); }
    .toolbar input { width:70px; background:var(--mantle); border:1px solid var(--surface1); color:var(--text); border-radius:6px; padding:6px 8px; font-size:0.85rem; }
    .toolbar select { background:var(--mantle); border:1px solid var(--surface1); color:var(--text); border-radius:6px; padding:6px 8px; font-size:0.82rem; }
    .btn-sm { padding:6px 12px; border:1px solid var(--surface1); background:var(--surface0); color:var(--text); border-radius:6px; font-size:0.82rem; cursor:pointer; }
    .btn-sm:hover { border-color:var(--blue); }
    .grid { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; max-height:120px; overflow-y:auto; scrollbar-color:var(--surface1) var(--mantle); }
    .grid button { width:34px; height:30px; border-radius:6px; border:1px solid var(--surface1); background:var(--mantle); color:var(--subtext); font-size:0.78rem; cursor:pointer; }
    .grid button.done { border-color:var(--green); color:var(--green); }
    .grid button.cur { background:var(--purple); color:var(--crust); border-color:var(--purple); font-weight:700; }
    .progress-bar { background:var(--surface0); border-radius:8px; height:8px; margin-bottom:12px; overflow:hidden; }
    .progress-fill { height:100%; background:var(--purple); border-radius:8px; transition:width 0.3s; }
    .stats { display:flex; gap:20px; margin-bottom:20px; font-size:0.85rem; color:var(--subtext); flex-wrap:wrap; }
    .stats span { color:var(--text); font-weight:600; }
    .scene { width:100%; height:320px; perspective:1000px; cursor:pointer; margin-bottom:20px; }
    .card-inner { width:100%; height:100%; position:relative; transform-style:preserve-3d; transition:transform 0.5s; }
    .card-inner.flipped { transform:rotateY(180deg); }
    .card-face { position:absolute; width:100%; height:100%; backface-visibility:hidden; border-radius:16px; padding:32px; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; overflow-y:auto; }
    .card-front { background:var(--surface0); border:2px solid var(--purple); }
    .card-back { background:var(--mantle); border:2px solid var(--teal); transform:rotateY(180deg); }
    .card-face .label { font-size:0.75rem; text-transform:uppercase; letter-spacing:.1em; margin-bottom:16px; }
    .card-front .label { color:var(--purple); }
    .card-back .label { color:var(--teal); }
    .card-face .text { font-size:1.05rem; line-height:1.65; white-space:pre-wrap; }
    .card-face .source { position:absolute; bottom:12px; right:16px; font-size:0.72rem; color:var(--overlay0); }
    .hint { text-align:center; color:var(--overlay0); font-size:0.82rem; margin-bottom:20px; }
    .buttons { display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }
    .btn { padding:12px 22px; border:none; border-radius:10px; font-size:0.9rem; font-weight:600; cursor:pointer; transition:opacity .15s, transform .1s; }
    .btn:hover { opacity:0.85; transform:translateY(-1px); }
    .btn:active { transform:translateY(0); }
    .btn:disabled { opacity:0.35; cursor:default; transform:none; }
    .btn-again { background:var(--red); color:var(--crust); }
    .btn-hard  { background:var(--yellow); color:var(--crust); }
    .btn-good  { background:var(--blue); color:var(--crust); }
    .btn-easy  { background:var(--green); color:var(--crust); }
    .btn-nav   { background:var(--surface1); color:var(--text); padding:8px 16px; font-size:0.82rem; }
    .btn-restart { background:var(--purple); color:var(--crust); }
    .review-btns { display:none; }
    .nav-row { display:flex; justify-content:space-between; margin-top:16px; }
    .done-screen { text-align:center; padding:48px 0; display:none; }
    .done-screen h2 { color:var(--green); font-size:1.8rem; margin-bottom:12px; }
    .done-screen p { color:var(--subtext); margin-bottom:24px; }
  </style>
</head>
<body>
  <header>
    <h1>🃏 Flashcards — Spaced Repetition</h1>
    <button class="btn-sm" onclick="startSession(mode)" title="Nova ordem aleatória para a sessão">🔀 Reembaralhar</button>
  </header>
  <div class="container">
    <div class="toolbar">
      <select id="mode" onchange="startSession(this.value)">
        <option value="due">Pendentes hoje (SM-2)</option>
        <option value="all">Todos os cards</option>
      </select>
      <label for="goto">Ir para card</label>
      <input id="goto" type="number" min="1" onkeydown="if(event.key==='Enter')gotoInput()">
      <button class="btn-sm" onclick="gotoInput()">Ir</button>
    </div>

    <div id="main-area">
      <div class="grid" id="grid"></div>
      <div class="progress-bar"><div class="progress-fill" id="prog"></div></div>
      <div class="stats">
        <div>Card <span id="cur">1</span> de <span id="tot">0</span></div>
        <div>Avaliados na sessão: <span id="rated">0</span></div>
        <div>Pendentes hoje: <span id="due-count">0</span></div>
      </div>
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
      <div class="nav-row">
        <button class="btn btn-nav" id="btn-prev" onclick="go(pos - 1)">← Anterior</button>
        <button class="btn btn-nav" id="btn-next" onclick="go(pos + 1)">Pular →</button>
      </div>
    </div>

    <div class="done-screen" id="done-screen">
      <h2 id="done-title">🎉 Sessão Concluída!</h2>
      <p id="done-msg">Você revisou todos os cards de hoje.</p>
      <button class="btn btn-restart" onclick="startSession('all')">Estudar todos os cards</button>
    </div>
  </div>

  <script>
    const ALL_CARDS = __CARDS_JSON__;
    const STORE_KEY = 'fc_srs_' + location.pathname;

    const today = () => new Date().toISOString().split('T')[0];

    // Id estável por conteúdo: reordenar/regerar cards não troca o histórico
    // SM-2 de um card pelo de outro (antes o estado era indexado pela posição).
    function hashId(s) {
      let h = 5381;
      for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
      return 'c' + (h >>> 0).toString(36);
    }
    const IDS = ALL_CARDS.map(c => hashId(String(c.pergunta)));

    function loadState() {
      try { return JSON.parse(localStorage.getItem(STORE_KEY) || 'null'); } catch { return null; }
    }
    function saveState() {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch {}
    }

    function initState() {
      const saved = loadState();
      const srs = (saved && saved.srs) || {};
      // Migração do formato antigo ({cards:[{id: índice, ...}]}), que só era
      // válido enquanto a quantidade de cards não mudasse.
      if (saved && Array.isArray(saved.cards) && saved.cards.length === ALL_CARDS.length) {
        saved.cards.forEach((c, i) => {
          srs[IDS[i]] = { ef: c.ef, interval: c.interval, reps: c.reps, due: c.due };
        });
      }
      IDS.forEach(id => {
        if (!srs[id]) srs[id] = { ef: 2.5, interval: 0, reps: 0, due: today() };
      });
      return { srs };
    }

    function sm2(card, grade) {
      const q = [0, 3, 3, 4, 5][grade];
      if (q < 3) { card.reps = 0; card.interval = 1; }
      else {
        if (card.reps === 0)      card.interval = 1;
        else if (card.reps === 1) card.interval = 6;
        else                      card.interval = Math.round(card.interval * card.ef);
        card.reps++;
      }
      card.ef = Math.max(1.3, card.ef + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02));
      const d = new Date();
      d.setDate(d.getDate() + card.interval);
      card.due = d.toISOString().split('T')[0];
      return card;
    }

    function shuffle(a) {
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    }

    let state = initState();
    saveState();
    let mode = 'due';
    let queue = [];         // índices em ALL_CARDS, congelados na sessão
    let rated = new Set();  // posições da fila já avaliadas nesta sessão
    let pos = 0;
    let flipped = false;

    function dueCount() { return IDS.filter(id => state.srs[id].due <= today()).length; }

    function startSession(m) {
      mode = m;
      document.getElementById('mode').value = m;
      const idx = ALL_CARDS.map((_, i) => i);
      queue = shuffle(m === 'all' ? idx : idx.filter(i => state.srs[IDS[i]].due <= today()));
      rated = new Set();
      pos = 0;
      if (!queue.length) { showDone(); return; }
      document.getElementById('main-area').style.display = 'block';
      document.getElementById('done-screen').style.display = 'none';
      render();
    }

    function renderGrid() {
      document.getElementById('grid').innerHTML = queue.map((_, i) => {
        let cls = rated.has(i) ? 'done' : '';
        if (i === pos) cls += ' cur';
        return `<button class="${cls}" onclick="go(${i})">${i + 1}</button>`;
      }).join('');
    }

    function render() {
      const card = ALL_CARDS[queue[pos]];
      renderGrid();
      document.getElementById('q-text').textContent = card.pergunta;
      document.getElementById('a-text').textContent = card.resposta;
      document.getElementById('q-source').textContent = card.fonte || '';
      document.getElementById('cur').textContent = pos + 1;
      document.getElementById('tot').textContent = queue.length;
      document.getElementById('rated').textContent = rated.size;
      document.getElementById('due-count').textContent = dueCount();
      document.getElementById('prog').style.width = Math.round(rated.size / queue.length * 100) + '%';
      document.getElementById('btn-prev').disabled = pos === 0;
      document.getElementById('btn-next').disabled = pos === queue.length - 1;
      flipped = false;
      document.getElementById('card-inner').classList.remove('flipped');
      document.getElementById('flip-hint').style.display = 'block';
      document.getElementById('review-btns').style.display = 'none';
    }

    function flipCard() {
      if (flipped) return;
      flipped = true;
      document.getElementById('card-inner').classList.add('flipped');
      document.getElementById('flip-hint').style.display = 'none';
      document.getElementById('review-btns').style.display = 'flex';
    }

    function rate(grade) {
      sm2(state.srs[IDS[queue[pos]]], grade);
      saveState();
      rated.add(pos);
      if (rated.size === queue.length) { showDone(); return; }
      // Próximo card ainda não avaliado (circular), sem recalcular a fila.
      let next = pos;
      do { next = (next + 1) % queue.length; } while (rated.has(next));
      pos = next;
      render();
    }

    function go(i) {
      if (i < 0 || i >= queue.length) return;
      pos = i;
      render();
    }

    function gotoInput() {
      const v = parseInt(document.getElementById('goto').value, 10);
      if (!isNaN(v)) go(v - 1);
    }

    function showDone() {
      const pend = dueCount();
      document.getElementById('done-msg').textContent = mode === 'all'
        ? 'Você passou por todos os cards.'
        : (pend ? `Ainda há ${pend} card(s) pendente(s) hoje.` : 'Você revisou todos os cards de hoje.');
      document.getElementById('main-area').style.display = 'none';
      document.getElementById('done-screen').style.display = 'block';
    }

    startSession('due');
  </script>
</body>
</html>"""


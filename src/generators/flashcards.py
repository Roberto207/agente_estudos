"""Flashcards (SM-2) em dois passos, com revisão humana no meio.

    propor(llm, pasta)  -> <pasta>/flashcards_propostos.md   (o usuário aprova no Obsidian)
    montar(pasta)       -> <pasta>/html/flashcards.html      (só os aprovados)

As regras de qualidade vivem em prompts/flashcards_regras.md (fonte única, lida
também pelo agente Claude criar-estudo). O formato da lista, o parser e o lint
ficam em flashcards_lista.py, sem LLM.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

from ..llm import LLMClient
from . import flashcards_lista as lista

_REGRAS = Path(__file__).resolve().parents[2] / "prompts" / "flashcards_regras.md"

_ARQUIVOS_IGNORADOS = {"guia_de_estudos.md", lista.NOME_ARQUIVO}
_TLDR_MAX = 1800        # caracteres do TL;DR de cada arquivo
_MAPA_MAX = 6000        # caracteres do mapa da pasta
_CONCEITOS_MAX = 4000   # caracteres do arquivo de conceitos para dominar
_ALVO_POR_CHAMADA = (30, 50)


def regras() -> str:
    if not _REGRAS.exists():
        raise FileNotFoundError(f"Regras dos flashcards ausentes: {_REGRAS}")
    texto = _REGRAS.read_text(encoding="utf-8")
    return re.sub(r"\A\s*<!--.*?-->\s*", "", texto, count=1, flags=re.S)


# ── Passo 1: propor ───────────────────────────────────────────────────────────

def propor(llm: LLMClient, pasta: str, regerar: bool = False) -> lista.Relatorio | None:
    """Gera a lista de cards propostos pelo LLM do config e grava flashcards_propostos.md.

    Retorna o relatório do lint, ou None se a pasta não tem conteúdo suficiente.
    """
    material = _coletar_material(pasta)
    if not material["arquivos"]:
        return None

    prompt = _montar_prompt(material)
    resposta = llm.chat_json(
        messages=[{"role": "user", "content": prompt}],
        system=regras(),
        max_tokens=8192,
    )  # erro de LLM/JSON propaga: o chamador mostra o motivo real em vez de engolir
    if not isinstance(resposta, list):
        raise ValueError("o LLM não devolveu uma lista JSON de flashcards")

    cards = [
        lista.Card(
            pergunta=str(c.get("pergunta", "")).strip(),
            resposta=str(c.get("resposta", "")).strip(),
            fonte=str(c.get("fonte", "")).strip(),
            secao=str(c.get("secao", "")).strip(),
            termos=_ler_termos(c.get("termos")),
        )
        for c in resposta if isinstance(c, dict)
    ]
    return lista.gravar_lista(pasta, cards, titulo=Path(pasta).name, regerar=regerar)


def _ler_termos(bruto) -> list[lista.Termo]:
    """Subcards (termo + explicação) vindos do JSON do LLM; entradas malformadas são ignoradas."""
    if not isinstance(bruto, list):
        return []
    termos = []
    for t in bruto:
        if isinstance(t, dict) and str(t.get("termo", "")).strip() and str(t.get("explicacao", "")).strip():
            termos.append(lista.Termo(str(t["termo"]).strip().strip("`"), str(t["explicacao"]).strip()))
    return termos


def _coletar_material(pasta: str) -> dict:
    raiz = Path(pasta)
    mapa = ""
    for nome in ("00_contexto_e_mapa.md",):
        for cand in sorted(raiz.rglob(nome)):
            mapa += cand.read_text(encoding="utf-8")[:_MAPA_MAX] + "\n\n"
    conceitos = ""
    for cand in sorted(raiz.rglob("*conceitos_para_dominar*.md")):
        conceitos += cand.read_text(encoding="utf-8")[:_CONCEITOS_MAX] + "\n\n"

    arquivos = []
    for md in sorted(raiz.rglob("*.md")):
        if md.name in _ARQUIVOS_IGNORADOS or "transcripts" in md.parts or md.name.startswith("00_contexto"):
            continue
        if any(part.startswith(".") for part in md.relative_to(raiz).parts):
            continue
        texto = md.read_text(encoding="utf-8")
        if len(texto.strip()) < 100:
            continue
        arquivos.append({
            "nome": md.stem,
            "secao": md.parent.name if md.parent != raiz else raiz.name,
            "tldr": _tldr(texto),
        })
    return {"mapa": mapa.strip(), "conceitos": conceitos.strip(), "arquivos": arquivos}


def _tldr(texto: str) -> str:
    m = re.search(r"^## TL;DR\s*\n(.*?)(?=^## |\Z)", texto, re.S | re.M)
    trecho = m.group(1) if m else texto
    return trecho.strip()[:_TLDR_MAX]


def _montar_prompt(material: dict) -> str:
    lo, hi = _ALVO_POR_CHAMADA
    partes = [f"Crie de {lo} a {hi} flashcards seguindo as regras do sistema."]
    if material["mapa"]:
        partes.append("## Mapa da pasta (fluxo principal)\n" + material["mapa"])
    if material["conceitos"]:
        partes.append("## Conceitos para dominar\n" + material["conceitos"])
    partes.append("## TL;DR de cada arquivo")
    for a in material["arquivos"]:
        partes.append(f"### {a['nome']} (pasta: {a['secao']})\n{a['tldr']}")
    partes.append(
        "Responda só com um array JSON, sem texto extra, neste formato:\n"
        '[{"pergunta": "...", "resposta": "...", "fonte": "[[nome_do_arquivo]]", "secao": "nome da pasta", '
        '"termos": [{"termo": "símbolo ou termo como aparece no card", "explicacao": "o que é, em 1 a 3 frases"}]}]'
        "\nCada símbolo de equação e cada termo técnico usado na pergunta ou na resposta precisa de um item em \"termos\"."
    )
    return "\n\n".join(partes)


# ── Passo 2: montar ───────────────────────────────────────────────────────────

def montar(pasta: str, aprovar_todos: bool = False) -> str:
    """Lê flashcards_propostos.md e escreve html/flashcards.html só com os aprovados.

    Levanta FileNotFoundError se não há lista e ValueError se nada foi aprovado.
    """
    if not (Path(pasta) / lista.NOME_ARQUIVO).exists():
        raise FileNotFoundError(
            f"Não há {lista.NOME_ARQUIVO} em {pasta}. Rode antes o modo flashcards-propor."
        )
    cards = lista.aprovados(pasta, aprovar_todos=aprovar_todos)
    if not cards:
        raise ValueError(
            f"Nenhum card aprovado em {lista.NOME_ARQUIVO}. Marque [x] nos que quiser, "
            "ou use --aprovar-todos."
        )
    html_dir = os.path.join(pasta, "html")
    Path(html_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(html_dir, "flashcards.html")
    Path(out_path).write_text(_render_html([c.como_dict() for c in cards]), encoding="utf-8")
    return out_path


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
    .layout { width:100%; max-width:1500px; display:grid; grid-template-columns:minmax(0,1fr) minmax(0,760px) minmax(0,1fr); gap:12px; padding:0 16px; }
    .container { grid-column:2; grid-row:1; width:100%; padding:24px 0 32px; }
    .side { align-self:center; display:flex; flex-direction:column; gap:8px; padding-top:40px; }
    .side-left { grid-column:1; grid-row:1; align-items:flex-end; }
    .side-right { grid-column:3; grid-row:1; align-items:flex-start; }
    .chip { max-width:100%; padding:7px 12px; border:1px solid var(--surface1); background:var(--surface0); color:var(--teal); border-radius:999px; font-size:0.85rem; cursor:pointer; text-align:left; overflow-wrap:anywhere; transition:border-color .15s, background .15s; }
    .chip:hover { border-color:var(--blue); }
    .chip.active { background:var(--blue); color:var(--crust); border-color:var(--blue); font-weight:600; }
    .scene-wrap { position:relative; }
    .term-panel { position:absolute; z-index:20; left:5%; right:5%; top:16px; max-height:calc(100% - 52px); overflow-y:auto; background:var(--crust); border:2px solid var(--blue); border-radius:14px; padding:18px 20px; box-shadow:0 12px 32px rgba(0,0,0,.55); }
    .term-panel .term-title { color:var(--blue); font-weight:700; font-size:1.05rem; margin-bottom:8px; overflow-wrap:anywhere; }
    .term-panel .term-text { font-size:0.95rem; line-height:1.6; white-space:pre-wrap; }
    .term-panel .term-close { position:absolute; top:8px; right:12px; background:none; border:none; color:var(--overlay0); font-size:1.2rem; cursor:pointer; }
    .term-panel .term-close:hover { color:var(--text); }
    @media (max-width:1000px) {
      .layout { grid-template-columns:minmax(0,1fr); }
      .container { grid-column:1; grid-row:1; }
      .side { padding-top:0; flex-direction:row; flex-wrap:wrap; justify-content:center; align-items:center; }
      .side-left { grid-column:1; grid-row:2; }
      .side-right { grid-column:1; grid-row:3; }
      .side:empty { display:none; }
    }
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
    .scene { width:100%; height:460px; perspective:1000px; cursor:pointer; margin-bottom:20px; }
    .card-inner { width:100%; height:100%; position:relative; transform-style:preserve-3d; transition:transform 0.5s; }
    .card-inner.flipped { transform:rotateY(180deg); }
    .card-face { position:absolute; width:100%; height:100%; backface-visibility:hidden; border-radius:16px; padding:32px; display:flex; flex-direction:column; justify-content:safe center; align-items:center; text-align:center; overflow-y:auto; }
    .card-front { background:var(--surface0); border:2px solid var(--purple); }
    .card-back { background:var(--mantle); border:2px solid var(--teal); transform:rotateY(180deg); }
    .card-face .label { font-size:0.75rem; text-transform:uppercase; letter-spacing:.1em; margin-bottom:16px; }
    .card-front .label { color:var(--purple); }
    .card-back .label { color:var(--teal); }
    .card-face .text { font-size:1rem; line-height:1.6; text-align:left; white-space:pre-wrap; }
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
  <div class="layout">
  <aside class="side side-left" id="side-left" aria-label="Termos e símbolos"></aside>
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
      <div class="scene-wrap" id="scene-wrap">
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
      <div class="term-panel" id="term-panel" role="dialog" aria-live="polite" hidden>
        <button class="term-close" onclick="closePanel()" title="Fechar (Esc)">×</button>
        <div class="term-title" id="term-title"></div>
        <div class="term-text" id="term-text"></div>
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
  <aside class="side side-right" id="side-right" aria-label="Termos e símbolos"></aside>
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

    // ── Subcards: botões laterais com a explicação de termos e símbolos ──────────
    const norm = s => String(s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
    // Termos de 1 ou 2 letras (m, β, v̂) só casam como palavra inteira; "m" não pode casar em "como".
    function contem(x, t) {
      if (t.length >= 3) return x.includes(t);
      let i = x.indexOf(t);
      while (i !== -1) {
        const antes = i > 0 ? x[i - 1] : ' ', depois = x[i + t.length] || ' ';
        if (!/[\\p{L}\\p{N}]/u.test(antes) && !/\\p{L}/u.test(depois)) return true;
        i = x.indexOf(t, i + 1);
      }
      return false;
    }
    function aparece(termo, texto) {
      const t = norm(termo), x = norm(texto);
      if (contem(x, t)) return true;
      const base = t.split(/[_\\s(^]/)[0];
      return base.length > 0 && contem(x, base);
    }
    // Face da pergunta: termos que aparecem nela. Face da resposta: os que aparecem na
    // resposta, mais os que não aparecem na pergunta (para não vazar termo só da resposta).
    function termosDaFace(card, face) {
      const ts = card.termos || [];
      return ts.filter(t => {
        const naP = aparece(t.termo, card.pergunta), naR = aparece(t.termo, card.resposta);
        return face === 'q' ? naP : (naR || !naP);
      });
    }
    function closePanel() {
      document.getElementById('term-panel').hidden = true;
      document.querySelectorAll('.chip.active').forEach(b => b.classList.remove('active'));
    }
    function openTerm(btn, t) {
      if (btn.classList.contains('active')) { closePanel(); return; }
      closePanel();
      btn.classList.add('active');
      document.getElementById('term-title').textContent = t.termo;
      document.getElementById('term-text').textContent = t.explicacao;
      document.getElementById('term-panel').hidden = false;
    }
    function renderChips(face) {
      closePanel();
      const left = document.getElementById('side-left'), right = document.getElementById('side-right');
      left.textContent = ''; right.textContent = '';
      termosDaFace(ALL_CARDS[queue[pos]], face).forEach((t, i) => {
        const b = document.createElement('button');
        b.className = 'chip';
        b.textContent = t.termo;
        b.title = 'Ver o que é';
        b.onclick = e => { e.stopPropagation(); openTerm(b, t); };
        (i % 2 === 0 ? left : right).appendChild(b);
      });
    }
    document.addEventListener('click', e => {
      if (!e.target.closest('#term-panel') && !e.target.closest('.chip')) closePanel();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closePanel(); });

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
      renderChips('q');
    }

    function flipCard() {
      if (flipped) return;
      flipped = true;
      renderChips('a');
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


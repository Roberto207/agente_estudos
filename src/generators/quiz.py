"""Gera quiz de múltipla escolha como HTML autocontido."""
from __future__ import annotations
import json
import os
from pathlib import Path

from ..llm import LLMClient


def generate(llm: LLMClient, pasta: str) -> str | None:
    """
    Lê os .md da pasta, gera questões MCQ via LLM e escreve html/quiz.html.
    Retorna o caminho do arquivo gerado ou None se não há conteúdo suficiente.
    """
    md_files = _collect_md_files(pasta)
    if not md_files:
        return None

    combined = _combine_content(md_files)
    questions = _generate_questions(llm, combined)
    if not questions:
        return None

    html_dir = os.path.join(pasta, "html")
    Path(html_dir).mkdir(parents=True, exist_ok=True)
    out_path = os.path.join(html_dir, "quiz.html")
    Path(out_path).write_text(_render_html(questions), encoding="utf-8")
    return out_path


# ── Coleta e geração ───────────────────────────────────────────────────────────

def _collect_md_files(pasta: str) -> list[str]:
    skip = {"guia_de_estudos.md"}
    result = []
    for md in sorted(Path(pasta).rglob("*.md")):
        if md.name in skip or "transcripts" in md.parts:
            continue
        result.append(str(md))
    return result[:10]


def _combine_content(md_files: list[str]) -> str:
    parts = []
    for path in md_files:
        content = Path(path).read_text(encoding="utf-8")
        parts.append(f"### {Path(path).stem}\n{content[:1500]}")
    return "\n\n---\n\n".join(parts)


def _generate_questions(llm: LLMClient, content: str) -> list[dict]:
    prompt = f"""Leia o material abaixo e crie 10 a 15 questões de múltipla escolha.

Material de estudo:
{content[:8000]}

Responda com JSON válido neste formato exato (array, sem texto extra):
[
  {{
    "pergunta": "Enunciado da questão?",
    "opcoes": ["A) texto opção A", "B) texto opção B", "C) texto opção C", "D) texto opção D"],
    "correta": 0,
    "explicacao": "Explicação detalhada de por que A está correta e por que as outras estão erradas.",
    "fonte": "nome_do_arquivo_origem"
  }}
]

"correta" é o índice (0=A, 1=B, 2=C, 3=D) da resposta correta.
Varie: questões conceituais, de aplicação e de análise comparativa.
Garanta dificuldade variada (fácil, média, difícil)."""

    try:
        result = llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        if isinstance(result, list):
            return [q for q in (_normalize(q) for q in result) if q]
    except Exception:
        pass
    return []


def _normalize(q) -> dict | None:
    """Descarta questões malformadas e força `correta` para int válido — o JS
    compara com ===, então um "1" (string) vindo do LLM nunca daria acerto."""
    if not isinstance(q, dict) or "pergunta" not in q or not isinstance(q.get("opcoes"), list):
        return None
    try:
        correta = int(q.get("correta", -1))
    except (TypeError, ValueError):
        return None
    if not 0 <= correta < len(q["opcoes"]):
        return None
    return {**q, "correta": correta}


# ── Renderização HTML ──────────────────────────────────────────────────────────

def _render_html(questions: list[dict]) -> str:
    # `</` escapado pra um enunciado com "</script>" não fechar o bloco de script.
    qs_json = json.dumps(questions, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__QS_JSON__", qs_json)


# Template com placeholder em vez de f-string: o JS usa muitas chaves e
# template literals, e duplicá-las todas ({{ }}) era fonte fácil de erro.
#
# Navegação: ordem das questões e das alternativas embaralhada a cada sessão
# ("Reembaralhar" gera nova ordem e zera respostas); grade 1..N clicável e campo
# "ir para" permitem pular para qualquer questão; anterior/próxima livres.
_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quiz — Teste seus Conhecimentos</title>
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
    .container { width:100%; max-width:720px; padding:24px 16px 32px; }
    .toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:14px; }
    .toolbar input { width:70px; background:var(--mantle); border:1px solid var(--surface1); color:var(--text); border-radius:6px; padding:6px 8px; font-size:0.85rem; }
    .btn-sm { padding:6px 12px; border:1px solid var(--surface1); background:var(--surface0); color:var(--text); border-radius:6px; font-size:0.82rem; cursor:pointer; }
    .btn-sm:hover { border-color:var(--blue); }
    .grid { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; max-height:120px; overflow-y:auto; scrollbar-color:var(--surface1) var(--mantle); }
    .grid button { width:34px; height:30px; border-radius:6px; border:1px solid var(--surface1); background:var(--mantle); color:var(--subtext); font-size:0.78rem; cursor:pointer; }
    .grid button.ok { border-color:var(--green); color:var(--green); }
    .grid button.err { border-color:var(--red); color:var(--red); }
    .grid button.cur { background:var(--purple); color:var(--crust); border-color:var(--purple); font-weight:700; }
    .progress-bar { background:var(--surface0); border-radius:8px; height:8px; margin-bottom:10px; overflow:hidden; }
    .progress-fill { height:100%; background:var(--purple); border-radius:8px; transition:width 0.3s; }
    .progress-label { color:var(--subtext); font-size:0.82rem; margin-bottom:16px; }
    .question-card { background:var(--surface0); border-radius:16px; padding:28px; margin-bottom:20px; border-left:4px solid var(--blue); }
    .question-num { color:var(--blue); font-size:0.78rem; text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }
    .question-card h2 { color:var(--text); font-size:1.05rem; line-height:1.65; margin-bottom:22px; font-weight:500; }
    .options { display:flex; flex-direction:column; gap:10px; }
    .option { background:var(--mantle); border:2px solid var(--surface1); border-radius:10px; padding:12px 16px; cursor:pointer; font-size:0.93rem; transition:border-color .15s, background .15s; text-align:left; color:var(--text); width:100%; }
    .option:hover:not(:disabled) { border-color:var(--blue); background:var(--surface0); }
    .option.correct { border-color:var(--green) !important; background:rgba(166,227,161,0.1) !important; color:var(--green) !important; }
    .option.wrong   { border-color:var(--red) !important; background:rgba(243,139,168,0.1) !important; color:var(--red) !important; }
    .option:disabled { cursor:default; }
    .feedback { margin-top:16px; padding:14px; border-radius:10px; font-size:0.88rem; line-height:1.55; display:none; }
    .feedback.show { display:block; }
    .feedback.correct { background:rgba(166,227,161,0.08); border:1px solid var(--green); color:var(--green); }
    .feedback.wrong   { background:rgba(243,139,168,0.08); border:1px solid var(--red); color:var(--text); }
    .source-label { margin-top:10px; font-size:0.74rem; color:var(--overlay0); }
    .nav-btns { display:flex; gap:12px; justify-content:space-between; margin-top:20px; }
    .btn { padding:10px 22px; border:none; border-radius:8px; font-size:0.9rem; font-weight:600; cursor:pointer; transition:opacity .15s; }
    .btn:hover { opacity:0.85; }
    .btn:disabled { opacity:0.35; cursor:default; }
    .btn-prev   { background:var(--surface1); color:var(--text); }
    .btn-next   { background:var(--purple); color:var(--crust); }
    .btn-finish { background:var(--green); color:var(--crust); }
    .results { background:var(--surface0); border-radius:16px; padding:32px; text-align:center; display:none; }
    .results h2 { color:var(--green); font-size:1.8rem; margin-bottom:8px; }
    .score { font-size:3rem; font-weight:700; color:var(--purple); margin:16px 0; }
    .results p { color:var(--subtext); margin-bottom:20px; }
    .wrong-list { text-align:left; margin-top:20px; }
    .wrong-list h3 { color:var(--yellow); margin-bottom:12px; }
    .wrong-item { background:var(--mantle); border-radius:8px; padding:12px; margin-bottom:8px; font-size:0.88rem; line-height:1.5; }
    .wrong-item .src { color:var(--overlay0); font-size:0.78rem; }
    .results-actions { display:flex; gap:12px; justify-content:center; margin-top:24px; flex-wrap:wrap; }
  </style>
</head>
<body>
  <header>
    <h1>📝 Quiz — Teste seus Conhecimentos</h1>
    <button class="btn-sm" onclick="startSession()" title="Nova ordem aleatória; zera as respostas">🔀 Reembaralhar</button>
  </header>
  <div class="container">
    <div id="quiz-area">
      <div class="toolbar">
        <label for="goto" style="color:var(--subtext);font-size:0.82rem;">Ir para questão</label>
        <input id="goto" type="number" min="1" onkeydown="if(event.key==='Enter')gotoInput()">
        <button class="btn-sm" onclick="gotoInput()">Ir</button>
      </div>
      <div class="grid" id="grid"></div>
      <div class="progress-bar"><div class="progress-fill" id="prog"></div></div>
      <p class="progress-label" id="prog-label"></p>
      <div id="question-area"></div>
      <div class="nav-btns" id="nav-btns"></div>
    </div>
    <div class="results" id="results"></div>
  </div>

  <script>
    const QS = __QS_JSON__;
    // Cada item da sessão: {q: índice em QS, opts: ordem embaralhada das
    // alternativas (índices originais), resp: alternativa original escolhida | null}
    let session = [];
    let pos = 0;

    function esc(s) {
      return String(s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
    // As alternativas vêm do LLM como "A) texto" — o prefixo deixa de valer
    // depois do embaralhamento, então é removido e a letra é recolocada na tela.
    function stripLetter(s) { return String(s).replace(/^\\s*[A-Ea-e]\\s*[\\)\\.\\-:]\\s*/, ''); }
    function shuffled(n) {
      const a = Array.from({length: n}, (_, i) => i);
      for (let i = n - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
      return a;
    }

    function startSession() {
      session = shuffled(QS.length).map(q => ({ q, opts: shuffled(QS[q].opcoes.length), resp: null }));
      pos = 0;
      document.getElementById('results').style.display = 'none';
      document.getElementById('quiz-area').style.display = 'block';
      render();
    }

    function answeredCount() { return session.filter(s => s.resp !== null).length; }

    function renderGrid() {
      document.getElementById('grid').innerHTML = session.map((s, i) => {
        let cls = '';
        if (s.resp !== null) cls = s.resp === QS[s.q].correta ? 'ok' : 'err';
        if (i === pos) cls += ' cur';
        return `<button class="${cls}" onclick="go(${i})">${i + 1}</button>`;
      }).join('');
    }

    function render() {
      const s = session[pos];
      const q = QS[s.q];
      const n = session.length;
      renderGrid();
      document.getElementById('prog').style.width = Math.round(answeredCount() / n * 100) + '%';
      document.getElementById('prog-label').textContent =
        `Questão ${pos + 1} de ${n} — ${answeredCount()} respondida(s)`;

      const opts = s.opts.map((orig, i) => {
        let cls = 'option';
        if (s.resp !== null) {
          if (orig === q.correta) cls += ' correct';
          else if (orig === s.resp) cls += ' wrong';
        }
        const letter = String.fromCharCode(65 + i);
        return `<button class="${cls}" onclick="selectOpt(${orig})" ${s.resp !== null ? 'disabled' : ''}>${letter}) ${esc(stripLetter(q.opcoes[orig]))}</button>`;
      }).join('');

      let fb = '';
      if (s.resp !== null) {
        const ok = s.resp === q.correta;
        fb = `<div class="feedback ${ok ? 'correct' : 'wrong'} show">${ok ? '✓ Correto!  ' : '✗ Incorreto. '}${esc(q.explicacao || '')}</div>`;
      }

      document.getElementById('question-area').innerHTML = `
        <div class="question-card">
          <p class="question-num">Questão ${pos + 1}</p>
          <h2>${esc(q.pergunta)}</h2>
          <div class="options">${opts}</div>
          ${fb}
          ${q.fonte ? `<p class="source-label">Fonte: ${esc(q.fonte)}</p>` : ''}
        </div>`;

      const last = pos === n - 1;
      document.getElementById('nav-btns').innerHTML = `
        <button class="btn btn-prev" onclick="go(${pos - 1})" ${pos === 0 ? 'disabled' : ''}>← Anterior</button>
        ${last
          ? '<button class="btn btn-finish" onclick="showResults()">Ver Resultado →</button>'
          : `<button class="btn btn-next" onclick="go(${pos + 1})">Próxima →</button>`}`;
    }

    function selectOpt(orig) {
      const s = session[pos];
      if (s.resp !== null) return;
      s.resp = orig;
      render();
    }

    function go(i) {
      if (i < 0 || i >= session.length) return;
      pos = i;
      render();
    }

    function gotoInput() {
      const v = parseInt(document.getElementById('goto').value, 10);
      if (!isNaN(v)) go(v - 1);
    }

    function showResults() {
      const n = session.length;
      const answered = session.filter(s => s.resp !== null);
      const score = answered.filter(s => s.resp === QS[s.q].correta).length;
      const wrong = answered.filter(s => s.resp !== QS[s.q].correta);
      const pending = n - answered.length;
      const pct = Math.round(score / n * 100);
      const emoji = pct >= 80 ? '🎉' : pct >= 60 ? '👍' : '📚';
      const msg = pct >= 80
        ? 'Excelente domínio do conteúdo!'
        : pct >= 60 ? 'Bom progresso, revise os erros.'
        : 'Revise o material e tente novamente.';

      const wrongHtml = wrong.length ? `
        <div class="wrong-list">
          <h3>📌 Para revisar:</h3>
          ${wrong.map(s => {
            const q = QS[s.q];
            return `<div class="wrong-item">
              <strong>${esc(q.pergunta)}</strong><br>
              Resposta correta: ${esc(stripLetter(q.opcoes[q.correta]))}
              ${q.fonte ? `<br><span class="src">Material: ${esc(q.fonte)}</span>` : ''}
            </div>`;
          }).join('')}
        </div>` : (answered.length ? '<p style="color:var(--green);margin-top:12px;">Parabéns! Nenhum erro.</p>' : '');

      document.getElementById('quiz-area').style.display = 'none';
      document.getElementById('results').innerHTML = `
        <h2>${emoji} Resultado Final</h2>
        <div class="score">${score}/${n}</div>
        <p>${pct}% de acerto — ${msg}${pending ? `<br>${pending} questão(ões) sem resposta.` : ''}</p>
        ${wrongHtml}
        <div class="results-actions">
          ${pending ? '<button class="btn btn-prev" onclick="backToQuiz()">← Voltar às questões</button>' : ''}
          <button class="btn btn-next" onclick="startSession()">🔀 Tentar novamente (nova ordem)</button>
        </div>`;
      document.getElementById('results').style.display = 'block';
    }

    function backToQuiz() {
      document.getElementById('results').style.display = 'none';
      document.getElementById('quiz-area').style.display = 'block';
      const firstPending = session.findIndex(s => s.resp === null);
      go(firstPending >= 0 ? firstPending : 0);
    }

    startSession();
  </script>
</body>
</html>"""

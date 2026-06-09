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
            return [
                q for q in result
                if isinstance(q, dict) and "pergunta" in q and "opcoes" in q
            ]
    except Exception:
        pass
    return []


# ── Renderização HTML ──────────────────────────────────────────────────────────

def _render_html(questions: list[dict]) -> str:
    qs_json = json.dumps(questions, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quiz — Teste seus Conhecimentos</title>
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
    .container {{ width:100%; max-width:720px; padding:32px 16px; }}
    .progress-bar {{ background:var(--surface0); border-radius:8px; height:8px; margin-bottom:10px; overflow:hidden; }}
    .progress-fill {{ height:100%; background:var(--purple); border-radius:8px; transition:width 0.3s; }}
    .progress-label {{ color:var(--subtext); font-size:0.82rem; margin-bottom:24px; }}
    .question-card {{ background:var(--surface0); border-radius:16px; padding:28px; margin-bottom:20px; border-left:4px solid var(--blue); }}
    .question-num {{ color:var(--blue); font-size:0.78rem; text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }}
    .question-card h2 {{ color:var(--text); font-size:1.05rem; line-height:1.65; margin-bottom:22px; font-weight:500; }}
    .options {{ display:flex; flex-direction:column; gap:10px; }}
    .option {{ background:var(--mantle); border:2px solid var(--surface1); border-radius:10px; padding:12px 16px; cursor:pointer; font-size:0.93rem; transition:border-color .15s, background .15s; text-align:left; color:var(--text); width:100%; }}
    .option:hover:not(:disabled) {{ border-color:var(--blue); background:var(--surface0); }}
    .option.correct {{ border-color:var(--green) !important; background:rgba(166,227,161,0.1) !important; color:var(--green) !important; }}
    .option.wrong   {{ border-color:var(--red) !important; background:rgba(243,139,168,0.1) !important; color:var(--red) !important; }}
    .option:disabled {{ cursor:default; }}
    .feedback {{ margin-top:16px; padding:14px; border-radius:10px; font-size:0.88rem; line-height:1.55; display:none; }}
    .feedback.show {{ display:block; }}
    .feedback.correct {{ background:rgba(166,227,161,0.08); border:1px solid var(--green); color:var(--green); }}
    .feedback.wrong   {{ background:rgba(243,139,168,0.08); border:1px solid var(--red); color:var(--text); }}
    .source-label {{ margin-top:10px; font-size:0.74rem; color:var(--overlay0); }}
    .nav-btns {{ display:flex; gap:12px; justify-content:flex-end; margin-top:20px; }}
    .btn {{ padding:10px 22px; border:none; border-radius:8px; font-size:0.9rem; font-weight:600; cursor:pointer; transition:opacity .15s; }}
    .btn:hover {{ opacity:0.85; }}
    .btn-next   {{ background:var(--purple); color:var(--crust); }}
    .btn-finish {{ background:var(--green); color:var(--crust); }}
    .results {{ background:var(--surface0); border-radius:16px; padding:32px; text-align:center; display:none; }}
    .results h2 {{ color:var(--green); font-size:1.8rem; margin-bottom:8px; }}
    .score {{ font-size:3rem; font-weight:700; color:var(--purple); margin:16px 0; }}
    .results p {{ color:var(--subtext); margin-bottom:20px; }}
    .wrong-list {{ text-align:left; margin-top:20px; }}
    .wrong-list h3 {{ color:var(--yellow); margin-bottom:12px; }}
    .wrong-item {{ background:var(--mantle); border-radius:8px; padding:12px; margin-bottom:8px; font-size:0.88rem; line-height:1.5; }}
    .wrong-item a {{ color:var(--blue); }}
    .btn-restart {{ background:var(--purple); color:var(--crust); margin-top:24px; }}
  </style>
</head>
<body>
  <header>
    <h1>📝 Quiz — Teste seus Conhecimentos</h1>
    <a href="index.html">← Voltar ao índice</a>
  </header>
  <div class="container">
    <div id="quiz-area">
      <div class="progress-bar"><div class="progress-fill" id="prog"></div></div>
      <p class="progress-label" id="prog-label">Questão 1 de 0</p>
      <div id="question-area"></div>
      <div class="nav-btns" id="nav-btns"></div>
    </div>
    <div class="results" id="results"></div>
  </div>

  <script>
    const QS = {qs_json};
    let current = 0;
    let score = 0;
    const wrong = [];
    let answered = false;

    function esc(s) {{
      return String(s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}
    function slug(s) {{ return String(s).toLowerCase().replace(/\\s+/g,'_'); }}

    function renderQ() {{
      if (current >= QS.length) {{ showResults(); return; }}
      const q = QS[current];
      answered = false;

      document.getElementById('prog').style.width = Math.round(current / QS.length * 100) + '%';
      document.getElementById('prog-label').textContent = `Questão ${{current + 1}} de ${{QS.length}}`;

      const opts = q.opcoes.map((o, i) =>
        `<button class="option" onclick="selectOpt(${{i}})" id="opt-${{i}}">${{esc(o)}}</button>`
      ).join('');

      document.getElementById('question-area').innerHTML = `
        <div class="question-card">
          <p class="question-num">Questão ${{current + 1}}</p>
          <h2>${{esc(q.pergunta)}}</h2>
          <div class="options">${{opts}}</div>
          <div class="feedback" id="feedback"></div>
          ${{q.fonte ? `<p class="source-label">Fonte: ${{esc(q.fonte)}}</p>` : ''}}
        </div>`;

      document.getElementById('nav-btns').innerHTML = '';
    }}

    function selectOpt(idx) {{
      if (answered) return;
      answered = true;
      const q = QS[current];
      document.querySelectorAll('.option').forEach(b => b.disabled = true);
      const fb = document.getElementById('feedback');

      if (idx === q.correta) {{
        score++;
        document.getElementById('opt-' + idx).classList.add('correct');
        fb.textContent = '✓ Correto!  ' + q.explicacao;
        fb.className = 'feedback correct show';
      }} else {{
        document.getElementById('opt-' + idx).classList.add('wrong');
        document.getElementById('opt-' + q.correta).classList.add('correct');
        fb.textContent = '✗ Incorreto. ' + q.explicacao;
        fb.className = 'feedback wrong show';
        wrong.push({{ q: q.pergunta, fonte: q.fonte, correta: q.opcoes[q.correta] }});
      }}

      const navBtns = document.getElementById('nav-btns');
      if (current < QS.length - 1) {{
        navBtns.innerHTML = '<button class="btn btn-next" onclick="nextQ()">Próxima →</button>';
      }} else {{
        navBtns.innerHTML = '<button class="btn btn-finish" onclick="showResults()">Ver Resultado →</button>';
      }}
    }}

    function nextQ() {{ current++; renderQ(); }}

    function showResults() {{
      document.getElementById('quiz-area').style.display = 'none';
      const pct = Math.round(score / QS.length * 100);
      const emoji = pct >= 80 ? '🎉' : pct >= 60 ? '👍' : '📚';
      const msg = pct >= 80
        ? 'Excelente domínio do conteúdo!'
        : pct >= 60 ? 'Bom progresso, revise os erros.'
        : 'Revise o material e tente novamente.';

      const wrongHtml = wrong.length ? `
        <div class="wrong-list">
          <h3>📌 Para revisar:</h3>
          ${{wrong.map(w =>
            `<div class="wrong-item">
              <strong>${{esc(w.q)}}</strong><br>
              Resposta correta: ${{esc(w.correta)}}
              ${{w.fonte ? ` &nbsp;—&nbsp; <a href="${{slug(w.fonte)}}.html">Ver material</a>` : ''}}
            </div>`
          ).join('')}}
        </div>` : '<p style="color:var(--green);margin-top:12px;">Parabéns! Nenhum erro.</p>';

      document.getElementById('results').innerHTML = `
        <h2>${{emoji}} Resultado Final</h2>
        <div class="score">${{score}}/${{QS.length}}</div>
        <p>${{pct}}% de acerto — ${{msg}}</p>
        ${{wrongHtml}}
        <button class="btn btn-restart" onclick="location.reload()">Tentar novamente</button>`;
      document.getElementById('results').style.display = 'block';
    }}

    renderQ();
  </script>
</body>
</html>"""

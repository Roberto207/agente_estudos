"""Modo artigo: regras carregadas, prompt montado, PDF lido por inteiro, CLI protegida."""
import pytest

from src import agent, modo_artigo
from src.tools import web


def test_system_inclui_regras_do_modo_e_didaticas():
    s = modo_artigo.system_modo_artigo()
    assert "MODO ARTIGO" in s and "Pausa" in s                      # modo_artigo.md
    assert "Todo termo técnico é definido na PRIMEIRA ocorrência" in s  # regras_didaticas.md
    assert "<!--" not in s                                          # cabeçalho de manutenção removido
    assert "NÃO crie `guia_de_estudos.md`" in s


def test_regra_16_fontes_do_ganho_chega_ao_redator_e_ao_checklist():
    s = modo_artigo.system_modo_artigo()
    assert "16. **Quando o ganho de um método vem de fontes distintas" in s   # regras_didaticas.md
    assert "O que X não faz." in s and "sem piso" in s                        # anti-enchimento
    assert "(derivação própria)" in s and "sem base no material" in s         # anti-invenção
    assert "7b. **A decomposição do ganho (regra 16)**" in s                  # modo_artigo.md
    assert "10. Se o artigo atribui o ganho do método a duas ou mais fontes" in s


def test_task_do_modo_artigo_pede_leitura_do_texto_completo():
    t = agent._build_task("LoRA", "", "", "/tmp/x", ["https://arxiv.org/pdf/2106.09685"], modo_artigo=True)
    assert "MODO ARTIGO" in t and "texto completo" in t
    normal = agent._build_task("LoRA", "", "", "/tmp/x", [])
    assert "MODO ARTIGO" not in normal


class _Resp:
    def __init__(self, content: bytes, ctype: str, text: str = ""):
        self.content, self.headers, self.text = content, {"Content-Type": ctype}, text

    def raise_for_status(self):
        pass


def test_fetch_url_converte_pdf_em_texto_completo(monkeypatch):
    monkeypatch.setattr(web.requests, "get", lambda *a, **k: _Resp(b"%PDF-1.5 ...", "application/pdf"))
    monkeypatch.setattr(web, "_pdf_para_texto", lambda data: "TEXTO COMPLETO DO PAPER")
    assert web.fetch_url("https://arxiv.org/pdf/1412.6980") == "TEXTO COMPLETO DO PAPER"


def test_fetch_url_html_continua_igual(monkeypatch):
    html = "<html><body><p>" + "uma linha longa de texto util para o teste " * 3 + "</p></body></html>"
    monkeypatch.setattr(web.requests, "get", lambda *a, **k: _Resp(html.encode(), "text/html", html))
    assert "linha longa" in web.fetch_url("https://exemplo.com/a")


def test_main_recusa_artigo_fora_do_modo_agent(tmp_path):
    from typer.testing import CliRunner
    import main
    r = CliRunner().invoke(main.app if hasattr(main, "app") else main.typer.main.get_command, [
        "--mode", "pipeline", "--artigo", "--tema", "x", "--pasta", str(tmp_path),
    ]) if hasattr(main, "app") else None
    if r is None:
        pytest.skip("main.py não expõe `app`")
    assert r.exit_code != 0

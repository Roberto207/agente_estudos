"""Flashcards em dois passos: lista de aprovação, lint, merge e montagem do HTML. Sem LLM."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.generators import flashcards, flashcards_lista as fl


LONGA = ("Porque não se conhece o formato das soluções, então a medida é indireta: sorteiam-se d direções, "
         "deixa-se o treino andar só nelas e aumenta-se d até a tarefa ser resolvida. O primeiro d que funciona "
         "estima a dimensão intrínseca.")


def _card(p="Por que o treino anda num subespaço aleatório?", r=LONGA,
          fonte="[[03_leitura]]", secao="Leitura", aprovado=False):
    return fl.Card(pergunta=p, resposta=r, fonte=fonte, secao=secao, aprovado=aprovado)


# ── parser / render ───────────────────────────────────────────────────────────

def test_render_e_parse_sao_inversos():
    cards = [_card(aprovado=True), _card(p="Qual a diferença entre D e d_int em palavras?", r=LONGA)]
    de_volta = fl.parse(fl.render(cards, "CNT34"))
    assert [(c.pergunta, c.resposta, c.fonte, c.aprovado, c.secao) for c in de_volta] == \
           [(c.pergunta, c.resposta, c.fonte, c.aprovado, c.secao) for c in cards]


def test_render_e_parse_preservam_os_termos_e_suas_marcas():
    c = _card(aprovado=True)
    c.termos = [fl.Termo("θ_t", "parâmetros depois do passo t", True), fl.Termo("α", "taxa de aprendizado")]
    sem = _card(p="Outra pergunta sem subcards sobre projeção?", r=LONGA)
    de_volta = fl.parse(fl.render([c, sem], "T"))
    assert de_volta[0].termos == c.termos
    assert de_volta[1].termos == []
    assert de_volta[1].fonte == "[[03_leitura]]"


def test_parse_le_marcas_x_maiusculo_e_vazio():
    texto = (
        "## S\n\n"
        "- [X] **P:** Pergunta um?\n  **R:** Resposta um.\n  **Fonte:** [[a]]\n"
        "- [ ] **P:** Pergunta dois?\n  **R:** Resposta dois.\n"
    )
    c1, c2 = fl.parse(texto)
    assert c1.aprovado and not c2.aprovado
    assert c2.fonte == ""


def test_hash_id_bate_com_o_javascript_do_html():
    # djb2 sobre unidades UTF-16, como o `hashId` do template
    assert fl.hash_id("") == "c" + fl._base36(5381)
    assert fl.hash_id("Por que?") == fl.hash_id("Por que?")
    assert fl.hash_id("a") != fl.hash_id("b")
    h = 5381
    for ch in "ção?":
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    assert fl.hash_id("ção?") == "c" + fl._base36(h)


# ── lint ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pergunta,resposta,trecho", [
    ("Qual é a Eq. 2 do artigo?", "É a soma.", "arquivo, seção"),
    ("O que diz a seção 3 sobre o treino?", "Que treina.", "arquivo, seção"),
    ("Como se escreve θ no subespaço?", "Assim.", "subcard"),
    ("Quanto vale $d$ no exemplo?", "Cem.", "LaTeX"),
    ("O d_int é menor que D?", "Sim.", "sim ou não"),
    ("Defina o espaço de parâmetros.", "É onde vivem os pesos.", "interrogação"),
    ("", "algo", "vazia"),
])
def test_lint_rejeita(pergunta, resposta, trecho):
    motivo = fl.motivo_rejeicao(fl.Card(pergunta, resposta))
    assert motivo is not None and trecho in motivo


def test_lint_exige_subcard_para_simbolo_e_aceita_cobertura_pela_letra_base():
    r = LONGA + " O passo vale m̂_t / √v̂_t, e ε evita dividir por zero."
    c = _card(p="Por que o passo usa m̂_t dividido por √v̂_t?", r=r)
    assert "subcard" in fl.motivo_rejeicao(c)
    c.termos = [fl.Termo("m̂_t", "média do gradiente")]
    assert "v, ε" in fl.motivo_rejeicao(c) or "ε, v" in fl.motivo_rejeicao(c)
    c.termos += [fl.Termo("v̂", "média do quadrado"), fl.Termo("ε", "evita dividir por zero")]
    assert fl.motivo_rejeicao(c) is None  # v̂ cobre v̂_t pela letra-base


def test_lint_operador_so_exige_algum_subcard():
    c = _card(p="Por que a raiz √ aparece no denominador do passo?", r=LONGA)
    assert "subcard" in fl.motivo_rejeicao(c)
    c.termos = [fl.Termo("√", "raiz quadrada")]
    assert fl.motivo_rejeicao(c) is None


def test_lint_aceita_pergunta_boa():
    assert fl.motivo_rejeicao(_card()) is None


def test_lint_rejeita_resposta_curta_demais_mas_respeita_o_aprovado():
    assert "menos de" in fl.motivo_rejeicao(_card(r="Porque não se conhece o formato."))
    assert fl.motivo_rejeicao(_card(r="Porque não se conhece o formato.", aprovado=True)) is None


def test_lint_rejeita_resposta_longa():
    assert "resposta" in fl.motivo_rejeicao(_card(r="x" * (fl.RESPOSTA_MAX + 1)))


def test_validar_barra_duplicata_exata_e_parecida():
    a = _card()
    b = _card()
    c = _card(p="Por que o treino anda dentro de um subespaço aleatório?")
    rel = fl.validar([a, b, c])
    assert rel.aceitos == [a]
    assert {m for _, m in rel.rejeitados} == {"duplicata"}


# ── gravar_lista / reproposição ──────────────────────────────────────────────

def test_gravar_recusa_sobrescrever_sem_regerar(tmp_path):
    fl.gravar_lista(str(tmp_path), [_card()], "T")
    with pytest.raises(FileExistsError):
        fl.gravar_lista(str(tmp_path), [_card(p="Outra pergunta totalmente diferente sobre projeção?")], "T")


def test_regerar_mantem_aprovados_e_nao_repropoe_apagados(tmp_path):
    pasta = str(tmp_path)
    p1 = _card(p="Por que o treino anda num subespaço aleatório?", r=LONGA)
    p2 = _card(p="Como d_int90 resolve o problema da perda que nunca chega a zero?", r=LONGA)
    p2.termos = [fl.Termo("d_int90", "menor d com 90% do desempenho")]
    fl.gravar_lista(pasta, [p1, p2], "T")

    # usuário aprova o primeiro e apaga o segundo
    arq = tmp_path / fl.NOME_ARQUIVO
    cards = fl.parse(arq.read_text(encoding="utf-8"))
    cards[0].aprovado = True
    arq.write_text(fl.render(cards[:1], "T"), encoding="utf-8")

    novo = _card(p="Qual a diferença entre dimensão do espaço e dimensão intrínseca?", r=LONGA)
    rel = fl.gravar_lista(pasta, [p1, p2, novo], "T", regerar=True)

    finais = fl.parse(arq.read_text(encoding="utf-8"))
    assert [c.pergunta for c in finais] == [p1.pergunta, novo.pergunta]
    assert finais[0].aprovado and not finais[1].aprovado
    assert any("descartado" in m for _, m in rel.rejeitados)
    estado = json.loads((tmp_path / ".agente" / fl.NOME_ESTADO).read_text(encoding="utf-8"))
    assert p2.id in estado["descartados"]


# ── montar ───────────────────────────────────────────────────────────────────

def _lista_com(tmp_path, cards):
    (tmp_path / fl.NOME_ARQUIVO).write_text(fl.render(cards, "T"), encoding="utf-8")


def _cards_do_html(caminho):
    html = Path(caminho).read_text(encoding="utf-8")
    m = re.search(r"const ALL_CARDS = (\[.*?\]);\n", html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_montar_inclui_so_os_aprovados(tmp_path):
    _lista_com(tmp_path, [_card(aprovado=True), _card(p="Outra pergunta aprovada sobre projeção esparsa?", aprovado=False)])
    cards = _cards_do_html(flashcards.montar(str(tmp_path)))
    assert [c["pergunta"] for c in cards] == ["Por que o treino anda num subespaço aleatório?"]


def test_montar_leva_so_os_termos_marcados(tmp_path):
    c = _card(aprovado=True)
    c.termos = [fl.Termo("θ_t", "parâmetros depois do passo t", True), fl.Termo("α", "taxa", False)]
    _lista_com(tmp_path, [c])
    cards = _cards_do_html(flashcards.montar(str(tmp_path)))
    assert cards[0]["termos"] == [{"termo": "θ_t", "explicacao": "parâmetros depois do passo t"}]


def test_montar_aprovar_todos_leva_todos_os_termos(tmp_path):
    c = _card()
    c.termos = [fl.Termo("θ_t", "a"), fl.Termo("α", "b")]
    _lista_com(tmp_path, [c])
    cards = _cards_do_html(flashcards.montar(str(tmp_path), aprovar_todos=True))
    assert [t["termo"] for t in cards[0]["termos"]] == ["θ_t", "α"]


def test_card_sem_termos_nao_tem_chave_termos_no_html(tmp_path):
    _lista_com(tmp_path, [_card(aprovado=True)])
    assert "termos" not in _cards_do_html(flashcards.montar(str(tmp_path)))[0]


def test_montar_escapa_fecha_script_nos_termos(tmp_path):
    c = _card(aprovado=True)
    c.termos = [fl.Termo("</script>", "x", True)]
    _lista_com(tmp_path, [c])
    html = Path(flashcards.montar(str(tmp_path))).read_text(encoding="utf-8")
    assert html.count("</script>") == 1


def test_html_tem_colunas_laterais_e_painel(tmp_path):
    _lista_com(tmp_path, [_card(aprovado=True)])
    html = Path(flashcards.montar(str(tmp_path))).read_text(encoding="utf-8")
    for marca in ('id="side-left"', 'id="side-right"', 'id="term-panel"', "function renderChips"):
        assert marca in html
    # colunas fixas: lateral vazia não pode puxar o card para a primeira coluna da grade
    for regra in (".container { grid-column:2;", ".side-left { grid-column:1;", ".side-right { grid-column:3;"):
        assert regra in html


def test_montar_aprovar_todos(tmp_path):
    _lista_com(tmp_path, [_card(), _card(p="Outra pergunta sobre projeção esparsa e Fastfood?")])
    assert len(_cards_do_html(flashcards.montar(str(tmp_path), aprovar_todos=True))) == 2


def test_montar_sem_aprovados_ou_sem_lista_da_erro_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="flashcards-propor"):
        flashcards.montar(str(tmp_path))
    _lista_com(tmp_path, [_card()])
    with pytest.raises(ValueError, match="aprovado"):
        flashcards.montar(str(tmp_path))


def test_montar_escapa_fecha_script(tmp_path):
    _lista_com(tmp_path, [_card(p="Por que um card com </script> não quebra a página?", aprovado=True)])
    html = Path(flashcards.montar(str(tmp_path))).read_text(encoding="utf-8")
    assert html.count("</script>") == 1


# ── propor (LLM falso) ───────────────────────────────────────────────────────

class _LLMFalso:
    def __init__(self, resposta):
        self.resposta, self.chamadas = resposta, []

    def chat_json(self, messages, system=None, max_tokens=0, **_):
        self.chamadas.append((messages, system))
        return self.resposta


def _pasta_de_estudo(tmp_path):
    (tmp_path / "00_contexto_e_mapa.md").write_text("# Mapa\nO fluxo principal em sete passos. " * 5, encoding="utf-8")
    (tmp_path / "fundamentos").mkdir()
    (tmp_path / "fundamentos" / "01_base.md").write_text(
        "# Base\n\n## TL;DR\n\nA ideia central da base.\n\n## Conteúdo Completo\n\n" + "texto longo " * 40, encoding="utf-8")
    return str(tmp_path)


def test_propor_usa_regras_mapa_e_tldr_e_grava_lista(tmp_path):
    pasta = _pasta_de_estudo(tmp_path)
    llm = _LLMFalso([
        {"pergunta": "Por que a base vem antes da leitura?", "resposta": LONGA, "fonte": "[[01_base]]", "secao": "fundamentos"},
        {"pergunta": "Qual a fórmula θ da Eq. 2?", "resposta": LONGA + " θ₀ + P·θ.", "fonte": "[[01_base]]", "secao": "fundamentos"},
    ])
    rel = flashcards.propor(llm, pasta)
    (mensagem,), system = llm.chamadas[0][0], llm.chamadas[0][1]
    assert "A ideia central da base." in mensagem["content"] and "fluxo principal" in mensagem["content"]
    assert "Conteúdo Completo" not in mensagem["content"] and "texto longo" not in mensagem["content"]
    assert "Alvo de **30 a 50 cards" in system and "<!--" not in system
    assert len(rel.aceitos) == 1 and len(rel.rejeitados) == 1
    assert len(fl.ler_lista(pasta)) == 1 and not fl.ler_lista(pasta)[0].aprovado


def test_propor_pasta_sem_conteudo_devolve_none(tmp_path):
    assert flashcards.propor(_LLMFalso([]), str(tmp_path)) is None


def test_propor_resposta_invalida_propaga_o_erro(tmp_path):
    pasta = _pasta_de_estudo(tmp_path)
    with pytest.raises(ValueError, match="lista JSON"):
        flashcards.propor(_LLMFalso({"erro": 1}), pasta)


# ── CLI de validação (usada pelo agente Claude) ──────────────────────────────

def test_cli_valida_lista_escrita_a_mao(tmp_path):
    _lista_com(tmp_path, [_card(), _card(p="Qual é a Eq. 2 do artigo?")])
    r = subprocess.run([sys.executable, "-m", "src.generators.flashcards_lista", str(tmp_path)],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 1 and "1 rejeitados" in r.stdout

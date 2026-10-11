import json

from src.podcast.lint import lint, lint_arquivo, main

# Fala "boa" de ~25 palavras, repetida para chegar à faixa de R13.
_P = "[Professor]: Pensa numa fila de banco em que cada pessoa passa a informação adiante, e o erro vai sendo corrigido aos poucos por todo mundo."
_A = "[Aprendiz]: Mas por que a correção começa pelo fim da fila e não pelo começo, e se a fila for muito longa?"


def _roteiro(*extra: str, repeticoes: int = 45) -> str:
    corpo = ["## Abertura"] + [_P, _A] * repeticoes + list(extra)
    return "---\nepisodio: 2\n---\n" + "\n".join(corpo) + "\n"


def _codigos(texto, numero=2, total=3, curto=False):
    return lint(texto, numero, total, curto).codigos


def test_roteiro_limpo_so_avisa_falta_de_ponte():
    res = lint(_roteiro(), numero=2, total=3)
    assert res.status == "aviso"
    assert res.codigos == ["L6"]


def test_ponte_para_episodio_anterior_remove_o_aviso():
    texto = _roteiro("[Professor]: Lembra do episódio um, quando vimos a fila?")
    assert lint(texto, 2, 3).status == "aprovado"


def test_l1_linha_fora_do_formato():
    assert "L1" in _codigos(_roteiro("Aqui está o roteiro:"))
    assert "L1" in _codigos(_roteiro("**[Professor]:** oi"))
    assert "L1" in _codigos(_roteiro("# Episódio 2"))


def test_l2_markdown_latex_codigo_e_rubricas():
    for fala in [
        "[Professor]: A derivada é ∂L/∂w.",
        "[Professor]: Chame loss.backward depois.",
        "[Professor]: Use learning_rate pequeno.",
        "[Aprendiz]: (risos) entendi",
        "[Professor]: Isso é **importante**.",
        "[Professor]: x = y + 1",
    ]:
        assert "L2" in _codigos(_roteiro(fala)), fala


def test_l2_pontuacao_tipografica_e_permitida():
    assert "L2" not in _codigos(_roteiro("[Professor]: “Aspas” e reticências… e travessão — tudo bem, 95% certo."))


def test_l3_tamanho_e_excecao_de_material_curto():
    curto = _roteiro(repeticoes=5)
    assert "L3" in _codigos(curto)
    assert "L3" not in _codigos(curto, curto=True)
    assert "L3" in _codigos(_roteiro(repeticoes=80), curto=True)  # limite superior vale sempre


def test_l4_episodio_1_citando_anterior():
    assert "L4" in _codigos(_roteiro("[Professor]: Como no episódio anterior."), numero=1)


def test_l4_episodio_futuro_como_ja_visto_e_auto_apresentacao():
    assert "L4" in _codigos(_roteiro("[Professor]: Lembra do episódio três, que vimos?"), numero=2)
    # Mencionar o próprio número sem marcador de passado é legítimo.
    assert "L4" not in _codigos(_roteiro("[Professor]: Bem-vindos ao episódio dois."), numero=2)
    # Gancho para o futuro também.
    assert "L4" not in _codigos(_roteiro("[Professor]: No episódio três a gente aprofunda."), numero=2)


def test_l4_episodio_inexistente_e_ultimo_prometendo_proximo():
    assert "L4" in _codigos(_roteiro("[Professor]: No episódio nove veremos mais."), numero=2, total=3)
    assert "L4" in _codigos(_roteiro("[Professor]: No próximo episódio, CNNs."), numero=3, total=3)


def test_l5_elogio_vazio_vale_para_os_dois_papeis():
    assert "L5" in _codigos(_roteiro("[Professor]: Ótima pergunta!"))
    assert "L5" in _codigos(_roteiro("[Aprendiz]: Boa pergunta, eu também queria saber."))
    assert "L5" in _codigos(_roteiro("[Professor]: Boa dúvida de engenheiro."))
    assert "L5" in _codigos(_roteiro("[Professor]: Que observação interessante."))


def test_l7_aprendiz_sem_por_que_e_sem_e_se():
    corpo = "## A\n" + "\n".join([_P, "[Aprendiz]: Entendo, continue explicando com calma por favor."] * 45)
    res = lint(corpo, 2, 3, material_curto=True)  # curto: isola o L7 do L3 (tamanho)
    assert [a.mensagem for a in res.achados if a.codigo == "L7"] == [
        "Aprendiz não pergunta 'por quê'", "Aprendiz não pergunta 'e se'"]
    assert res.status == "aviso"


def test_l8_aprendiz_so_concordando():
    seq = ["[Aprendiz]: Entendi.", _P, "[Aprendiz]: Faz sentido.", _P, "[Aprendiz]: Certo."]
    assert "L8" in _codigos(_roteiro(*seq))


def test_cli_infere_numero_total_e_material_curto(tmp_path, capsys):
    (tmp_path / "a.md").write_text("curto", encoding="utf-8")
    pod = tmp_path / "podcast"
    pod.mkdir()
    (pod / "serie.json").write_text(json.dumps({"episodios": [
        {"numero": 1, "arquivos": ["a.md"]}, {"numero": 2, "arquivos": ["a.md"]}]}), encoding="utf-8")
    roteiro = pod / "episodio_02_x.md"
    roteiro.write_text(_roteiro(repeticoes=3), encoding="utf-8")

    assert lint_arquivo(roteiro).status == "aviso"   # curto → sem L3; só L6
    assert main([str(roteiro)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "aviso"

    roteiro.write_text(_roteiro("[Professor]: x = 1", repeticoes=3), encoding="utf-8")
    assert main([str(roteiro)]) == 1

from src.podcast.script_io import dump, duracao_estimada_s, nome_arquivo, parse, slug

ROTEIRO = """---
episodio: 2
titulo: Gradiente
---
## Abertura
[Professor]: Hoje a gente fala de gradiente.
[Aprendiz]: Por que isso importa?

## Mecanismo
[Professor]: Porque ele aponta a direção de maior subida.
"""


def test_parse_frontmatter_blocos_e_falas():
    r = parse(ROTEIRO)
    assert r.frontmatter == {"episodio": 2, "titulo": "Gradiente"}
    assert r.blocos == ["Abertura", "Mecanismo"]
    assert [(f.papel, f.bloco) for f in r.falas] == [("Professor", 0), ("Aprendiz", 0), ("Professor", 1)]


def test_palavras_contam_so_o_texto_depois_do_rotulo():
    r = parse(ROTEIRO)
    assert r.palavras == 6 + 4 + 8


def test_dump_e_parse_ida_e_volta():
    fm = {"episodio": 1, "titulo": "Introdução à atenção", "fontes": ["01/a.md"]}
    corpo = "## Abertura\n[Professor]: Olá."
    r = parse(dump(fm, corpo))
    assert r.frontmatter == fm
    assert r.falas[0].texto == "Olá."


def test_duracao_estimada_150_palavras_por_minuto():
    assert duracao_estimada_s(150) == 60
    assert duracao_estimada_s(2500) == 1000


def test_slug_e_nome_de_arquivo_d4():
    assert slug("Atenção: é tudo!") == "atencao_e_tudo"
    assert len(slug("x" * 100)) == 40
    assert nome_arquivo(3, "Backpropagation", total=12) == "episodio_03_backpropagation.md"
    assert nome_arquivo(3, "Backpropagation", total=120) == "episodio_003_backpropagation.md"

from src.podcast import material


def _criar(tmp_path, arquivos: dict[str, str]):
    for rel, texto in arquivos.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")


def test_d1_exclui_dirs_e_arquivos_gerados(tmp_path):
    _criar(tmp_path, {
        "01_fund/a.md": "x", "02_av/b.md": "x", "raiz.md": "x",
        "transcripts/t.md": "x", "podcast/episodio_01_a.md": "x", "html/z.md": "x",
        ".obsidian/c.md": "x", "guia_de_estudos.md": "x", "sub/proximos_passos.md": "x",
        "fontes_selecionadas.md": "x",
    })
    assert material.arquivos_de_conteudo(tmp_path) == ["01_fund/a.md", "02_av/b.md", "raiz.md"]


def test_d2_ordem_do_guia_com_restante_alfabetico(tmp_path):
    _criar(tmp_path, {
        "01/a.md": "x", "01/b.md": "x", "02/c.md": "x", "02/d.md": "x",
        "guia_de_estudos.md": "Comece por [[c]], depois [[01/a|o A]] e [[c#secao]] de novo. [[inexistente]]",
    })
    assert material.ordem_do_guia(tmp_path) == ["02/c.md", "01/a.md", "01/b.md", "02/d.md"]


def test_d2_sem_guia_e_alfabetico(tmp_path):
    _criar(tmp_path, {"b.md": "x", "a.md": "x"})
    assert material.ordem_do_guia(tmp_path) == ["a.md", "b.md"]


def test_d3_posicao_do_episodio_e_a_menor():
    ordem = ["c.md", "a.md", "b.md"]
    assert material.posicao_do_episodio(["b.md", "a.md"], ordem) == 1


def test_d9_material_curto(tmp_path):
    _criar(tmp_path, {"a.md": "palavra " * 1499, "b.md": "palavra " * 1500})
    assert material.material_curto(tmp_path, ["a.md"]) is True
    assert material.material_curto(tmp_path, ["b.md"]) is False

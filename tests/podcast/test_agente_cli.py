"""CLI determinística usada pelo caminho do agente Claude (R38)."""
import json

from src.podcast import agente
from src.podcast.script_io import parse

from .fakes import critica, criar_pasta, roteiro_bom

MATERIAL = "# {t}\n\n" + "palavra " * 1600


def _pasta(tmp_path):
    return criar_pasta(tmp_path, {"01/a.md": MATERIAL.format(t="Gradiente"),
                                  "02/b.md": MATERIAL.format(t="Backpropagation")},
                       guia="[[a]] depois [[b]]")


def _plano(tmp_path, plano: dict):
    p = tmp_path / "plano.json"
    p.write_text(json.dumps(plano), encoding="utf-8")
    return p


PLANO = {"titulo_serie": "Redes", "episodios": [
    {"numero": 1, "titulo": "Gradiente", "arquivos": ["01/a.md"], "introduz": ["gradiente"], "retoma": [], "pontes": []},
    {"numero": 2, "titulo": "Backprop", "arquivos": ["02/b.md"], "introduz": ["backpropagation"],
     "retoma": [{"conceito": "gradiente", "episodio": 1}], "pontes": [{"alvo": "episodio:1", "ideia": "base"}]}]}


def test_fluxo_completo_do_agente(tmp_path, capsys):
    pasta = _pasta(tmp_path)
    assert agente.status(pasta)["serie"] == "ausente"

    plan = agente.planejamento(pasta)
    assert "Só valem as tags" in open(plan["entrada"], encoding="utf-8").read()

    out, cod = agente.serie(pasta, _plano(tmp_path, PLANO), replanejar=False, forcar=False)
    assert cod == 0 and [e["numero"] for e in out["episodios"]] == [1, 2]
    st = agente.status(pasta)
    assert st["serie"] == "valida" and [e["existe"] for e in st["episodios"]] == [False, False]

    ent = agente.entradas(pasta, 2)
    texto = open(ent["entradas"], encoding="utf-8").read()
    assert "episódio 2 de 2" in texto and "retomar o conceito 'gradiente'" in texto
    assert ent["roteiro"].endswith("episodio_02_backprop.md")

    # o sub-agente gerar-podcast escreveria isto:
    rot = roteiro_bom("[Professor]: Lembra do episódio um, quando vimos o gradiente?")
    open(ent["roteiro"], "w", encoding="utf-8").write(f"---\nepisodio: 2\n---\n{rot}\n")
    # e o podcast-critico, isto:
    crit = tmp_path / "critica.json"
    crit.write_text(json.dumps(critica()), encoding="utf-8")

    fim = agente.finalizar(pasta, 2, "claude-opus-5-5", 0, crit, False)
    assert (fim["lint"], fim["critica"]) == ("aprovado", "aprovado")
    assert fim["pontes"][0]["alvo"] == "episodio:1"
    fm = parse(open(ent["roteiro"], encoding="utf-8").read()).frontmatter
    assert fm["gerado_por"] == "claude-agent" and fm["provider"] == "anthropic"
    rel = json.loads((pasta / "podcast" / "relatorio.json").read_text(encoding="utf-8"))
    assert rel["execucoes"][-1]["episodios"][0]["episodio"] == 2


def test_serie_com_erros_pede_correcao_e_forcar_conserta(tmp_path):
    pasta = _pasta(tmp_path)
    ruim = {"titulo_serie": "X", "episodios": [{"numero": 1, "titulo": "A", "arquivos": ["01/a.md"],
                                                "introduz": [], "retoma": [], "pontes": []}]}
    out, cod = agente.serie(pasta, _plano(tmp_path, ruim), replanejar=False, forcar=False)
    assert cod == 3 and any("02/b.md" in e for e in out["erros"])
    assert not (pasta / "podcast" / "serie.json").exists()
    out, cod = agente.serie(pasta, _plano(tmp_path, ruim), replanejar=False, forcar=True)
    assert cod == 0 and len(out["episodios"]) == 2 and out["avisos"]


def test_finalizar_lint_reprovado_e_critica_quebrada(tmp_path):
    pasta = _pasta(tmp_path)
    agente.serie(pasta, _plano(tmp_path, PLANO), replanejar=False, forcar=False)
    ent = agente.entradas(pasta, 1)

    open(ent["roteiro"], "w", encoding="utf-8").write("---\nepisodio: 1\n---\n" + roteiro_bom("[Professor]: x = 1"))
    crit = tmp_path / "c.json"
    crit.write_text(json.dumps(critica()), encoding="utf-8")
    assert agente.finalizar(pasta, 1, "m", 1, crit, False)["critica"] == "nao_avaliado"

    open(ent["roteiro"], "w", encoding="utf-8").write("---\nepisodio: 1\n---\n" + roteiro_bom())
    crit.write_text("{não é json", encoding="utf-8")
    assert agente.finalizar(pasta, 1, "m", 0, crit, False)["critica"] == "indisponivel"   # fail-open


def test_backup_e_finalizar_restaura_quando_reescrita_quebra_o_lint(tmp_path):
    pasta = _pasta(tmp_path)
    agente.serie(pasta, _plano(tmp_path, PLANO), replanejar=False, forcar=False)
    ent = agente.entradas(pasta, 1)
    bom = "---\nepisodio: 1\n---\n" + roteiro_bom()
    open(ent["roteiro"], "w", encoding="utf-8").write(bom)
    crit = pasta / "podcast" / ".agente" / "critica_01.json"
    crit.write_text(json.dumps(critica(fidelidade=[{"fala": "f", "motivo": "m", "evidencia": ""}])), encoding="utf-8")

    agente.backup(pasta, 1)
    # reescrita quebrou o formato; a nova crítica nem rodou
    open(ent["roteiro"], "w", encoding="utf-8").write("---\nepisodio: 1\n---\n" + roteiro_bom("[Professor]: x = 1"))
    fim = agente.finalizar(pasta, 1, "m", 1, crit, False)
    assert fim["restaurado_do_backup"] is True
    assert (fim["lint"], fim["critica"]) == ("aprovado", "reprovado")   # versão e crítica anteriores
    assert "x = 1" not in open(ent["roteiro"], encoding="utf-8").read()


def test_cli_codigos_de_saida(tmp_path, capsys):
    vazia = criar_pasta(tmp_path / "v", {"transcripts/t.md": "x"})
    assert agente.main(["status", str(vazia)]) == 1
    assert "erro" in json.loads(capsys.readouterr().out)

import json
from pathlib import Path

import pytest

from src.podcast.normalize import normalizar

CASOS = json.loads((Path(__file__).parent / "normalize_casos.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("caso", CASOS, ids=[c["entrada"] for c in CASOS])
def test_tabela_de_casos(caso):
    assert normalizar(caso["entrada"]) == caso["saida"]


def test_deterministico():
    texto = "Em 2024, 95% de 1.000 exemplos e taxa 0.001"
    assert normalizar(texto) == normalizar(texto)


def test_taxa_de_aprendizado_no_padrao_ingles_nao_vira_milhar():
    assert normalizar("0.001") == "zero vírgula zero zero um"

"""LLM falso para os testes do estágio 1: responde por papel (planejador,
redator, crítico) a partir de filas configuradas pelo teste, e registra as chamadas."""
from __future__ import annotations
import json
from pathlib import Path

_P = "[Professor]: Pensa numa fila de banco em que cada pessoa passa a informação adiante, e o erro vai sendo corrigido aos poucos por todo mundo."
_A = "[Aprendiz]: Mas por que a correção começa pelo fim da fila e não pelo começo, e se a fila for muito longa?"


def roteiro_bom(*extra: str, repeticoes: int = 45) -> str:
    return "\n".join(["## Abertura", *([_P, _A] * repeticoes), *extra])


def critica(**problemas_por_criterio) -> dict:
    nomes = ("fidelidade", "pontes", "explicacao", "aprendiz", "integridade")
    return {
        "criterios": {n: {"problemas": problemas_por_criterio.get(n, [])} for n in nomes},
        "instrucoes_reescrita": "corrija" if problemas_por_criterio else "",
    }


class FakeLLM:
    def __init__(self, plano=None, roteiros=None, criticas=None):
        self.plano = list(plano or [])
        self.roteiros = list(roteiros or [])
        self.criticas = list(criticas or [])
        self.chamadas: list[tuple[str, float | None, list[dict]]] = []
        self.config = {"provider": "fake", "fake": {"model": "fake-1"}}

    @staticmethod
    def _papel(system: str) -> str:
        if system.startswith("Você planeja"):
            return "planejador"
        if system.startswith("Você revisa"):
            return "critico"
        return "redator"

    def chat(self, messages, system=None, max_tokens=0, temperature=None):
        papel = self._papel(system or "")
        self.chamadas.append((papel, temperature, messages))
        assert papel == "redator", papel
        return self.roteiros.pop(0)

    def chat_json(self, messages, system=None, max_tokens=0, temperature=None):
        papel = self._papel(system or "")
        self.chamadas.append((papel, temperature, messages))
        fila = self.plano if papel == "planejador" else self.criticas
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def papeis(self) -> list[str]:
        return [c[0] for c in self.chamadas]


def criar_pasta(tmp_path: Path, arquivos: dict[str, str], guia: str | None = None) -> Path:
    for rel, texto in arquivos.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")
    if guia is not None:
        (tmp_path / "guia_de_estudos.md").write_text(guia, encoding="utf-8")
    return tmp_path


def ler_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

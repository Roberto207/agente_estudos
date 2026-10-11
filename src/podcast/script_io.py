"""Leitura/escrita do roteiro de episódio: frontmatter (D11), falas (D6) e blocos."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field

import yaml

PALAVRAS_POR_MINUTO = 150

FALA_RE = re.compile(r"^\[(Professor|Aprendiz)\]: (.*\S.*)$")
BLOCO_RE = re.compile(r"^## (\S.*)$")


@dataclass
class Fala:
    papel: str        # "Professor" | "Aprendiz"
    texto: str
    bloco: int        # índice do bloco (-1 = antes do primeiro "## ")
    linha: int        # número da linha no corpo (1-based), para mensagens do lint


@dataclass
class Roteiro:
    frontmatter: dict
    corpo: str
    blocos: list[str] = field(default_factory=list)
    falas: list[Fala] = field(default_factory=list)

    @property
    def palavras(self) -> int:
        """D6: soma dos tokens depois do rótulo, antes de qualquer normalização."""
        return sum(len(f.texto.split()) for f in self.falas)


def separar_frontmatter(texto: str) -> tuple[dict, str]:
    if texto.startswith("---\n"):
        fim = texto.find("\n---\n", 4)
        if fim != -1:
            dados = yaml.safe_load(texto[4:fim]) or {}
            return (dados if isinstance(dados, dict) else {}), texto[fim + 5:]
    return {}, texto


def parse(texto: str) -> Roteiro:
    """Não valida — linhas fora do formato são ignoradas aqui e apontadas pelo lint."""
    frontmatter, corpo = separar_frontmatter(texto)
    roteiro = Roteiro(frontmatter=frontmatter, corpo=corpo)
    for n, linha in enumerate(corpo.splitlines(), start=1):
        if m := BLOCO_RE.match(linha):
            roteiro.blocos.append(m.group(1).strip())
        elif m := FALA_RE.match(linha):
            roteiro.falas.append(Fala(m.group(1), m.group(2).strip(), len(roteiro.blocos) - 1, n))
    return roteiro


def duracao_estimada_s(palavras: int) -> int:
    return round(palavras / PALAVRAS_POR_MINUTO * 60)


def dump(frontmatter: dict, corpo: str) -> str:
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n{corpo.strip()}\n"


def slug(titulo: str, limite: int = 40) -> str:
    """D4."""
    s = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:limite].strip("_") or "episodio"


def nome_arquivo(numero: int, titulo: str, total: int) -> str:
    """D4: `episodio_<NN>_<slug>.md` (3 dígitos se a série passar de 99)."""
    largura = 3 if total > 99 else 2
    return f"episodio_{numero:0{largura}d}_{slug(titulo)}.md"

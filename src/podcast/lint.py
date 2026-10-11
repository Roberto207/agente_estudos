"""Lint determinístico do roteiro (DEFINE R12–R18; DESIGN §6).

Roda antes do crítico LLM: é barato, não varia entre execuções e não pode ser
convencido por prompt injection. Também é usado pelo agente Claude
`gerar-podcast` via CLI:

    python -m src.podcast.lint <pasta>/podcast/episodio_03_xxx.md

Sai com código 1 quando o roteiro é reprovado.
"""
from __future__ import annotations
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from num2words import num2words

from . import material
from .script_io import BLOCO_RE, FALA_RE, parse, separar_frontmatter

PALAVRAS_MIN, PALAVRAS_MAX = 2000, 3200  # R13

# D7 — além das letras, dígitos e espaço. As variantes tipográficas (“ ” ‘ ’ … – —)
# são as mesmas pontuações faladas que modelos costumam emitir em pt-BR.
_PONTUACAO_OK = set(".,;:!?-'\"%“”‘’…–—")
_PONTO_ENTRE_LETRAS = re.compile(r"[^\W\d_]\.[^\W\d_]")  # loss.backward, np.array

# R17 — elogio à pergunta/dúvida, em qualquer papel (inclui as variações que um
# exemplo de prompt mal escolhido ensinou: "boa dúvida", "bela observação").
_BORDOES = re.compile(
    r"\b(ótima|ótimo|excelente|boa|bom|bela|belo|grande|que) (pergunta|dúvida|observação|questão|ponto)\b",
    re.IGNORECASE,
)

_EXTENSO = {num2words(n, lang="pt_BR"): n for n in range(1, 100)}
_MENCAO_EP = re.compile(
    r"\bepis[oó]dio\s+(\d{1,3}|"
    + "|".join(sorted(map(re.escape, _EXTENSO), key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
# Marcadores de passado: "episódio N" + um destes na mesma fala = "já visto".
_PASSADO = re.compile(
    r"\b(vimos|viu|vi|falamos|falou|aprendemos|aprendeu|estudamos|lembra|lembram|lembrando|"
    r"como a gente viu|já vimos|tínhamos)\b",
    re.IGNORECASE,
)
_EP_ANTERIOR = re.compile(r"\bepis[oó]dio (anterior|passado)\b|\b[uú]ltimo epis[oó]dio\b", re.IGNORECASE)
_PROXIMO_EP = re.compile(r"\bpr[oó]ximo epis[oó]dio\b", re.IGNORECASE)

_POR_QUE = re.compile(r"\bpor qu[eê]\b", re.IGNORECASE)
_E_SE = re.compile(r"\be se\b", re.IGNORECASE)
_CONCORDA = re.compile(r"\b(entendi|faz sentido|certo|legal|ok|beleza|show|claro|saquei)\b", re.IGNORECASE)


@dataclass
class Achado:
    codigo: str
    mensagem: str
    linha: int | None = None
    bloqueia: bool = True


@dataclass
class ResultadoLint:
    achados: list[Achado] = field(default_factory=list)

    @property
    def status(self) -> str:
        if any(a.bloqueia for a in self.achados):
            return "reprovado"
        return "aviso" if self.achados else "aprovado"

    @property
    def codigos(self) -> list[str]:
        return sorted({a.codigo for a in self.achados})

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "codigos": self.codigos,
            "achados": [a.__dict__ for a in self.achados],
        }


def _numero_mencionado(token: str) -> int:
    return int(token) if token.isdigit() else _EXTENSO[token.lower()]


def caracteres_invalidos(texto: str) -> list[str]:
    """D7: caracteres de uma fala fora da lista branca."""
    ruins = [c for c in texto if not (c.isalpha() or c.isdigit() or c == " " or c in _PONTUACAO_OK)]
    return sorted(set(ruins))


def lint(texto: str, numero: int, total: int, material_curto: bool = False) -> ResultadoLint:
    """Avalia o roteiro completo (com ou sem frontmatter) do episódio `numero` de `total`."""
    res = ResultadoLint()
    add = res.achados.append
    _, corpo = separar_frontmatter(texto)
    roteiro = parse(texto)

    # L1 — R12: só "## título", falas e linhas em branco.
    for n, linha in enumerate(corpo.splitlines(), start=1):
        if linha.strip() and not (BLOCO_RE.match(linha) or FALA_RE.match(linha)):
            add(Achado("L1", f"linha fora do formato: {linha[:80]!r}", n))
    if not roteiro.falas:
        add(Achado("L1", "nenhuma fala encontrada"))

    for f in roteiro.falas:
        # L2 — R14 / D7.
        if ruins := caracteres_invalidos(f.texto):
            add(Achado("L2", f"caracteres não falados: {' '.join(ruins)}", f.linha))
        if _PONTO_ENTRE_LETRAS.search(f.texto):
            add(Achado("L2", "ponto entre letras (código ou abreviação colada)", f.linha))
        # L5 — R17.
        if _BORDOES.search(f.texto):
            add(Achado("L5", f"elogio vazio: {_BORDOES.search(f.texto).group(0)!r}", f.linha))
        # L4 — R15.
        for m in _MENCAO_EP.finditer(f.texto):
            k = _numero_mencionado(m.group(1))
            if k > total:
                add(Achado("L4", f"cita o episódio {k}, mas a série tem {total}", f.linha))
            elif k >= numero and _PASSADO.search(f.texto):
                add(Achado("L4", f"trata o episódio {k} como já visto no episódio {numero}", f.linha))
        if numero == 1 and _EP_ANTERIOR.search(f.texto):
            add(Achado("L4", "episódio 1 citando episódio anterior", f.linha))
        if numero == total and _PROXIMO_EP.search(f.texto):
            add(Achado("L4", "último episódio prometendo um próximo episódio", f.linha))

    # L3 — R13 (limite inferior não se aplica a material curto, D9).
    p = roteiro.palavras
    if p > PALAVRAS_MAX or (p < PALAVRAS_MIN and not material_curto):
        add(Achado("L3", f"{p} palavras de fala (faixa {PALAVRAS_MIN}–{PALAVRAS_MAX})"))

    # L6 — R16 (aviso).
    if total > 1 and numero > 1:
        anteriores = [
            _numero_mencionado(m.group(1))
            for f in roteiro.falas for m in _MENCAO_EP.finditer(f.texto)
        ]
        if not any(k < numero for k in anteriores):
            add(Achado("L6", "nenhuma menção a episódio anterior", bloqueia=False))

    # L7 — R18 (aviso).
    aprendiz = [f for f in roteiro.falas if f.papel == "Aprendiz"]
    if not any(_POR_QUE.search(f.texto) for f in aprendiz):
        add(Achado("L7", "Aprendiz não pergunta 'por quê'", bloqueia=False))
    if not any(_E_SE.search(f.texto) for f in aprendiz):
        add(Achado("L7", "Aprendiz não pergunta 'e se'", bloqueia=False))

    # L8 — mais de 2 falas seguidas do Aprendiz que só concordam (aviso; o crítico decide).
    seguidas = 0
    for f in aprendiz:
        if len(f.texto.split()) <= 6 and _CONCORDA.search(f.texto) and "?" not in f.texto:
            seguidas += 1
            if seguidas == 3:
                add(Achado("L8", "Aprendiz concorda em mais de 2 falas seguidas", f.linha, bloqueia=False))
        else:
            seguidas = 0

    return res


def lint_arquivo(caminho: str | Path) -> ResultadoLint:
    """Infere número, total e material curto a partir do frontmatter e do
    serie.json da pasta (`<pasta>/podcast/<roteiro>.md`)."""
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8")
    fm, _ = separar_frontmatter(texto)
    pasta = caminho.parent.parent
    serie = json.loads((caminho.parent / "serie.json").read_text(encoding="utf-8"))
    numero = int(fm["episodio"])
    episodio = next(e for e in serie["episodios"] if e["numero"] == numero)
    curto = material.material_curto(pasta, episodio["arquivos"])
    return lint(texto, numero, len(serie["episodios"]), curto)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("uso: python -m src.podcast.lint <roteiro.md>", file=sys.stderr)
        return 2
    res = lint_arquivo(argv[0])
    print(json.dumps(res.as_dict(), ensure_ascii=False, indent=2))
    return 1 if res.status == "reprovado" else 0


if __name__ == "__main__":
    sys.exit(main())

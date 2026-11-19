"""Lista de flashcards propostos (`flashcards_propostos.md`): formato, parser, lint e merge.

O fluxo tem dois passos com revisão humana no meio:

    propor  -> <pasta>/flashcards_propostos.md   (o usuário aprova no Obsidian)
    montar  -> <pasta>/html/flashcards.html      (só os aprovados)

Este módulo não usa LLM, então tudo aqui é testável offline. O agente Claude
`criar-estudo` escreve o arquivo à mão seguindo prompts/flashcards_regras.md e
usa `python -m src.generators.flashcards_lista <pasta>` para validar.

Formato de cada card:

    - [ ] **P:** pergunta
      **R:** resposta
      **Fonte:** [[arquivo]]
      **Termos:**
      - [ ] `θ_t`: parâmetros do modelo depois do passo t.
      - [ ] `α`: taxa de aprendizado, o tamanho do passo.

`[x]` aprova; apagar o bloco descarta; copiar um bloco cria um card novo.
A seção **Termos** é opcional: cada linha é um subcard (botão lateral no HTML,
que abre a explicação do termo ou símbolo). Só os subcards marcados `[x]` entram
no HTML; os não marcados ficam só na lista.
"""
from __future__ import annotations
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

NOME_ARQUIVO = "flashcards_propostos.md"
NOME_ESTADO = "flashcards_estado.json"  # em <pasta>/.agente/

PERGUNTA_MAX = 300
RESPOSTA_MIN = 200  # resposta seca demais não traz o porquê nem o contexto
RESPOSTA_MAX = 1100
SIMILARIDADE_MAX = 0.7  # Jaccard de palavras entre perguntas

_CARD_RE = re.compile(
    r"^- \[(?P<marca>[ xX])\] \*\*P:\*\*[ \t]*(?P<p>.+?)[ \t]*\n"
    r"[ \t]+\*\*R:\*\*[ \t]*(?P<r>.+?)[ \t]*"
    r"(?:\n[ \t]+\*\*Fonte:\*\*[ \t]*(?P<f>.*?)[ \t]*)?"
    r"(?:\n[ \t]+\*\*Termos:\*\*[ \t]*(?P<t>(?:\n[ \t]+- \[[ xX]\] .+)*))?$",
    re.MULTILINE,
)
_TERMO_RE = re.compile(
    r"^[ \t]+- \[(?P<m>[ xX])\] `(?P<termo>[^`]+)`[ \t]*:[ \t]*(?P<e>.+?)[ \t]*$",
    re.MULTILINE,
)
_SECAO_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)

# LaTeX continua fora: o HTML é offline e mostra texto simples (unicode).
_LATEX = re.compile(r"\$|\\[a-zA-Z]+|[_^]\{")
# Símbolo de equação: letra grega, operador matemático, ou letra latina isolada com
# acento combinante, subscrito, sobrescrito ou `_` (m̂, v_t, g², β₁). Cada letra precisa
# de um subcard; operadores só exigem que o card tenha algum subcard.
_GREGO = "α-ωΑ-Ω"
_MARCAS = "\u0300-\u036f₀-₉⁰-⁹¹²³"
_SIMBOLO_LETRA = re.compile(rf"([{_GREGO}])|(?<![A-Za-z0-9_^])([A-Za-z])[{_MARCAS}_]")
_OPERADOR = re.compile(r"[√∑∫∂∇≈≤≥±∞×÷]")
_CITA_ARQUIVO = re.compile(
    r"\b(arquivo|se[cç][aã]o|figura|tabela|equa[cç][aã]o \d|p[aá]gina|cap[ií]tulo \d)\b|\beq\.",
    re.IGNORECASE,
)
# Pergunta que cobra raciocínio tem uma palavra interrogativa; sem ela, é de sim ou não.
_INTERROGATIVA = re.compile(
    r"\b(por ?que|como|qual|quais|o que|o quê|quando|onde|quem|quanto|quantos|quantas)\b",
    re.IGNORECASE,
)


@dataclass
class Termo:
    """Subcard: um termo ou símbolo do card e a sua explicação (botão lateral no HTML)."""
    termo: str
    explicacao: str
    aprovado: bool = False


@dataclass
class Card:
    pergunta: str
    resposta: str
    fonte: str = ""
    aprovado: bool = False
    secao: str = ""
    termos: list[Termo] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hash_id(self.pergunta)

    def como_dict(self) -> dict:
        d = {"pergunta": self.pergunta, "resposta": self.resposta}
        if self.fonte:
            d["fonte"] = self.fonte
        if self.termos:
            d["termos"] = [{"termo": t.termo, "explicacao": t.explicacao} for t in self.termos]
        return d


def hash_id(pergunta: str) -> str:
    """Mesmo hash djb2 do JavaScript do HTML (`hashId`), para o id bater nos dois lados."""
    h = 5381
    for ch in str(pergunta):
        # `(h << 5) + h + código`, com o mesmo truncamento em 32 bits do JS.
        for unit in _utf16_units(ch):
            h = ((h << 5) + h + unit) & 0xFFFFFFFF
    return "c" + _base36(h)


def _utf16_units(ch: str) -> list[int]:
    b = ch.encode("utf-16-le")
    return [int.from_bytes(b[i:i + 2], "little") for i in range(0, len(b), 2)]


def _base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


# ── Parser e render ───────────────────────────────────────────────────────────

def parse(texto: str) -> list[Card]:
    cards: list[Card] = []
    secoes = [(m.start(), m.group(1)) for m in _SECAO_RE.finditer(texto)]
    for m in _CARD_RE.finditer(texto):
        secao = ""
        for pos, nome in secoes:
            if pos < m.start():
                secao = nome
        termos = [
            Termo(t.group("termo").strip(), t.group("e").strip(), t.group("m").lower() == "x")
            for t in _TERMO_RE.finditer(m.group("t") or "")
        ]
        cards.append(Card(
            pergunta=m.group("p").strip(),
            resposta=m.group("r").strip(),
            fonte=(m.group("f") or "").strip(),
            aprovado=m.group("marca").lower() == "x",
            secao=secao,
            termos=termos,
        ))
    return cards


def render(cards: list[Card], titulo: str = "") -> str:
    linhas = [
        f"# Flashcards propostos — {titulo}".rstrip(" —"),
        "",
        "Marque `[x]` para aprovar. Apague o bloco para descartar. "
        "Para criar um card, copie um bloco e escreva o seu. "
        "Depois rode `python main.py --mode flashcards-montar --pasta <pasta>`.",
        "",
    ]
    por_secao: dict[str, list[Card]] = {}
    for c in cards:
        por_secao.setdefault(c.secao or "Geral", []).append(c)
    for secao, grupo in por_secao.items():
        linhas.append(f"## {secao}")
        linhas.append("")
        for c in grupo:
            linhas.append(f"- [{'x' if c.aprovado else ' '}] **P:** {_uma_linha(c.pergunta)}")
            linhas.append(f"  **R:** {_uma_linha(c.resposta)}")
            if c.fonte:
                linhas.append(f"  **Fonte:** {_uma_linha(c.fonte)}")
            if c.termos:
                linhas.append("  **Termos:**")
                for t in c.termos:
                    linhas.append(f"  - [{'x' if t.aprovado else ' '}] `{_uma_linha(t.termo)}`: {_uma_linha(t.explicacao)}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def _uma_linha(s: str) -> str:
    return " ".join(str(s).split())


# ── Lint ──────────────────────────────────────────────────────────────────────

@dataclass
class Relatorio:
    aceitos: list[Card] = field(default_factory=list)
    rejeitados: list[tuple[Card, str]] = field(default_factory=list)

    def resumo(self) -> str:
        linhas = [f"{len(self.aceitos)} aceitos, {len(self.rejeitados)} rejeitados"]
        for c, motivo in self.rejeitados:
            linhas.append(f"  - {motivo}: {c.pergunta[:80]}")
        return "\n".join(linhas)


def motivo_rejeicao(c: Card) -> str | None:
    if not c.pergunta.strip() or not c.resposta.strip():
        return "pergunta ou resposta vazia"
    if len(c.pergunta) > PERGUNTA_MAX:
        return f"pergunta com mais de {PERGUNTA_MAX} caracteres"
    if len(c.resposta) > RESPOSTA_MAX:
        return f"resposta com mais de {RESPOSTA_MAX} caracteres"
    if _LATEX.search(c.pergunta) or _LATEX.search(c.resposta):
        return "LaTeX não é suportado: escreva a fórmula em texto simples (unicode)"
    if _CITA_ARQUIVO.search(c.pergunta):
        return "pergunta cita arquivo, seção, figura ou tabela"
    if "?" not in c.pergunta:
        return "pergunta sem interrogação"
    if not _INTERROGATIVA.search(c.pergunta):
        return "pergunta de sim ou não"
    sem_cobertura = _simbolos_sem_subcard(c)
    if sem_cobertura:
        return "símbolo sem subcard em **Termos**: " + ", ".join(sorted(sem_cobertura))
    # Card já aprovado pelo usuário não é barrado por ser curto: a decisão é dele.
    if len(c.resposta) < RESPOSTA_MIN and not c.aprovado:
        return f"resposta com menos de {RESPOSTA_MIN} caracteres (falta porquê ou contexto)"
    return None


def _base(token: str) -> str:
    """Letra-base de um símbolo ou termo: sem acento combinante, subscrito nem sobrescrito."""
    nfd = unicodedata.normalize("NFD", token)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _simbolos(texto: str) -> set[str]:
    return {a or b for a, b in _SIMBOLO_LETRA.findall(texto)}


def _simbolos_sem_subcard(c: Card) -> set[str]:
    """Letras de símbolo usadas na pergunta ou resposta que nenhum subcard explica.

    Operadores (√, ×, ≤ ...) só exigem que o card tenha algum subcard.
    """
    texto = c.pergunta + " " + c.resposta
    letras = _simbolos(texto)
    tem_operador = bool(_OPERADOR.search(texto))
    if not letras and not tem_operador:
        return set()
    cobertas: set[str] = set()
    for t in c.termos:
        cobertas |= _simbolos(t.termo)
        limpo = _base(t.termo).strip()
        if len(limpo) == 1:
            cobertas.add(limpo)
    if not c.termos:
        return letras or {"operador matemático"}
    return letras - cobertas


def validar(cards: list[Card], conhecidos: list[Card] | None = None) -> Relatorio:
    """Separa aceitos e rejeitados. `conhecidos` são cards já na lista (duplicata contra eles)."""
    rel = Relatorio()
    vistos = list(conhecidos or [])
    for c in cards:
        motivo = motivo_rejeicao(c)
        if motivo is None:
            for outro in vistos:
                if outro.id == c.id or _similaridade(outro.pergunta, c.pergunta) >= SIMILARIDADE_MAX:
                    motivo = "duplicata"
                    break
        if motivo:
            rel.rejeitados.append((c, motivo))
        else:
            rel.aceitos.append(c)
            vistos.append(c)
    return rel


def _palavras(s: str) -> set[str]:
    sem_acento = unicodedata.normalize("NFD", s.lower())
    sem_acento = "".join(ch for ch in sem_acento if unicodedata.category(ch) != "Mn")
    return set(re.findall(r"[a-z0-9]{3,}", sem_acento))


def _similaridade(a: str, b: str) -> float:
    pa, pb = _palavras(a), _palavras(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


# ── Estado (reproposição sem repetir o que foi apagado) ───────────────────────

def _caminho_estado(pasta: str) -> Path:
    return Path(pasta) / ".agente" / NOME_ESTADO


def _ler_estado(pasta: str) -> dict:
    p = _caminho_estado(pasta)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"propostos": [], "descartados": []}


def _gravar_estado(pasta: str, estado: dict) -> None:
    p = _caminho_estado(pasta)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_lista(pasta: str) -> list[Card]:
    p = Path(pasta) / NOME_ARQUIVO
    return parse(p.read_text(encoding="utf-8")) if p.exists() else []


def gravar_lista(pasta: str, novos: list[Card], titulo: str = "", regerar: bool = False) -> Relatorio:
    """Valida `novos` e grava a lista.

    Sem `regerar`, recusa sobrescrever uma lista existente (ela guarda a sua revisão).
    Com `regerar`, mantém os cards atuais (e os `[x]`), acrescenta só os novos como `[ ]`
    e não repropõe o que o usuário apagou desde a última proposta.
    """
    destino = Path(pasta) / NOME_ARQUIVO
    existentes = ler_lista(pasta)
    if existentes and not regerar:
        raise FileExistsError(
            f"{destino} já existe e guarda a sua revisão. Use --regerar para acrescentar cards novos."
        )

    estado = _ler_estado(pasta)
    ids_atuais = {c.id for c in existentes}
    # sumiu do arquivo desde a última proposta = foi apagado de propósito
    descartados = set(estado["descartados"]) | (set(estado["propostos"]) - ids_atuais)

    candidatos = [c for c in novos if c.id not in descartados]
    rel = validar(candidatos, conhecidos=existentes)
    for c in novos:
        if c.id in descartados:
            rel.rejeitados.append((c, "já descartado por você antes"))

    todos = existentes + rel.aceitos
    destino.write_text(render(todos, titulo), encoding="utf-8")
    _gravar_estado(pasta, {
        "propostos": sorted({c.id for c in todos}),
        "descartados": sorted(descartados),
    })
    return rel


def aprovados(pasta: str, aprovar_todos: bool = False) -> list[Card]:
    """Cards que entram no HTML. Com `aprovar_todos`, entram todos os cards e todos os subcards;
    sem ele, só os cards `[x]`, cada um com apenas os subcards `[x]`."""
    cards = ler_lista(pasta)
    if aprovar_todos:
        return cards
    return [replace(c, termos=[t for t in c.termos if t.aprovado]) for c in cards if c.aprovado]


# ── CLI de validação (usada pelo agente Claude) ───────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("uso: python -m src.generators.flashcards_lista <pasta>")
        return 2
    pasta = args[0]
    cards = ler_lista(pasta)
    if not cards:
        print(f"nenhum card em {Path(pasta) / NOME_ARQUIVO}")
        return 1
    rel = validar(cards)
    print(f"{len(cards)} cards na lista; {rel.resumo()}")
    return 1 if rel.rejeitados else 0


if __name__ == "__main__":
    sys.exit(main())

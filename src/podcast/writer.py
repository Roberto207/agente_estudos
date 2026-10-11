"""Redator de episódio: monta o contexto (DESIGN §5) e chama o LLM (DEFINE R12–R18, R25/R26)."""
from __future__ import annotations
from pathlib import Path

from . import material
from .comum import Envelope, carregar_prompt, sanitizar_falavel, titulo_do_md
from .lint import _EXTENSO, _MENCAO_EP  # mesmo reconhecimento de D8 que o lint usa
from .script_io import parse

_MAX_TOKENS = 8192


# ── Contexto ──────────────────────────────────────────────────────────────────

def resumo_episodio(ep: dict, roteiro_path: Path | None) -> str:
    """Resumo DETERMINÍSTICO do que um episódio anterior cobriu: título, blocos
    (se o roteiro já existe) e conceitos de "introduz" escritos exatamente como
    o redator deve citá-los. Sem LLM: não soma chamada nem alucinação."""
    linhas = [f"Episódio {ep['numero']}: {ep['titulo']}"]
    if roteiro_path and roteiro_path.exists():
        blocos = parse(roteiro_path.read_text(encoding="utf-8")).blocos
        if blocos:
            linhas.append("Blocos: " + "; ".join(blocos))
    if ep.get("introduz"):
        linhas.append("Conceitos apresentados: " + "; ".join(ep["introduz"]))
    return "\n".join(linhas)


def pontes_filtradas(ep: dict, anteriores: dict[int, dict]) -> list[str]:
    """Some (a) ponte para episódio ≥ N ou para arquivo que não é de episódio
    anterior (série planejada antes desta regra) e (b) "retomada" cujo conceito
    não está nos conceitos do episódio citado (o 'dropout que nunca foi visto')."""
    n = ep["numero"]
    de_anteriores = {a for e in anteriores.values() for a in e.get("arquivos", [])}
    saida = []
    for p in ep.get("pontes", []):
        alvo = p["alvo"]
        if alvo.startswith("episodio:"):
            k = int(alvo[9:]) if alvo[9:].isdigit() else 0
            if not 0 < k < n:
                continue
        elif alvo.startswith("arquivo:") and alvo[8:] not in de_anteriores:
            continue
        saida.append(f"{alvo} — {p.get('ideia', '')}")
    for r in ep.get("retoma", []):
        k = r["episodio"]
        conceitos = {c.casefold() for c in anteriores.get(k, {}).get("introduz", [])}
        if 0 < k < n and r["conceito"].casefold() in conceitos:
            saida.append(f"episodio:{k} — retomar o conceito {r['conceito']!r}")
    return saida


def texto_material(pasta: Path, arquivos: list[str], limite: int) -> str:
    """Material do episódio dentro do orçamento, truncando cada arquivo de forma proporcional."""
    textos = [(rel, (pasta / rel).read_text(encoding="utf-8")) for rel in arquivos]
    total = sum(len(t) for _, t in textos) or 1
    partes = []
    for rel, t in textos:
        cota = max(500, int(limite * len(t) / total))
        partes.append(f"### Arquivo: {rel}\n{t[:cota]}")
    return "\n\n".join(partes)


def trechos_outras_pastas(config: dict, cfg: dict, pasta: Path, consulta: str) -> tuple[str, list[str]]:
    """R25/R26: só lê um índice que já existe — nunca cria nem atualiza
    (search_vault chamaria build_or_update_index, por isso não é usado aqui)."""
    raiz = str(cfg.get("rag_raiz") or "").strip()
    if not raiz:
        return "", []
    raiz_path = Path(raiz).expanduser()
    from ..indexer import EmbeddingClient, _index_path, _load_index, search

    index = _load_index(_index_path(raiz_path))
    if not index or not index.get("chunks"):
        return "", []
    try:
        dentro = pasta.resolve().relative_to(raiz_path.resolve()).as_posix() + "/"
    except ValueError:
        dentro = None
    resultados = search(index, consulta, EmbeddingClient(config), k=20)
    fora = [r for r in resultados if not (dentro and r["file"].startswith(dentro))][: int(cfg["rag_k"])]
    texto = "\n\n".join(f"[{r['file']}" + (f" — {r['heading']}" if r["heading"] else "") + f"]\n{r['text'][:800]}"
                        for r in fora)
    return texto, sorted({r["file"] for r in fora})


def situacao(ep: dict, serie: dict, pasta: Path, cfg: dict) -> dict:
    total = len(serie["episodios"])
    n = ep["numero"]
    palavras = material.palavras(pasta, ep["arquivos"])
    curto = palavras < material.LIMIAR_MATERIAL_CURTO
    proximo = next((e for e in serie["episodios"] if e["numero"] == n + 1), None)
    faixa = cfg["palavras"]
    return {
        "numero": n,
        "total": total,
        "primeiro": n == 1,
        "ultimo": n == total,
        "material_curto": curto,
        "palavras_material": palavras,
        "palavras_alvo": "o que o material sustentar" if curto else f"{faixa['min'] + 200} a {faixa['max'] - 200}",
        "introduz": ep.get("introduz", []),
        "proximo_tema": sanitizar_falavel(proximo["titulo"]) if proximo else "",
    }


def _situacao_texto(s: dict) -> str:
    sim = lambda v: "sim" if v else "não"  # noqa: E731
    return "\n".join([
        f"episódio {s['numero']} de {s['total']}",
        f"primeiro: {sim(s['primeiro'])}",
        f"último: {sim(s['ultimo'])}",
        f"material curto: {sim(s['material_curto'])} ({s['palavras_material']} palavras de material)",
        f"palavras-alvo de fala: {s['palavras_alvo']}",
        "conceitos centrais (introduz): " + ("; ".join(s["introduz"]) or "—"),
        f"tema do próximo episódio: {s['proximo_tema'] or '— (não há próximo)'}",
    ])


def montar_entradas(ep: dict, serie: dict, pasta: Path, config: dict, cfg: dict,
                    roteiros: dict[int, Path]) -> tuple[Envelope, dict, list[str]]:
    """Blocos compartilhados pelo redator e pelo crítico (mesmas entradas)."""
    anteriores = {e["numero"]: e for e in serie["episodios"] if e["numero"] < ep["numero"]}
    sit = situacao(ep, serie, pasta, cfg)
    outras, rag_usados = trechos_outras_pastas(
        config, cfg, pasta, f"{ep['titulo']}. " + "; ".join(ep.get("introduz", [])))
    env = Envelope()
    blocos = {
        "situacao": env.bloco("situacao", _situacao_texto(sit)),
        "material": env.bloco("material", texto_material(pasta, ep["arquivos"], cfg["max_chars_material"])),
        "episodios_anteriores": env.bloco("episodios_anteriores", "\n\n".join(
            resumo_episodio(e, roteiros.get(k)) for k, e in sorted(anteriores.items())) or "— (nenhum)"),
        "pontes_sugeridas": env.bloco("pontes_sugeridas",
                                      "\n".join(pontes_filtradas(ep, anteriores)) or "— (nenhuma)"),
        "outras_pastas": env.bloco("outras_pastas", outras or "— (nenhum)"),
    }
    blocos["_situacao"] = sit  # type: ignore[assignment]
    return env, blocos, rag_usados


# ── Chamadas ──────────────────────────────────────────────────────────────────

def _mensagem(env: Envelope, blocos: dict) -> str:
    ordem = ["situacao", "material", "episodios_anteriores", "pontes_sugeridas", "outras_pastas"]
    return "\n\n".join([env.cabecalho(), *(blocos[k] for k in ordem),
                        "Escreva agora o roteiro completo deste episódio."])


def _limpar_formato(texto: str) -> str:
    """Conserta deslizes de formato sem significado (cerca de código, preâmbulo
    antes do primeiro "## ") — o resto fica para o lint julgar."""
    linhas = [l for l in (texto or "").splitlines() if not l.strip().startswith("```")]
    inicio = next((i for i, l in enumerate(linhas) if l.startswith("## ")), 0)
    return "\n".join(linhas[inicio:]).strip()


def escrever(llm, cfg: dict, env: Envelope, blocos: dict) -> tuple[str, list[dict]]:
    system, _ = carregar_prompt("redator")
    msgs = [{"role": "user", "content": _mensagem(env, blocos)}]
    texto = _limpar_formato(llm.chat(msgs, system=system, max_tokens=_MAX_TOKENS,
                                     temperature=cfg["temperaturas"]["redator"]))
    return texto, msgs + [{"role": "assistant", "content": texto}]


def reescrever(llm, cfg: dict, conversa: list[dict], apontamentos: str) -> tuple[str, list[dict]]:
    system, _ = carregar_prompt("redator")
    msgs = conversa + [{"role": "user", "content": (
        "Reescreva o roteiro COMPLETO corrigindo os problemas abaixo, mantendo todas as REGRAS e o "
        "FORMATO DE SAÍDA. Responda só com o roteiro.\n\n" + apontamentos)}]
    texto = _limpar_formato(llm.chat(msgs, system=system, max_tokens=_MAX_TOKENS,
                                     temperature=cfg["temperaturas"]["redator"]))
    return texto, msgs + [{"role": "assistant", "content": texto}]


# ── Pontes efetivamente feitas (frontmatter D11) ──────────────────────────────

def pontes_no_texto(texto: str, ep: dict, serie: dict, pasta: Path) -> list[dict]:
    """Extração determinística: falas que mencionam (D8) episódio anterior, e
    falas que citam o título de um arquivo que não é fonte deste episódio."""
    n = ep["numero"]
    titulos = {}
    for outro in serie["episodios"]:
        for rel in outro["arquivos"]:
            if rel not in ep["arquivos"]:
                t = titulo_do_md(pasta / rel)
                if len(t) >= 6:
                    titulos[rel] = t.casefold()
    pontes = []
    for f in parse(texto).falas:
        for m in _MENCAO_EP.finditer(f.texto):
            tok = m.group(1)
            k = int(tok) if tok.isdigit() else _EXTENSO.get(tok.lower(), 0)
            if 0 < k < n:
                pontes.append({"alvo": f"episodio:{k}", "fala": f.texto[:200]})
        baixo = f.texto.casefold()
        for rel, t in titulos.items():
            if t in baixo:
                pontes.append({"alvo": f"arquivo:{rel}", "fala": f.texto[:200]})
    return pontes

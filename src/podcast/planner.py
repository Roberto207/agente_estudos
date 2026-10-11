"""Planejamento da série — serie.json (DEFINE R2–R5, R8–R11).

O LLM decide o agrupamento e os conceitos; o código garante cobertura,
unicidade, numeração (D3), "retoma" válido e pontes só para trás.
"""
from __future__ import annotations
import json
import shutil
from datetime import datetime
from pathlib import Path

from . import material
from .comum import Envelope, ErroPodcast, carregar_prompt, sanitizar_falavel, titulo_do_md
from .script_io import separar_frontmatter

SERIE = "serie.json"
_TENTATIVAS = 2  # reenvios com a lista de erros antes do conserto determinístico
MAX_CENTRAIS = 5  # "introduz" (v3): o resto vai para "menciona"
MAX_APOIO = 8     # "menciona" (v3): sem teto, 30 termos de glossário diluíam os centrais


def caminho_serie(pasta: Path) -> Path:
    return pasta / "podcast" / SERIE


def carregar_ou_planejar(llm, cfg: dict, pasta: Path, replanejar: bool = False,
                         avisos: list[str] | None = None) -> dict:
    avisos = avisos if avisos is not None else []
    arquivos = material.arquivos_de_conteudo(pasta)
    if not pasta.is_dir() or not arquivos:
        raise ErroPodcast(f"Nenhum .md de conteúdo em {pasta.resolve()} — gere o material escrito antes do podcast.")

    serie_path = caminho_serie(pasta)
    if serie_path.exists() and not replanejar:
        serie = _ler_serie_valida(serie_path, arquivos)
        return serie
    if serie_path.exists() and replanejar:
        arquivar(pasta)

    serie = planejar(llm, cfg, pasta, arquivos, avisos)
    serie_path.parent.mkdir(parents=True, exist_ok=True)
    serie_path.write_text(json.dumps(serie, ensure_ascii=False, indent=2), encoding="utf-8")
    return serie


def _ler_serie_valida(serie_path: Path, arquivos: list[str]) -> dict:
    """R3/R4: reutiliza só se for válido e cobrir exatamente o conjunto atual."""
    try:
        serie = json.loads(serie_path.read_text(encoding="utf-8"))
        listados = [a for ep in serie["episodios"] for a in ep["arquivos"]]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ErroPodcast(f"{serie_path} inválido ({exc}). Rode com --replanejar.") from exc
    novos = sorted(set(arquivos) - set(listados))
    removidos = sorted(set(listados) - set(arquivos))
    if novos or removidos:
        partes = []
        if novos:
            partes.append("novos: " + ", ".join(novos))
        if removidos:
            partes.append("removidos: " + ", ".join(removidos))
        raise ErroPodcast(
            f"serie.json não corresponde ao material atual ({'; '.join(partes)}). Rode com --replanejar."
        )
    return serie


def arquivar(pasta: Path) -> Path:
    """R5: move serie.json e os roteiros para podcast/arquivo/<data-hora>/."""
    podcast = pasta / "podcast"
    destino = podcast / "arquivo" / datetime.now().strftime("%Y%m%d-%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    for p in [podcast / SERIE, *sorted(podcast.glob("episodio_*.md"))]:
        if p.exists():
            shutil.move(str(p), destino / p.name)
    return destino


def mensagem_planejamento(pasta: Path, arquivos: list[str]) -> str:
    """Entrada do planejador — a mesma para o Python e para o agente Claude."""
    env = Envelope()
    lista = "\n".join(_descricao(pasta / rel, rel) for rel in arquivos)
    return "\n\n".join([
        env.cabecalho(),
        env.bloco("arquivos", lista),
        env.bloco("ordem_do_guia", "\n".join(material.ordem_do_guia(pasta, arquivos))),
    ])


def planejar(llm, cfg: dict, pasta: Path, arquivos: list[str], avisos: list[str]) -> dict:
    system, _ = carregar_prompt("planejador")
    ordem = material.ordem_do_guia(pasta, arquivos)
    msgs = [{"role": "user", "content": mensagem_planejamento(pasta, arquivos)}]

    plano: dict = {}
    for tentativa in range(_TENTATIVAS + 1):
        plano = llm.chat_json(msgs, system=system, max_tokens=4096,
                              temperature=cfg["temperaturas"]["planejador"])
        erros = validar(plano, arquivos)
        if not erros:
            break
        if tentativa < _TENTATIVAS:
            msgs = msgs + [
                {"role": "assistant", "content": json.dumps(plano, ensure_ascii=False)},
                {"role": "user", "content": "O plano tem estes erros — corrija e responda só o JSON completo:\n- "
                 + "\n- ".join(erros)},
            ]
    return consertar(plano, arquivos, ordem, avisos)


def _descricao(md: Path, rel: str, limite: int = 300) -> str:
    """Caminho | título | tamanho | seções | começo. As seções e o tamanho mostram o que o
    arquivo DESENVOLVE (300 caracteres sozinhos faziam arquivo denso parecer curto); o
    frontmatter YAML sai antes, senão as tags viravam "conceitos centrais"."""
    _, corpo = separar_frontmatter(md.read_text(encoding="utf-8"))
    linhas = corpo.splitlines()
    secoes = [l.lstrip("#").strip() for l in linhas if l.startswith(("## ", "### "))][:15]
    inicio = " ".join(l.strip() for l in linhas if l.strip() and not l.startswith("#"))[:limite]
    return (f"- {rel} | {titulo_do_md(md)} | {len(corpo.split())} palavras"
            f" | seções: {'; '.join(secoes) or '—'} | começo: {inicio}")


def validar(plano, arquivos: list[str]) -> list[str]:
    """Erros que justificam reenviar ao LLM (R9–R11)."""
    if not isinstance(plano, dict) or not isinstance(plano.get("episodios"), list) or not plano["episodios"]:
        return ["o JSON precisa de uma lista não vazia em 'episodios'"]
    erros = []
    vistos: dict[str, int] = {}
    introduz: dict[int, set[str]] = {}
    for ep in plano["episodios"]:
        if not isinstance(ep, dict) or not isinstance(ep.get("numero"), int):
            erros.append("todo episódio precisa de 'numero' inteiro")
            continue
        n = ep["numero"]
        introduz[n] = {str(c).strip().casefold() for c in ep.get("introduz", []) + ep.get("menciona", [])}
        if len(ep.get("introduz", [])) > MAX_CENTRAIS:
            erros.append(f"episódio {n}: {len(ep['introduz'])} conceitos em 'introduz' — no máximo "
                         f"{MAX_CENTRAIS} centrais; mova os demais para 'menciona'")
        for a in ep.get("arquivos", []):
            if a not in arquivos:
                erros.append(f"episódio {n}: arquivo inexistente {a!r}")
            elif a in vistos:
                erros.append(f"{a!r} aparece nos episódios {vistos[a]} e {n}")
            else:
                vistos[a] = n
        for p in ep.get("pontes", []):
            if len(str(p.get("ideia", "")).split()) > 20:
                erros.append(f"episódio {n}: 'ideia' de ponte com mais de 20 palavras")
    faltando = [a for a in arquivos if a not in vistos]
    if faltando:
        erros.append("arquivos sem episódio: " + ", ".join(faltando))
    for ep in plano["episodios"]:
        if not isinstance(ep, dict) or not isinstance(ep.get("numero"), int):
            continue
        for r in ep.get("retoma", []):
            k, c = r.get("episodio"), str(r.get("conceito", "")).strip().casefold()
            if not isinstance(k, int) or k >= ep["numero"] or c not in introduz.get(k, set()):
                erros.append(f"episódio {ep['numero']}: 'retoma' inválido {r} (precisa estar em 'introduz' ou 'menciona' de episódio anterior)")
    return erros


def consertar(plano, arquivos: list[str], ordem: list[str], avisos: list[str]) -> dict:
    """Garante R8–R11 por código depois das tentativas, registrando avisos."""
    episodios = []
    vistos: set[str] = set()
    for ep in (plano.get("episodios") if isinstance(plano, dict) else None) or []:
        if not isinstance(ep, dict):
            continue
        arqs = [a for a in ep.get("arquivos", []) if a in arquivos and a not in vistos]
        vistos.update(arqs)
        if arqs:
            episodios.append({**ep, "arquivos": arqs})
    for a in [a for a in ordem if a not in vistos]:
        avisos.append(f"planejador não alocou {a}; virou episódio próprio")
        episodios.append({"numero": None, "titulo": a.rsplit("/", 1)[-1][:-3].replace("_", " "),
                          "arquivos": [a], "introduz": [], "retoma": [], "pontes": []})

    # R8/D3: renumera pela posição na ordem do guia, remapeando referências.
    episodios.sort(key=lambda ep: material.posicao_do_episodio(ep["arquivos"], ordem))
    novo_de = {ep["numero"]: i for i, ep in enumerate(episodios, start=1)
               if isinstance(ep.get("numero"), int)}

    resultado = []
    for i, ep in enumerate(episodios, start=1):
        centrais = [str(c).strip() for c in ep.get("introduz", []) if str(c).strip()]
        apoio = [str(c).strip() for c in ep.get("menciona", []) if str(c).strip()]
        if len(centrais) > MAX_CENTRAIS:
            avisos.append(f"episódio {i}: {len(centrais)} conceitos centrais; "
                          f"os {len(centrais) - MAX_CENTRAIS} últimos foram para 'menciona'")
            centrais, apoio = centrais[:MAX_CENTRAIS], centrais[MAX_CENTRAIS:] + apoio
        # um conceito, um grupo
        chaves = {c.casefold() for c in centrais}
        apoio = [c for k, c in {c.casefold(): c for c in apoio}.items() if k not in chaves]
        if len(apoio) > MAX_APOIO:
            avisos.append(f"episódio {i}: {len(apoio)} conceitos de apoio; mantidos os {MAX_APOIO} primeiros")
            apoio = apoio[:MAX_APOIO]
        resultado.append({
            "numero": i,
            "titulo": sanitizar_falavel(str(ep.get("titulo") or f"Episódio {i}")) or f"Episódio {i}",
            "arquivos": ep["arquivos"],
            "introduz": centrais,
            "menciona": apoio,
            "retoma": [{"conceito": r.get("conceito"), "episodio": novo_de.get(r.get("episodio"))}
                       for r in ep.get("retoma", []) if isinstance(r, dict)],
            "pontes": [_remapear_ponte(p, novo_de) for p in ep.get("pontes", []) if isinstance(p, dict)],
        })

    # Central repetido de episódio anterior vira "retoma" (o redator não reensina do zero).
    centrais_antes: dict[str, int] = {}
    for ep in resultado:
        novos = []
        for c in ep["introduz"]:
            k = centrais_antes.get(c.casefold())
            if k is not None:
                ep["retoma"].append({"conceito": c, "episodio": k})
                avisos.append(f"episódio {ep['numero']}: {c!r} já era central no episódio {k}; virou 'retoma'")
            else:
                novos.append(c)
        ep["introduz"] = novos
        for c in novos:
            centrais_antes[c.casefold()] = ep["numero"]

    introduz = {ep["numero"]: {c.casefold() for c in ep["introduz"] + ep["menciona"]} for ep in resultado}
    episodio_do_arquivo = {a: ep["numero"] for ep in resultado for a in ep["arquivos"]}
    for ep in resultado:
        n = ep["numero"]
        validos = []
        for r in ep["retoma"]:
            k, c = r["episodio"], str(r["conceito"] or "").strip()
            if isinstance(k, int) and k < n and c.casefold() in introduz.get(k, set()):
                validos.append({"conceito": c, "episodio": k})
            else:
                avisos.append(f"episódio {n}: 'retoma' removido ({c!r} do episódio {k})")
        ep["retoma"] = validos
        pontes = []
        for p in ep["pontes"]:
            alvo = p["alvo"]
            if alvo.startswith("episodio:") and not (alvo[9:].isdigit() and int(alvo[9:]) < n):
                avisos.append(f"episódio {n}: ponte para {alvo} removida (só pontes para trás)")
            elif alvo.startswith("arquivo:") and alvo[8:] not in arquivos:
                avisos.append(f"episódio {n}: ponte para arquivo inexistente {alvo[8:]!r} removida")
            elif alvo.startswith("arquivo:") and episodio_do_arquivo.get(alvo[8:], 0) >= n:
                # arquivo deste episódio ou de um futuro: o redator não tem base para a ponte
                avisos.append(f"episódio {n}: ponte para {alvo[8:]!r} (episódio "
                              f"{episodio_do_arquivo[alvo[8:]]}) removida (só pontes para trás)")
            else:
                pontes.append({"alvo": alvo, "ideia": " ".join(str(p.get("ideia", "")).split()[:20])})
        ep["pontes"] = pontes

    titulo = str(plano.get("titulo_serie", "")) if isinstance(plano, dict) else ""
    return {"titulo_serie": sanitizar_falavel(titulo) or "Série", "episodios": resultado}


def _remapear_ponte(p: dict, novo_de: dict) -> dict:
    alvo = str(p.get("alvo", ""))
    if alvo.startswith("episodio:") and alvo[9:].isdigit():
        novo = novo_de.get(int(alvo[9:]))
        alvo = f"episodio:{novo}" if novo else "episodio:?"
    return {"alvo": alvo, "ideia": p.get("ideia", "")}


def validar_selecao(serie: dict, episodios: list[int]) -> None:
    """R7."""
    existentes = {ep["numero"] for ep in serie["episodios"]}
    invalidos = sorted(set(episodios) - existentes)
    if invalidos:
        raise ErroPodcast(
            f"--episodios com número(s) inexistente(s): {', '.join(map(str, invalidos))} "
            f"(a série tem {len(existentes)} episódio(s))."
        )

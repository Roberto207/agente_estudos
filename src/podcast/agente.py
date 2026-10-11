"""Ponte para o caminho do agente Claude (DEFINE R38; DESIGN §4).

No caminho Claude, o LLM é o próprio Claude (criar-estudo planeja; os
sub-agentes gerar-podcast e podcast-critico escrevem e criticam). Tudo que é
determinístico vem daqui — as MESMAS funções do caminho Python, para os dois
produzirem os mesmos artefatos. Nenhum subcomando chama LLM.

    python -m src.podcast.agente status       <pasta>
    python -m src.podcast.agente planejamento <pasta>
    python -m src.podcast.agente serie        <pasta> <plano.json> [--replanejar] [--forcar]
    python -m src.podcast.agente entradas     <pasta> <n>
    python -m src.podcast.agente finalizar    <pasta> <n> --modelo M --reescritas K
                                              [--critica <critica.json> | --critica-indisponivel]

Saída: JSON em stdout. Código 0 = ok; 1 = erro de uso (ErroPodcast); 3 = plano com
erros a corrigir (subcomando `serie` sem --forcar).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import yaml

from . import critic, material, planner, writer
from .comum import ErroPodcast, config_podcast
from .lint import lint
from .run import frontmatter, gravar_relatorio
from .script_io import dump, nome_arquivo, separar_frontmatter

_RAIZ = Path(__file__).resolve().parents[2]


def _config() -> dict:
    """Só a seção `podcast` (e embedding, se houver RAG) do config.yaml — sem chaves de LLM."""
    try:
        return yaml.safe_load((_RAIZ / "config.yaml").read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def _dir_agente(pasta: Path) -> Path:
    d = pasta / "podcast" / ".agente"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _serie(pasta: Path) -> dict:
    caminho = planner.caminho_serie(pasta)
    if not caminho.exists():
        raise ErroPodcast(f"{caminho} não existe — planeje a série primeiro (subcomando `serie`).")
    return planner._ler_serie_valida(caminho, material.arquivos_de_conteudo(pasta))


def _episodio(serie: dict, n: int) -> dict:
    planner.validar_selecao(serie, [n])
    return next(ep for ep in serie["episodios"] if ep["numero"] == n)


def _roteiros(pasta: Path, serie: dict) -> dict[int, Path]:
    total = len(serie["episodios"])
    return {ep["numero"]: pasta / "podcast" / nome_arquivo(ep["numero"], ep["titulo"], total)
            for ep in serie["episodios"]}


# ── Subcomandos ───────────────────────────────────────────────────────────────

def status(pasta: Path) -> dict:
    """R1/R3/R4: estado da série e quais episódios ainda não têm roteiro."""
    arquivos = material.arquivos_de_conteudo(pasta)
    if not arquivos:
        raise ErroPodcast(f"Nenhum .md de conteúdo em {pasta} — gere o material escrito antes do podcast.")
    caminho = planner.caminho_serie(pasta)
    if not caminho.exists():
        return {"serie": "ausente", "arquivos_de_conteudo": arquivos}
    try:
        serie = planner._ler_serie_valida(caminho, arquivos)
    except ErroPodcast as exc:
        return {"serie": "desatualizada_ou_invalida", "detalhe": str(exc)}
    roteiros = _roteiros(pasta, serie)
    return {"serie": "valida", "titulo_serie": serie["titulo_serie"], "episodios": [
        {"numero": ep["numero"], "titulo": ep["titulo"], "roteiro": str(roteiros[ep["numero"]]),
         "existe": roteiros[ep["numero"]].exists()} for ep in serie["episodios"]]}


def planejamento(pasta: Path) -> dict:
    arquivos = material.arquivos_de_conteudo(pasta)
    if not arquivos:
        raise ErroPodcast(f"Nenhum .md de conteúdo em {pasta}.")
    destino = _dir_agente(pasta) / "planejamento.md"
    destino.write_text(planner.mensagem_planejamento(pasta, arquivos), encoding="utf-8")
    return {"entrada": str(destino), "prompt": str(_RAIZ / "prompts" / "podcast_planejador.md"),
            "plano_saida_sugerido": str(_dir_agente(pasta) / "plano.json")}


def serie(pasta: Path, plano_json: Path, replanejar: bool, forcar: bool) -> tuple[dict, int]:
    arquivos = material.arquivos_de_conteudo(pasta)
    plano = json.loads(plano_json.read_text(encoding="utf-8"))
    erros = planner.validar(plano, arquivos)
    if erros and not forcar:
        return {"erros": erros, "instrucao": "corrija o plano e rode de novo; depois de 2 tentativas, use --forcar"}, 3
    caminho = planner.caminho_serie(pasta)
    arquivado = None
    if caminho.exists():
        if not replanejar:
            raise ErroPodcast(f"{caminho} já existe — use --replanejar para arquivar e substituir.")
        arquivado = str(planner.arquivar(pasta))
    avisos: list[str] = []
    resultado = planner.consertar(plano, arquivos, material.ordem_do_guia(pasta, arquivos), avisos)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"serie": str(caminho), "avisos": avisos, "arquivado_em": arquivado,
            "episodios": [{"numero": e["numero"], "titulo": e["titulo"], "arquivos": e["arquivos"]}
                          for e in resultado["episodios"]]}, 0


def entradas(pasta: Path, n: int) -> dict:
    """Mesmas entradas do redator e do crítico no caminho Python (DESIGN §5)."""
    config = _config()
    cfg = config_podcast(config)
    s = _serie(pasta)
    ep = _episodio(s, n)
    roteiros = _roteiros(pasta, s)
    env, blocos, rag = writer.montar_entradas(ep, s, pasta, config, cfg, roteiros)
    sit = blocos.pop("_situacao")
    ordem = ["situacao", "material", "episodios_anteriores", "pontes_sugeridas", "outras_pastas"]
    destino = _dir_agente(pasta) / f"entradas_{n:02d}.md"
    destino.write_text("\n\n".join([env.cabecalho(), *(blocos[k] for k in ordem)]) + "\n", encoding="utf-8")
    (_dir_agente(pasta) / f"rag_{n:02d}.json").write_text(json.dumps(rag), encoding="utf-8")
    return {"entradas": str(destino), "roteiro": str(roteiros[n]), "episodio": n,
            "total": len(s["episodios"]), "material_curto": sit["material_curto"],
            "palavras_alvo": sit["palavras_alvo"],
            "critica_saida_sugerida": str(_dir_agente(pasta) / f"critica_{n:02d}.json")}


def finalizar(pasta: Path, n: int, modelo: str, reescritas: int,
              critica_json: Path | None, critica_indisponivel: bool) -> dict:
    s = _serie(pasta)
    ep = _episodio(s, n)
    caminho = _roteiros(pasta, s)[n]
    _, texto = separar_frontmatter(caminho.read_text(encoding="utf-8"))
    curto = material.material_curto(pasta, ep["arquivos"])
    res = lint(texto, n, len(s["episodios"]), curto)

    resultado = None
    if res.status == "reprovado":
        veredito = "nao_avaliado"
    elif critica_indisponivel or critica_json is None:
        veredito = "indisponivel"
    else:
        try:
            resultado = critic.normalizar(json.loads(critica_json.read_text(encoding="utf-8")))
            veredito = "aprovado" if resultado["aprovado"] else "reprovado"
        except (ValueError, json.JSONDecodeError):
            veredito = "indisponivel"   # R23 — fail-open

    rag_path = _dir_agente(pasta) / f"rag_{n:02d}.json"
    rag = json.loads(rag_path.read_text()) if rag_path.exists() else []
    fm = frontmatter(texto.strip(), ep, s, pasta, res, veredito, resultado, reescritas, rag,
                     provider="anthropic", modelo=modelo, gerado_por="claude-agent")
    caminho.write_text(dump(fm, texto), encoding="utf-8")
    gravar_relatorio(pasta / "podcast", "anthropic", modelo, [{
        "episodio": n, "palavras": fm["palavras"], "lint": fm["lint"], "lint_codigos": fm["lint_codigos"],
        "critica": fm["critica"], "reescritas": reescritas, "segundos": None}], [])
    return {"roteiro": str(caminho), "palavras": fm["palavras"], "duracao_estimada_s": fm["duracao_estimada_s"],
            "lint": fm["lint"], "lint_codigos": fm["lint_codigos"], "critica": fm["critica"],
            "critica_problemas": fm["critica_problemas"], "pontes": fm["pontes"]}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.podcast.agente")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").add_argument("pasta")
    sub.add_parser("planejamento").add_argument("pasta")
    p = sub.add_parser("serie")
    p.add_argument("pasta"); p.add_argument("plano")
    p.add_argument("--replanejar", action="store_true"); p.add_argument("--forcar", action="store_true")
    p = sub.add_parser("entradas")
    p.add_argument("pasta"); p.add_argument("n", type=int)
    p = sub.add_parser("finalizar")
    p.add_argument("pasta"); p.add_argument("n", type=int)
    p.add_argument("--modelo", required=True); p.add_argument("--reescritas", type=int, default=0)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--critica"); g.add_argument("--critica-indisponivel", action="store_true")
    a = ap.parse_args(argv)

    pasta = Path(a.pasta).expanduser().resolve()
    codigo = 0
    try:
        if a.cmd == "status":
            out = status(pasta)
        elif a.cmd == "planejamento":
            out = planejamento(pasta)
        elif a.cmd == "serie":
            out, codigo = serie(pasta, Path(a.plano), a.replanejar, a.forcar)
        elif a.cmd == "entradas":
            out = entradas(pasta, a.n)
        else:
            out = finalizar(pasta, a.n, a.modelo, a.reescritas,
                            Path(a.critica) if a.critica else None, a.critica_indisponivel)
    except ErroPodcast as exc:
        out, codigo = {"erro": str(exc)}, 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return codigo


if __name__ == "__main__":
    sys.exit(main())

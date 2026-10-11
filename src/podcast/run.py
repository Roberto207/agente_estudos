"""Estágio 1 — `main.py --mode podcast` (DEFINE R1–R24; DESIGN §1).

planejador (1 chamada) → por episódio: redator → lint → [1 reescrita] →
crítico → [1 reescrita → lint → crítico] → grava roteiro + relatorio.json.
"""
from __future__ import annotations
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import critic, planner, writer
from .comum import ErroPodcast, carregar_prompt, config_podcast, provider_e_modelo
from .lint import lint
from .script_io import duracao_estimada_s, dump, nome_arquivo, parse

console = Console()


def run(config: dict, pasta: str, replanejar: bool = False, episodios: list[int] | None = None,
        llm=None) -> dict:
    from ..llm import LLMClient

    pasta_p = Path(pasta).expanduser().resolve()
    cfg = config_podcast(config)
    llm = llm or LLMClient(config)
    avisos: list[str] = []

    serie_existe = planner.caminho_serie(pasta_p).exists()
    if episodios and (replanejar or not serie_existe):
        # R7 pede validar antes de chamar o LLM — sem serie.json não há o que validar.
        raise ErroPodcast("--episodios exige um serie.json já planejado; rode primeiro sem --episodios.")

    serie = planner.carregar_ou_planejar(llm, cfg, pasta_p, replanejar=replanejar, avisos=avisos)
    total = len(serie["episodios"])
    if episodios:
        planner.validar_selecao(serie, episodios)

    podcast = pasta_p / "podcast"
    roteiros = {ep["numero"]: podcast / nome_arquivo(ep["numero"], ep["titulo"], total)
                for ep in serie["episodios"]}
    alvos = [ep for ep in serie["episodios"]
             if (ep["numero"] in episodios if episodios else not roteiros[ep["numero"]].exists())]

    console.print(f"\n[bold purple]Podcast[/bold purple] — {serie['titulo_serie']} "
                  f"({total} episódio(s); {len(alvos)} a gerar)")
    for a in avisos:
        console.print(f"  [yellow]aviso:[/yellow] {a}")

    linhas = []
    for ep in alvos:
        t0 = time.time()
        with console.status(f"[yellow]Episódio {ep['numero']}: {ep['titulo']}...[/yellow]"):
            fm = gerar_episodio(llm, config, cfg, pasta_p, serie, ep, roteiros)
        linhas.append({
            "episodio": ep["numero"], "palavras": fm["palavras"], "lint": fm["lint"],
            "lint_codigos": fm["lint_codigos"], "critica": fm["critica"],
            "reescritas": fm["reescritas"], "segundos": round(time.time() - t0, 1),
        })

    relatorio = _gravar_relatorio(podcast, config, linhas, avisos)
    _imprimir(linhas)
    return relatorio


def gerar_episodio(llm, config: dict, cfg: dict, pasta: Path, serie: dict, ep: dict,
                   roteiros: dict[int, Path]) -> dict:
    total = len(serie["episodios"])
    env, blocos, rag_usados = writer.montar_entradas(ep, serie, pasta, config, cfg, roteiros)
    curto = blocos["_situacao"]["material_curto"]

    texto, conversa = writer.escrever(llm, cfg, env, blocos)
    res = lint(texto, ep["numero"], total, curto)
    reescritas = 0
    resultado_critico = None

    if res.status == "reprovado":
        # R21: uma reescrita guiada pelas violações; se persistir, grava reprovado.
        texto, conversa = writer.reescrever(llm, cfg, conversa, _violacoes(res))
        reescritas += 1
        res = lint(texto, ep["numero"], total, curto)

    if res.status == "reprovado":
        critica = "nao_avaliado"
    else:
        resultado_critico = critic.avaliar(llm, cfg, env, blocos, texto)
        if resultado_critico is not None and not resultado_critico["aprovado"] and cfg["reescritas"] > 0:
            # R22: uma reescrita com os apontamentos; repassa lint e crítico.
            novo, _ = writer.reescrever(llm, cfg, conversa, critic.apontamentos(resultado_critico))
            reescritas += 1
            res_novo = lint(novo, ep["numero"], total, curto)
            if res_novo.status != "reprovado":
                texto, res = novo, res_novo
                resultado_critico = critic.avaliar(llm, cfg, env, blocos, texto)
            # Se a reescrita quebrou o formato, fica a versão anterior (já passou no
            # lint) com o veredito anterior — não se troca um problema por outro pior.
        if resultado_critico is None:
            critica = "indisponivel"   # R23 — fail-open
        else:
            critica = "aprovado" if resultado_critico["aprovado"] else "reprovado"

    provider, modelo = provider_e_modelo(config)
    fm = frontmatter(texto, ep, serie, pasta, res, critica, resultado_critico, reescritas,
                     rag_usados, provider, modelo, gerado_por="python")
    destino = roteiros[ep["numero"]]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(dump(fm, texto), encoding="utf-8")
    return fm


def frontmatter(texto: str, ep: dict, serie: dict, pasta: Path, res, critica: str,
                resultado_critico: dict | None, reescritas: int, rag_usados: list[str],
                provider: str, modelo: str, gerado_por: str) -> dict:
    """Frontmatter D11 — único para o caminho Python e o do agente Claude (R38)."""
    palavras = parse(texto).palavras
    return {
        "episodio": ep["numero"],
        "titulo": ep["titulo"],
        "fontes": ep["arquivos"],
        "pontes": writer.pontes_no_texto(texto, ep, serie, pasta),
        "rag_trechos": rag_usados,
        "prompts": {nome: carregar_prompt(nome)[1] for nome in ("planejador", "redator", "critico")},
        "provider": provider,
        "modelo": modelo,
        "gerado_por": gerado_por,
        "commit": _commit(),
        "data": datetime.now().astimezone().isoformat(timespec="seconds"),
        "palavras": palavras,
        "duracao_estimada_s": duracao_estimada_s(palavras),
        "lint": res.status,
        "lint_codigos": res.codigos,
        "critica": critica,
        "critica_problemas": critic.problemas_planos(resultado_critico) if resultado_critico else [],
        "reescritas": reescritas,
    }


def _violacoes(res) -> str:
    return "Violações de formato encontradas pelo verificador automático:\n" + "\n".join(
        f"- {a.codigo}: {a.mensagem}" + (f" (linha {a.linha})" if a.linha else "")
        for a in res.achados if a.bloqueia)


def _commit() -> str:
    try:
        raiz = Path(__file__).resolve().parents[2]
        # --dirty: o código que rodou tinha mudanças não commitadas (o hash sozinho mentiria).
        return subprocess.run(["git", "-C", str(raiz), "describe", "--always", "--dirty"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def _gravar_relatorio(podcast: Path, config: dict, linhas: list[dict], avisos: list[str]) -> dict:
    """R24: acrescenta esta execução a podcast/relatorio.json."""
    return gravar_relatorio(podcast, *provider_e_modelo(config), linhas, avisos)


def gravar_relatorio(podcast: Path, provider: str, modelo: str, linhas: list[dict], avisos: list[str]) -> dict:
    caminho = podcast / "relatorio.json"
    podcast.mkdir(parents=True, exist_ok=True)
    try:
        historico = json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        historico = {"execucoes": []}
    execucao = {"data": datetime.now().astimezone().isoformat(timespec="seconds"),
                "provider": provider, "modelo": modelo, "avisos": avisos, "episodios": linhas}
    historico["execucoes"].append(execucao)
    caminho.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
    return execucao


def _imprimir(linhas: list[dict]) -> None:
    if not linhas:
        console.print("[dim]Nada a gerar — todos os episódios já têm roteiro (use --episodios para refazer).[/dim]")
        return
    t = Table(title="Roteiros", border_style="purple")
    for col in ("Ep.", "Palavras", "Lint", "Crítica", "Reescritas", "Tempo"):
        t.add_column(col)
    cor = {"aprovado": "green", "aviso": "yellow", "reprovado": "red",
           "indisponivel": "yellow", "nao_avaliado": "dim"}
    for l in linhas:
        t.add_row(str(l["episodio"]), str(l["palavras"]),
                  f"[{cor[l['lint']]}]{l['lint']}[/] {' '.join(l['lint_codigos'])}",
                  f"[{cor.get(l['critica'], 'white')}]{l['critica']}[/]",
                  str(l["reescritas"]), f"{l['segundos']}s")
    console.print(t)

"""Crítico LLM do roteiro (DEFINE R20, R22, R23).

O LLM só lista problemas por critério; `ok` e `aprovado` são calculados aqui
(o veredito global gerado antes dos critérios enviesava a resposta), e as
citações são truncadas aqui (o LLM conta caracteres mal).
"""
from __future__ import annotations

from .comum import Envelope, carregar_prompt

CRITERIOS = ("fidelidade", "pontes", "explicacao", "aprendiz", "integridade")
_MAX_CITACAO = 300
_MAX_TOKENS = 4096


def avaliar(llm, cfg: dict, env: Envelope, blocos: dict, roteiro: str) -> dict | None:
    """Retorna {"aprovado", "criterios": {nome: {"ok", "problemas"}}, "instrucoes_reescrita"}
    ou None se o crítico falhar (o chamador grava `critica: indisponivel`, R23)."""
    system, _ = carregar_prompt("critico")
    ordem = ["situacao", "material", "episodios_anteriores", "pontes_sugeridas", "outras_pastas"]
    msg = "\n\n".join([env.cabecalho(), *(blocos[k] for k in ordem),
                       env.bloco("roteiro", roteiro), "Avalie o roteiro."])
    try:
        # chat_json já reenvia uma vez quando o JSON vem malformado (json_retries).
        bruto = llm.chat_json([{"role": "user", "content": msg}], system=system,
                              max_tokens=_MAX_TOKENS, temperature=cfg["temperaturas"]["critico"])
        return normalizar(bruto)
    except Exception:
        return None


def normalizar(bruto) -> dict:
    """Valida o schema e calcula ok/aprovado. Levanta ValueError se inválido."""
    if not isinstance(bruto, dict) or not isinstance(bruto.get("criterios"), dict):
        raise ValueError("resposta do crítico sem 'criterios'")
    criterios = {}
    for nome in CRITERIOS:
        item = bruto["criterios"].get(nome)
        if not isinstance(item, dict) or not isinstance(item.get("problemas", []), list):
            raise ValueError(f"critério ausente ou malformado: {nome}")
        problemas = [
            {k: str(p.get(k, ""))[:_MAX_CITACAO] for k in ("fala", "motivo", "evidencia")}
            for p in item.get("problemas", []) if isinstance(p, dict)
        ]
        criterios[nome] = {"ok": not problemas, "problemas": problemas}
    return {
        "aprovado": all(c["ok"] for c in criterios.values()),
        "criterios": criterios,
        "instrucoes_reescrita": str(bruto.get("instrucoes_reescrita", ""))[:1500],
    }


def apontamentos(resultado: dict) -> str:
    """Texto enviado ao redator na reescrita — contradições primeiro."""
    linhas = []
    for nome in CRITERIOS:
        for p in resultado["criterios"][nome]["problemas"]:
            linhas.append(f"- [{nome}] {p['motivo']} (fala: {p['fala']!r}"
                          + (f"; fonte: {p['evidencia']!r}" if p["evidencia"] else "") + ")")
    if resultado["instrucoes_reescrita"]:
        linhas.append("\nOrientação do revisor: " + resultado["instrucoes_reescrita"])
    return "\n".join(linhas)


def problemas_planos(resultado: dict) -> list[dict]:
    return [{"criterio": nome, **p} for nome in CRITERIOS for p in resultado["criterios"][nome]["problemas"]]

"""
Next Steps: analisa materiais de estudo e recomenda caminhos pós-estudo.

Gera proximos_passos.md com:
  - Síntese do que foi coberto
  - Caminho principal (próximos tópicos sequenciais)
  - Desvios pertinentes (fora do escopo mas valiosos)
  - Conexões inesperadas com outras áreas
"""
from __future__ import annotations
from datetime import date
from pathlib import Path

from ..llm import LLMClient


_SYSTEM = """\
Você é um orientador pedagógico especialista em IA, ML e tecnologia.
Analisará os materiais de estudo fornecidos e gerará recomendações de caminhos.

Produza o arquivo markdown EXATAMENTE neste formato (substitua os colchetes):

# O Que Estudar a Seguir — {tema}

> Análise gerada em {data}. Baseada nos materiais em `{pasta}`.

---

## O Que Você Já Cobriu
[1 parágrafo honesto sintetizando conceitos estudados e profundidade atingida. Mencione lacunas se existirem.]

---

## 🗺️ Caminho Principal
*Próximos passos diretos para aprofundar no tema (3–5 tópicos, do mais urgente ao menos):*

### 1. [Nome do tópico]
**Por quê agora**: [o que você já sabe que habilita este passo]
**Próxima busca**: `python buscar_fontes.py --tema "[tópico]" --foco "[aspecto específico]"`

### 2. [Nome do tópico]
**Por quê agora**: [...]
**Próxima busca**: `python buscar_fontes.py --tema "[...]" --foco "[...]"`

[Continue para 3–5 tópicos]

---

## 🔀 Desvios Pertinentes
*Tópicos que fogem do caminho principal mas enriquecem genuinamente o entendimento (2–4):*

### [Nome do desvio]
**Conexão**: [como se relaciona com o que foi estudado — seja específico, cite conceitos reais]
**Por que vale**: [justificativa não óbvia — evite o genérico]
**Quando estudar**: [antes do próximo passo | em paralelo com X | depois de dominar Y]

[Continue para 2–4 desvios]

---

## 🕸️ Conexões Inesperadas
*Como este tema conecta-se com áreas aparentemente distantes (2–3 pontes):*

- **[Área distante]**: [ponte não trivial — o que do material estudado reaparece nessa área]
- **[Área distante]**: [...]

---

## Próxima Ação Sugerida

```bash
python buscar_fontes.py --tema "[tópico mais urgente do caminho principal]" --foco "[foco específico]"
```

---

REGRAS:
- Escreva em português brasileiro
- Seja específico — cite conceitos, técnicas e termos reais do material analisado
- Nos desvios, prefira conexões não triviais. Exemplo ruim: "leia sobre deep learning" se o tema é redes neurais.
  Exemplo bom: "Teoria da Informação (Shannon entropy aparece na função de perda cross-entropy)"
- NÃO recomende o óbvio nem repita o que já foi estudado
- O objetivo é expandir a visão além do esperado, mostrando onde esse conhecimento leva de forma não linear
"""


def generate(llm: LLMClient, pasta: str) -> str | None:
    """Lê os .md da pasta e gera proximos_passos.md. Retorna o caminho ou None."""
    pasta_path = Path(pasta)

    md_files = sorted([
        f for f in pasta_path.rglob("*.md")
        if "transcripts" not in f.parts
        and f.name not in ("guia_de_estudos.md", "proximos_passos.md")
    ])

    if not md_files:
        return None

    parts: list[str] = []
    for f in md_files[:15]:
        try:
            text = f.read_text(encoding="utf-8")
            rel = f.relative_to(pasta_path)
            parts.append(f"### {rel}\n{text[:4000]}")
        except Exception:
            pass

    if not parts:
        return None

    tema = pasta_path.name.replace("_", " ").replace("-", " ").title()
    context = "\n\n---\n\n".join(parts)

    system = (
        _SYSTEM
        .replace("{tema}", tema)
        .replace("{data}", date.today().isoformat())
        .replace("{pasta}", str(pasta_path))
    )

    prompt = (
        f"Analise os materiais de estudo sobre '{tema}' abaixo "
        f"e gere as recomendações de próximos passos.\n\n"
        f"**Materiais** ({len(md_files)} arquivo(s)):\n\n{context}"
    )

    content = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        max_tokens=3000,
    )

    out_path = pasta_path / "proximos_passos.md"
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)

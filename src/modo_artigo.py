"""Modo artigo: material de estudo sobre UM artigo/paper.

As regras vivem em prompts/modo_artigo.md (fonte única, compartilhada com o
agente Claude criar-estudo) e em prompts/regras_didaticas.md. Este módulo só as
carrega e monta o system prompt do loop agêntico.
"""
from __future__ import annotations
import re
from pathlib import Path

_PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _ler(nome: str) -> str:
    caminho = _PROMPTS / nome
    if not caminho.exists():
        raise FileNotFoundError(f"Regras do modo artigo ausentes: {caminho}")
    texto = caminho.read_text(encoding="utf-8")
    # remove o comentário HTML de cabeçalho (nota de manutenção, não é instrução)
    return re.sub(r"\A\s*<!--.*?-->\s*", "", texto, count=1, flags=re.S)


def regras_modo_artigo() -> str:
    return _ler("modo_artigo.md")


def regras_didaticas() -> str:
    return _ler("regras_didaticas.md")


_INTRO = """\
Você é um agente especialista em criar material de estudo de alta qualidade, em português
brasileiro, a partir de UM artigo (paper). Você trabalha com as ferramentas disponíveis e decide
a ordem das chamadas.

## Produto final deste modo

Escreva na pasta destino (não crie subpastas temáticas):
- `NN_leitura_<artigo>_parte1.md` e `NN_leitura_<artigo>_parte2.md` (ou um único `NN_leitura_<artigo>.md`
  se couber em até uns 7 mil palavras): a leitura linear, na ordem do artigo, autossuficiente.
  Cada parte entre 4 e 6 mil palavras, cortada numa fronteira de seção do artigo.
- `NN_apoio_<artigo>.md` só se houver glossário realmente grande.
- `NN_perguntas_passo1.md` só se o usuário pedir as perguntas do ticket.
- `transcripts/paper_1.md`: um resumo curto do artigo e a lista dos números que você conferiu.
NÃO crie `guia_de_estudos.md`, TL;DR/Resumo/Conteúdo Completo, canvas, flashcards nem quiz: o formato
é o descrito nas regras abaixo. Não use blockquote (`>`) nem callouts do Obsidian.

## Processo

1. Crie `transcripts/` com `create_directory`.
2. Leia o TEXTO COMPLETO do paper com `fetch_url` (para PDFs a ferramenta devolve o texto inteiro, com
   tabelas e notas de rodapé). Se o texto vier cortado ou ilegível, tente de novo com a URL do PDF
   (`https://arxiv.org/pdf/<id>`). Não escreva nada a partir do abstract nem da memória.
3. Reconstrua as tabelas e confira cada número contra uma relação do próprio texto.
4. Escreva cada parte em UMA chamada de `write_file`, completa (sem rascunho parcial).
5. Confira o checklist final das regras antes de encerrar e responda com um resumo curto do que foi criado.

Escreva sempre em português brasileiro.
"""


def system_modo_artigo() -> str:
    return (
        _INTRO
        + "\n\n# REGRAS DO MODO ARTIGO\n\n" + regras_modo_artigo()
        + "\n\n# REGRAS DIDÁTICAS (valem junto)\n\n" + regras_didaticas()
    )

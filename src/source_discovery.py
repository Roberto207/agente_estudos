"""
Source Discovery: descobre e cura fontes de estudo de alta qualidade.

Busca em três camadas progressivas:
  fundamentos — survey papers, tutoriais introdutórios, vídeos de base
  moderno     — técnicas recentes (2023-2025), papers avançados
  pratico     — repos GitHub, notebooks, tutoriais com código real
"""
from __future__ import annotations
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus

import requests

from .llm import LLMClient
from .tools.web import web_search as _web_search

_HEADERS = {"User-Agent": "agente-estudos/1.0"}

_CURATION_SYSTEM = """\
Você é um curador especialista em materiais de estudo para IA, ML e tecnologia.
Receberá uma lista de resultados brutos de busca (YouTube, papers, GitHub, artigos).

Sua tarefa:
1. Remover duplicatas e resultados irrelevantes para o tema
2. Classificar cada resultado em: "fundamentos", "moderno" ou "pratico"
3. Atribuir score 0-10 por relevância e qualidade educacional
   (papers muito citados e vídeos de canais reconhecidos pontuam mais alto)
4. Escrever uma justificativa concisa em português brasileiro (1 frase, seja específico)

Responda APENAS com JSON válido, sem markdown, sem texto extra:
{
  "fontes": [
    {
      "url": "...",
      "titulo": "...",
      "tipo": "youtube|paper|github|article",
      "camada": "fundamentos|moderno|pratico",
      "score": 8.5,
      "motivo": "...",
      "metadata": {}
    }
  ]
}

Ordene por score decrescente dentro de cada camada.
Inclua no máximo {max_per_camada} fontes por camada.
Priorize: papers com citações, vídeos com muitas visualizações de canais técnicos, repos com estrelas.
Descarte: resultados pagos, marketing, conteúdo superficial.
"""


@dataclass
class DiscoveredSource:
    url: str
    titulo: str
    tipo: str     # "youtube" | "paper" | "github" | "article"
    camada: str   # "fundamentos" | "moderno" | "pratico"
    score: float  # 0.0–10.0
    motivo: str
    metadata: dict = field(default_factory=dict)


class SourceDiscoverer:
    def __init__(self, config: dict, llm: LLMClient) -> None:
        self._config = config
        self._llm = llm
        self._disc_cfg = config.get("source_discovery", {})

    def discover(self, tema: str, foco: str = "", max_per_camada: int = 5) -> list[DiscoveredSource]:
        queries = self._build_queries(tema, foco)
        raw: list[dict] = []

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = []
            for camada, qs in queries.items():
                futures.append(pool.submit(self._search_youtube, qs, camada))
                futures.append(pool.submit(self._search_papers, qs, camada))
                futures.append(pool.submit(self._search_github, qs, camada))
                futures.append(pool.submit(self._search_articles, qs, camada))
            for fut in as_completed(futures):
                try:
                    raw.extend(fut.result())
                except Exception:
                    pass

        return self._curate_with_llm(raw, tema, foco, max_per_camada)

    # ── Queries ───────────────────────────────────────────────────────────────

    def _build_queries(self, tema: str, foco: str) -> dict[str, list[str]]:
        t, f = tema, foco or tema
        return {
            "fundamentos": [
                f"{t} introduction fundamentals tutorial",
                f"{f} survey overview beginner explained",
                f"introdução {t} tutorial site:youtube.com",
            ],
            "moderno": [
                f"{t} {f} state of the art 2024 2025",
                f"{f} advanced paper arxiv recent",
                f"{t} {f} latest improvements techniques",
            ],
            "pratico": [
                f"{t} {f} implementation code tutorial",
                f"awesome {t} site:github.com",
                f"{t} {f} production architecture real world examples",
            ],
        }

    # ── YouTube ───────────────────────────────────────────────────────────────

    def _search_youtube(self, queries: list[str], camada: str) -> list[dict]:
        results: list[dict] = []
        min_dur = self._disc_cfg.get("min_youtube_duration", 300)

        for q in queries[:2]:
            try:
                proc = subprocess.run(
                    ["yt-dlp", "--dump-json", "--skip-download", "--flat-playlist",
                     f"ytsearch10:{q}"],
                    capture_output=True, text=True, timeout=30,
                )
                for line in proc.stdout.strip().splitlines():
                    try:
                        info = json.loads(line)
                        duration = info.get("duration") or 0
                        if duration < min_dur:
                            continue
                        vid_id = info.get("id", "")
                        if not vid_id:
                            continue
                        results.append({
                            "url": f"https://www.youtube.com/watch?v={vid_id}",
                            "titulo": info.get("title", ""),
                            "tipo": "youtube",
                            "camada_hint": camada,
                            "metadata": {
                                "duration": duration,
                                "view_count": info.get("view_count", 0),
                                "uploader": info.get("uploader", ""),
                            },
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue
            except Exception:
                # Fallback: DuckDuckGo
                try:
                    for r in _web_search(f"site:youtube.com {q}", max_results=3):
                        if "youtube.com/watch" in r.get("url", ""):
                            results.append({
                                "url": r["url"],
                                "titulo": r["title"],
                                "tipo": "youtube",
                                "camada_hint": camada,
                                "metadata": {},
                            })
                except Exception:
                    pass

        return results

    # ── Papers ────────────────────────────────────────────────────────────────

    def _search_papers(self, queries: list[str], camada: str) -> list[dict]:
        results: list[dict] = []
        for q in queries[:2]:
            results.extend(self._arxiv_search(q, camada))
            results.extend(self._semantic_scholar_search(q, camada))
        return results

    def _arxiv_search(self, query: str, camada: str) -> list[dict]:
        try:
            q = quote_plus(query)
            url = (
                f"https://export.arxiv.org/api/query"
                f"?search_query=ti:{q}+OR+abs:{q}&max_results=5&sortBy=relevance"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            if resp.status_code != 200:
                return []
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(resp.text)
            results = []
            for entry in root.findall("atom:entry", ns):
                title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
                id_el = entry.find("atom:id", ns)
                link = (id_el.text or "").strip() if id_el is not None else ""
                abstract = (entry.findtext("atom:summary", "", ns) or "")[:300].strip()
                published = (entry.findtext("atom:published", "", ns) or "")[:10]
                if link and title:
                    results.append({
                        "url": link,
                        "titulo": title,
                        "tipo": "paper",
                        "camada_hint": camada,
                        "metadata": {"abstract": abstract, "published": published},
                    })
            return results
        except Exception:
            return []

    def _semantic_scholar_search(self, query: str, camada: str) -> list[dict]:
        try:
            q = quote_plus(query)
            url = (
                f"https://api.semanticscholar.org/graph/v1/paper/search"
                f"?query={q}&fields=title,year,citationCount,externalIds&limit=5"
            )
            resp = requests.get(url, headers=_HEADERS, timeout=20)
            if resp.status_code != 200:
                return []
            results = []
            for paper in resp.json().get("data", []):
                ext = paper.get("externalIds") or {}
                arxiv_id = ext.get("ArXiv", "")
                doi = ext.get("DOI", "")
                link = (
                    f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id
                    else f"https://doi.org/{doi}" if doi
                    else ""
                )
                if not link or not paper.get("title"):
                    continue
                results.append({
                    "url": link,
                    "titulo": paper["title"],
                    "tipo": "paper",
                    "camada_hint": camada,
                    "metadata": {
                        "citationCount": paper.get("citationCount", 0),
                        "year": paper.get("year", ""),
                    },
                })
            return results
        except Exception:
            return []

    # ── GitHub ────────────────────────────────────────────────────────────────

    def _search_github(self, queries: list[str], camada: str) -> list[dict]:
        results: list[dict] = []
        min_stars = self._disc_cfg.get("min_github_stars", 100)
        headers = dict(_HEADERS)
        token = self._disc_cfg.get("github_token", "")
        if token:
            headers["Authorization"] = f"token {token}"

        for q in queries[:2]:
            try:
                q_enc = quote_plus(q)
                url = f"https://api.github.com/search/repositories?q={q_enc}&sort=stars&per_page=5"
                resp = requests.get(url, headers=headers, timeout=20)
                if resp.status_code != 200:
                    raise ValueError(f"GitHub API {resp.status_code}")
                for repo in resp.json().get("items", []):
                    if repo.get("stargazers_count", 0) < min_stars:
                        continue
                    results.append({
                        "url": repo["html_url"],
                        "titulo": repo["full_name"],
                        "tipo": "github",
                        "camada_hint": camada,
                        "metadata": {
                            "stars": repo.get("stargazers_count", 0),
                            "description": repo.get("description", ""),
                            "topics": repo.get("topics", []),
                        },
                    })
            except Exception:
                # Fallback: DuckDuckGo
                try:
                    for r in _web_search(f"site:github.com {q}", max_results=3):
                        gh_url = r.get("url", "")
                        # Keep only repo-level URLs (not files)
                        parts = gh_url.replace("https://github.com/", "").split("/")
                        if len(parts) == 2 and gh_url.startswith("https://github.com/"):
                            results.append({
                                "url": gh_url,
                                "titulo": r["title"],
                                "tipo": "github",
                                "camada_hint": camada,
                                "metadata": {},
                            })
                except Exception:
                    pass

        return results

    # ── Articles ──────────────────────────────────────────────────────────────

    def _search_articles(self, queries: list[str], camada: str) -> list[dict]:
        results: list[dict] = []
        for q in queries[:1]:
            try:
                for r in _web_search(q, max_results=5):
                    url = r.get("url", "")
                    if any(x in url for x in ("youtube.com", "github.com", "arxiv.org")):
                        continue
                    results.append({
                        "url": url,
                        "titulo": r["title"],
                        "tipo": "article",
                        "camada_hint": camada,
                        "metadata": {"snippet": r.get("snippet", "")},
                    })
            except Exception:
                pass
        return results

    # ── LLM Curation ──────────────────────────────────────────────────────────

    def _curate_with_llm(
        self, raw: list[dict], tema: str, foco: str, max_per_camada: int
    ) -> list[DiscoveredSource]:
        if not raw:
            return []

        # Deduplicar por URL
        seen: set[str] = set()
        deduped: list[dict] = []
        for r in raw:
            if r.get("url") and r["url"] not in seen:
                seen.add(r["url"])
                deduped.append(r)

        raw_json = json.dumps(deduped[:60], ensure_ascii=False, indent=2)
        system = _CURATION_SYSTEM.replace("{max_per_camada}", str(max_per_camada))
        prompt = (
            f"Tema de estudo: {tema}\n"
            f"Foco: {foco or tema}\n\n"
            f"Resultados brutos ({len(deduped)} itens):\n{raw_json}"
        )

        try:
            response = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                max_tokens=4096,
            )
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```[a-z]*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)

            data = json.loads(text)
            valid_fields = DiscoveredSource.__dataclass_fields__
            return [
                DiscoveredSource(**{k: v for k, v in src.items() if k in valid_fields})
                for src in data.get("fontes", [])
                if src.get("url") and src.get("titulo")
            ]
        except Exception:
            # Fallback: retorna resultados raw sem curadoria LLM
            return [
                DiscoveredSource(
                    url=r["url"],
                    titulo=r["titulo"],
                    tipo=r["tipo"],
                    camada=r.get("camada_hint", "fundamentos"),
                    score=5.0,
                    motivo="[curadoria automática indisponível]",
                    metadata=r.get("metadata", {}),
                )
                for r in deduped[:15]
            ]

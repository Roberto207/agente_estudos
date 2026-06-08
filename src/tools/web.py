from __future__ import annotations
import re
import requests


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/120.0 Safari/537.36"
    )
}


def fetch_url(url: str, timeout: int = 30) -> str:
    """Faz download de uma URL e retorna o texto limpo."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return _extract_text(resp.text)
    except Exception as exc:
        return f"[Erro ao buscar {url}: {exc}]"


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Busca na web via DuckDuckGo. Retorna lista de {title, url, snippet}."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in raw
        ]
    except ImportError:
        return _ddg_html_fallback(query, max_results)
    except Exception as exc:
        return [{"title": "Erro na busca", "url": "", "snippet": str(exc)}]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_text(html: str) -> str:
    """Extrai texto legível do HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 40]
        return "\n".join(lines[:400])
    except ImportError:
        # fallback sem bs4
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:20000]


def _ddg_html_fallback(query: str, max_results: int) -> list[dict]:
    """Fallback: scraping do HTML lite do DuckDuckGo."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "br-pt"},
            headers=_HEADERS,
            timeout=15,
        )
        urls = re.findall(r'class="result__a" href="([^"]+)"', resp.text)
        titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', resp.text)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', resp.text)
        results = []
        for i, url in enumerate(urls[:max_results]):
            results.append({
                "title": titles[i].strip() if i < len(titles) else "",
                "url": url,
                "snippet": snippets[i].strip() if i < len(snippets) else "",
            })
        return results
    except Exception as exc:
        return [{"title": "Erro na busca fallback", "url": "", "snippet": str(exc)}]

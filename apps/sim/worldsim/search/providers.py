"""Free SearchProvider implementations — default DuckDuckGo Instant Answer."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ..config import SearchConfig

logger = logging.getLogger("worldsim.search")

_HTML_TAG = re.compile(r"<[^>]+>")
_SCRIPTISH = re.compile(r"(?is)(ignore previous|system prompt|你是|jailbreak)")

# Public Instant Answer endpoint (no key). Attribution: DuckDuckGo.
DDG_INSTANT_ENDPOINT = "https://api.duckduckgo.com/"


@dataclass
class SearchHit:
    title: str
    snippet: str
    source_url: str
    provider: str
    trust: str = "unverified"
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def sanitize_text(text: str, max_len: int = 400) -> str:
    t = _HTML_TAG.sub(" ", text or "")
    t = t.replace("\n", " ").strip()
    t = re.sub(r"\s+", " ", t)
    if _SCRIPTISH.search(t):
        t = _SCRIPTISH.sub("[filtered]", t)
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return t


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        """Return ≤ budget snippets; empty on failure."""


class DuckDuckGoProvider(SearchProvider):
    """Default free provider: DuckDuckGo Instant Answer API (no key).

    Endpoint: https://api.duckduckgo.com/?q=…&format=json&no_html=1
    Notes: Instant Answer ≠ full web SERP; many queries return empty Abstract.
    ToS: respect DuckDuckGo terms; attribute when displaying; no API key required.
    """

    name = "duckduckgo"

    def __init__(
        self,
        endpoint: str = DDG_INSTANT_ENDPOINT,
        timeout: float = 4.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/") + "/"
        self.timeout = timeout

    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(
                    self.endpoint,
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                    headers={"User-Agent": "WorldSim/0.2 (educational; DuckDuckGo Instant Answer)"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("duckduckgo Instant Answer failed: %s", exc)
            return []

        hits: list[SearchHit] = []
        abstract = sanitize_text(data.get("AbstractText") or "")
        if abstract:
            hits.append(
                SearchHit(
                    title=sanitize_text(data.get("Heading") or query, 80),
                    snippet=abstract,
                    source_url=data.get("AbstractURL") or "https://duckduckgo.com/",
                    provider=self.name,
                )
            )
        for topic in data.get("RelatedTopics") or []:
            if len(hits) >= budget:
                break
            if isinstance(topic, dict) and topic.get("Text"):
                hits.append(
                    SearchHit(
                        title=sanitize_text((topic.get("Text") or "")[:40], 80),
                        snippet=sanitize_text(topic.get("Text") or ""),
                        source_url=topic.get("FirstURL") or "https://duckduckgo.com/",
                        provider=self.name,
                    )
                )
            elif isinstance(topic, dict) and topic.get("Topics"):
                for sub in topic["Topics"]:
                    if len(hits) >= budget:
                        break
                    if isinstance(sub, dict) and sub.get("Text"):
                        hits.append(
                            SearchHit(
                                title=sanitize_text((sub.get("Text") or "")[:40], 80),
                                snippet=sanitize_text(sub.get("Text") or ""),
                                source_url=sub.get("FirstURL") or "https://duckduckgo.com/",
                                provider=self.name,
                            )
                        )
        if hits:
            logger.info("duckduckgo returned %d hit(s) for %r", len(hits), query)
        else:
            logger.info("duckduckgo empty Instant Answer for %r", query)
        return hits[:budget]


class WikimediaProvider(SearchProvider):
    """Optional knowledge plugin: zh.wikipedia Action API (free, no key)."""

    name = "wikimedia"

    def __init__(
        self,
        endpoint: str = "https://zh.wikipedia.org/w/api.php",
        timeout: float = 4.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        headers = {
            "User-Agent": "WorldSim/0.2 (virtual-life sim; educational; contact=local-dev)",
        }
        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                sr = client.get(
                    self.endpoint,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": min(budget, 3),
                        "format": "json",
                        "utf8": 1,
                    },
                )
                sr.raise_for_status()
                results = (sr.json().get("query") or {}).get("search") or []
                hits: list[SearchHit] = []
                for item in results[:budget]:
                    title = item.get("title") or query
                    er = client.get(
                        self.endpoint,
                        params={
                            "action": "query",
                            "prop": "extracts",
                            "exintro": 1,
                            "explaintext": 1,
                            "titles": title,
                            "format": "json",
                            "utf8": 1,
                        },
                    )
                    er.raise_for_status()
                    pages = (er.json().get("query") or {}).get("pages") or {}
                    extract = ""
                    for page in pages.values():
                        extract = page.get("extract") or ""
                        break
                    snippet = sanitize_text(extract or _HTML_TAG.sub("", item.get("snippet") or title))
                    if not snippet:
                        continue
                    url = f"https://zh.wikipedia.org/wiki/{quote(title)}"
                    hits.append(
                        SearchHit(
                            title=sanitize_text(title, 80),
                            snippet=snippet,
                            source_url=url,
                            provider=self.name,
                        )
                    )
                if hits:
                    logger.info("wikimedia returned %d hit(s) for %r", len(hits), query)
                return hits
        except Exception as exc:  # noqa: BLE001
            logger.info("wikimedia failed: %s", exc)
            return []


class SearxngProvider(SearchProvider):
    """Optional local SearXNG JSON API — better full SERP when Docker is up."""

    name = "searxng"

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        url = f"{self.base_url}/search"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(
                    url,
                    params={"q": query, "format": "json"},
                    headers={"User-Agent": "WorldSim/0.2 (local SearXNG)"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("searxng unavailable at %s: %s", self.base_url, exc)
            return []

        hits: list[SearchHit] = []
        for item in (data.get("results") or [])[:budget]:
            snippet = sanitize_text(item.get("content") or item.get("title") or "")
            if not snippet:
                continue
            hits.append(
                SearchHit(
                    title=sanitize_text(item.get("title") or query, 80),
                    snippet=snippet,
                    source_url=item.get("url") or self.base_url,
                    provider=self.name,
                )
            )
        if hits:
            logger.info("searxng returned %d hit(s) for %r", len(hits), query)
        return hits


class LocalKnowledgeProvider(SearchProvider):
    """Offline canned facts — last-resort fallback when network providers empty."""

    name = "local_knowledge"

    FACTS: list[tuple[str, str, str]] = [
        (
            "城市公园",
            "城市公园与绿道适合短时放松；晴天户外活动常让人情绪更平稳，但并非世界天气字段的真相源。",
            "local://knowledge/park",
        ),
        (
            "通勤",
            "地铁与公交通勤会消耗精力；高峰拥挤可能抬高唤醒，宜预留缓冲时间。",
            "local://knowledge/commute",
        ),
        (
            "日用品",
            "家中日用品与食材不足时，可去商业点补给；这是资源缺口的常见触发。",
            "local://knowledge/staples",
        ),
        (
            "独处",
            "晚间独自在家时，适度社交或爱好可缓解空落感；需要时也可向信任的人倾诉。",
            "local://knowledge/companionship",
        ),
        (
            "天气",
            "气象信息应以来自模拟世界的 weather 字段为准；网上摘要可能过时，仅作信念参考。",
            "local://knowledge/weather",
        ),
        (
            "睡眠",
            "成人常见作息倾向夜间在家休息；睡眠不足会降低精力与愉悦。",
            "local://knowledge/sleep",
        ),
    ]

    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        scored: list[tuple[int, tuple[str, str, str]]] = []
        for title, snip, url in self.FACTS:
            score = 0
            for token in re.split(r"\s+", (query or "").strip()):
                if token and (token in title or token in snip):
                    score += 2
            for key in ("公园", "户外", "通勤", "地铁", "日用品", "独处", "陪伴", "天气", "睡眠", "精力"):
                if key in query and key in (title + snip):
                    score += 3
            if score == 0 and any(k in query for k in ("学习", "好奇", "知识", "查", "Python", "地球")):
                score = 1
            if score > 0:
                scored.append((score, (title, snip, url)))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            title, snip, url = self.FACTS[0]
            scored = [(1, (title, snip, url))]
        return [
            SearchHit(
                title=title,
                snippet=sanitize_text(snip),
                source_url=url,
                provider=self.name,
            )
            for _, (title, snip, url) in scored[:budget]
        ]


class CompositeSearchProvider(SearchProvider):
    """Try providers in priority order until enough hits."""

    name = "composite"

    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = providers

    def retrieve(self, query: str, budget: int = 3) -> list[SearchHit]:
        collected: list[SearchHit] = []
        for p in self.providers:
            if len(collected) >= budget:
                break
            try:
                chunk = p.retrieve(query, budget=budget - len(collected))
            except Exception as exc:  # noqa: BLE001
                logger.info("provider %s error: %s", p.name, exc)
                continue
            collected.extend(chunk)
        return collected[:budget]


def build_search_stack(cfg: SearchConfig) -> SearchProvider | None:
    """Wire providers: optional SearXNG → default DuckDuckGo → Wikimedia → local fallback."""
    if not cfg.enabled:
        logger.info("搜索学习已关闭（search.enabled=false）")
        return None

    pc = cfg.providers
    ordered: list[SearchProvider] = []
    names: list[str] = []

    # Optional upgrade: local SearXNG first when enabled (better full SERP)
    if pc.searxng.enabled:
        ordered.append(
            SearxngProvider(base_url=pc.searxng.base_url, timeout=pc.searxng.timeout_sec)
        )
        names.append("searxng")

    default = (cfg.default_provider or "duckduckgo").strip().lower()
    # Aliases
    if default in ("ddg", "ddg_instant", "duckduckgo_instant"):
        default = "duckduckgo"

    def _add_default() -> None:
        if default == "duckduckgo" and pc.duckduckgo.enabled:
            ordered.append(
                DuckDuckGoProvider(
                    endpoint=pc.duckduckgo.endpoint,
                    timeout=pc.duckduckgo.timeout_sec,
                )
            )
            names.append("duckduckgo")
        elif default == "wikimedia" and pc.wikimedia.enabled:
            ordered.append(
                WikimediaProvider(
                    endpoint=pc.wikimedia.endpoint,
                    timeout=pc.wikimedia.timeout_sec,
                )
            )
            names.append("wikimedia")
        elif default == "local_knowledge" and pc.local_knowledge.enabled:
            ordered.append(LocalKnowledgeProvider())
            names.append("local_knowledge")
        else:
            # Always wire DuckDuckGo if default unknown but duckduckgo enabled
            if pc.duckduckgo.enabled and "duckduckgo" not in names:
                ordered.append(
                    DuckDuckGoProvider(
                        endpoint=pc.duckduckgo.endpoint,
                        timeout=pc.duckduckgo.timeout_sec,
                    )
                )
                names.append("duckduckgo")
                logger.warning(
                    "未知 default_provider=%r — 回退接线 duckduckgo",
                    cfg.default_provider,
                )

    _add_default()

    # Knowledge supplement (if not already the default)
    if pc.wikimedia.enabled and "wikimedia" not in names:
        ordered.append(
            WikimediaProvider(
                endpoint=pc.wikimedia.endpoint,
                timeout=pc.wikimedia.timeout_sec,
            )
        )
        names.append("wikimedia")

    # Offline last resort
    if pc.local_knowledge.enabled and "local_knowledge" not in names:
        ordered.append(LocalKnowledgeProvider())
        names.append("local_knowledge")

    if not ordered:
        logger.info("未配置可用 SearchProvider — 跳过对外学习")
        return None

    logger.info(
        "SearchProvider 栈已接线：default=%s order=%s",
        cfg.default_provider,
        names,
    )
    if len(ordered) == 1:
        return ordered[0]
    return CompositeSearchProvider(ordered)

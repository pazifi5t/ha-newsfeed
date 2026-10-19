"""Katalog der Themen und Quellen.

Priorität: 3 = redaktionelle Top-/Schlagzeilen-Liste, 2 = Kernressort,
1 = ergänzende Quelle. Eigene Feeds lassen sich pro Thema in der
Konfiguration ergänzen.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from .feeds import Source


@dataclass(frozen=True)
class Topic:
    """Ein Themengebiet mit seinen Quellen."""

    key: str
    name: str
    icon: str
    sources: tuple[Source, ...]

    def source(self, key: str) -> Source | None:
        return next((s for s in self.sources if s.key == key), None)

    @property
    def default_sources(self) -> list[str]:
        return [s.key for s in self.sources if s.default]


def google_news(query: str) -> str:
    """Google-News-RSS-Suche (deutsch). Für Magazine ohne eigenen Feed."""
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(f"{query} when:7d")
        + "&hl=de&gl=DE&ceid=DE:de"
    )


TOPICS: dict[str, Topic] = {
    "it": Topic(
        key="it",
        name="IT",
        icon="mdi:laptop",
        sources=(
            Source("heise_top", "heise online Top-News",
                   "https://www.heise.de/rss/heise-top-atom.xml", priority=3, default=True),
            Source("heise_security", "heise Security",
                   "https://www.heise.de/security/rss/news-atom.xml", priority=2, default=True),
            Source("heise_ix", "iX",
                   "https://www.heise.de/ix/rss/news-atom.xml", priority=1),
            Source("heise_developer", "heise Developer",
                   "https://www.heise.de/developer/rss/news-atom.xml", priority=1),
            Source("spiegel_netzwelt", "SPIEGEL Netzwelt",
                   "https://www.spiegel.de/netzwelt/index.rss", priority=1),
        ),
    ),
    "politik": Topic(
        key="politik",
        name="Politik",
        icon="mdi:bank",
        sources=(
            Source("spiegel_politik", "SPIEGEL Politik",
                   "https://www.spiegel.de/politik/index.rss", priority=2, default=True),
            Source("spiegel_ausland", "SPIEGEL Ausland",
                   "https://www.spiegel.de/ausland/index.rss", priority=1),
            Source("spiegel_wirtschaft", "SPIEGEL Wirtschaft",
                   "https://www.spiegel.de/wirtschaft/index.rss", priority=1),
            Source("spiegel_schlagzeilen", "SPIEGEL Schlagzeilen (Gewichtung)",
                   "https://www.spiegel.de/schlagzeilen/index.rss",
                   priority=3, default=True, boost_only=True),
        ),
    ),
    "jagd": Topic(
        key="jagd",
        name="Jagd",
        icon="mdi:pine-tree",
        sources=(
            Source("wildundhund", "WILD UND HUND",
                   google_news("site:wildundhund.de"), priority=2, default=True,
                   strip_source_suffix=True),
            Source("pirsch", "PIRSCH",
                   google_news("site:pirsch.de"), priority=2, default=True,
                   strip_source_suffix=True),
            Source("jagderleben", "jagderleben (JÄGER / Unsere Jagd)",
                   google_news("site:jagderleben.de"), priority=2, default=True,
                   strip_source_suffix=True),
            Source("djz", "Deutsche Jagdzeitung",
                   google_news("site:djz.de"), priority=1,
                   strip_source_suffix=True),
            Source("djv", "Deutscher Jagdverband",
                   google_news("site:jagdverband.de"), priority=1,
                   strip_source_suffix=True),
            Source("jagd_presse", "Jagd in der Tagespresse",
                   google_news('(Jagd OR Jäger OR Jagdverband) -"Jagd auf"'), priority=1,
                   strip_source_suffix=True),
        ),
    ),
}

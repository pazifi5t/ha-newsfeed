"""Feed-Logik ohne Home-Assistant-Abhängigkeit: Parsen, Zeitfenster, Dubletten, Ranking.

Bewusst von Home Assistant getrennt, damit sie sich einfach testen lässt.
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SUMMARY_LENGTH = 280


class FeedError(Exception):
    """Ein Feed konnte nicht gelesen werden."""


@dataclass(frozen=True)
class Source:
    """Eine Nachrichtenquelle (RSS/Atom)."""

    key: str
    name: str
    url: str
    priority: int = 1
    default: bool = False
    # Nur zur Gewichtung: Artikel aus diesem Feed werden nicht neu aufgenommen,
    # sondern heben gleiche Artikel aus den anderen Quellen nach oben
    # (z. B. die SPIEGEL-Schlagzeilen für das Thema Politik).
    boost_only: bool = False
    # Google News hängt " - Quelle" an den Titel; das wird entfernt.
    strip_source_suffix: bool = False


@dataclass
class Article:
    """Ein Artikel nach dem Zusammenführen aller Quellen."""

    title: str
    link: str
    source: str
    published: datetime | None
    summary: str = ""
    image: str | None = None
    score: int = 0
    sources: list[str] = field(default_factory=list)
    top: bool = False

    @property
    def key(self) -> str:
        """Stabiler Schlüssel (für Events und Dubletten)."""
        return hashlib.sha1(_title_key(self.title).encode()).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        """Darstellung für die Sensor-Attribute."""
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "sources": self.sources,
            "published": self.published.isoformat() if self.published else None,
            "summary": self.summary,
            "image": self.image,
            "top": self.top,
            "score": self.score,
        }


def custom_source(url: str) -> Source:
    """Quelle aus einer vom Nutzer eingetragenen Feed-URL bauen."""
    host = urlsplit(url).hostname or url
    host = host.removeprefix("www.")
    key = "custom_" + hashlib.sha1(url.encode()).hexdigest()[:10]
    return Source(key=key, name=host, url=url, priority=1)


def parse_feed(raw: bytes, source: Source) -> list[Article]:
    """RSS 2.0, RSS 1.0 (RDF) oder Atom in Artikel umwandeln."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as err:
        raise FeedError(f"{source.name}: kein gültiges XML ({err})") from err
    if _local(root.tag) not in ("rss", "feed", "RDF"):
        raise FeedError(f"{source.name}: kein RSS-/Atom-Feed")

    articles: list[Article] = []
    for entry in root.iter():
        if _local(entry.tag) not in ("item", "entry"):
            continue
        title = _clean_text(_text(entry, "title"))
        link = _entry_link(entry)
        if not title or not link:
            continue
        if source.strip_source_suffix:
            title = _strip_source_suffix(title, _text(entry, "source"))
        summary = _summary(entry)
        if _repeats_title(summary, title):
            summary = ""
        articles.append(
            Article(
                title=title,
                link=link,
                source=source.name,
                published=_entry_datetime(entry),
                summary=summary,
                image=_image(entry),
            )
        )
    return articles


def rank(
    feeds: list[tuple[Source, list[Article]]],
    window: timedelta,
    max_items: int,
    now: datetime | None = None,
) -> list[Article]:
    """Artikel im Zeitfenster zusammenführen, Dubletten mergen und gewichten.

    Gewicht = Summe der Prioritäten aller Quellen, in denen der Artikel
    auftaucht. Ein Artikel, den die Redaktion zusätzlich in ihre Top- bzw.
    Schlagzeilen-Liste aufgenommen hat, steht damit vor gewöhnlichen
    Meldungen. Bei gleichem Gewicht entscheidet die Aktualität.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - window
    merged: list[Article] = []
    index: dict[str, Article] = {}

    # Normale Quellen zuerst, reine Ranking-Quellen danach.
    ordered = sorted(feeds, key=lambda item: item[0].boost_only)
    for source, articles in ordered:
        for art in articles:
            if art.published and art.published < cutoff:
                continue
            keys = (_link_key(art.link), _title_key(art.title))
            existing = next((index[k] for k in keys if k in index), None)
            if existing is not None:
                if source.name not in existing.sources:
                    existing.sources.append(source.name)
                    existing.score += source.priority
                if source.boost_only or source.priority >= 3:
                    existing.top = True
                if not existing.image and art.image:
                    existing.image = art.image
                for k in keys:
                    index.setdefault(k, existing)
                continue
            if source.boost_only:
                continue
            new = Article(
                title=art.title,
                link=art.link,
                source=art.source,
                published=art.published,
                summary=art.summary,
                image=art.image,
                score=source.priority,
                sources=[source.name],
                top=source.priority >= 3,
            )
            merged.append(new)
            for k in keys:
                index[k] = new

    merged.sort(
        key=lambda a: (
            a.score,
            a.published.timestamp() if a.published else 0,
        ),
        reverse=True,
    )
    return merged[:max_items]


# --- Hilfsfunktionen -------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w]+", re.UNICODE)


def _local(tag: Any) -> str:
    """Tag-Name ohne XML-Namespace."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _children(entry: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in entry if _local(child.tag) == name]


def _text(entry: ET.Element, *names: str) -> str:
    for name in names:
        for child in _children(entry, name):
            value = "".join(child.itertext()).strip()
            if value:
                return value
    return ""


def _clean_text(value: str) -> str:
    value = html.unescape(_TAG_RE.sub(" ", value or ""))
    value = _TAG_RE.sub(" ", value)  # doppelt maskiertes HTML
    return _WS_RE.sub(" ", value).strip()


def _entry_link(entry: ET.Element) -> str:
    links = _children(entry, "link")
    # Atom: <link rel="alternate" href="..."/>
    for link in links:
        href = link.get("href")
        if href and link.get("rel", "alternate") == "alternate":
            return href.strip()
    for link in links:
        if link.get("href"):
            return link.get("href", "").strip()
        if link.text and link.text.strip():
            return link.text.strip()
    guid = _children(entry, "guid")
    if guid and guid[0].get("isPermaLink", "true") == "true":
        value = (guid[0].text or "").strip()
        if value.startswith("http"):
            return value
    return ""


def _summary(entry: ET.Element) -> str:
    text = _clean_text(_text(entry, "summary", "description", "encoded", "content"))
    if len(text) > SUMMARY_LENGTH:
        text = text[: SUMMARY_LENGTH - 1].rsplit(" ", 1)[0] + "…"
    return text


def _repeats_title(summary: str, title: str) -> bool:
    """Anreißer, der nur die Überschrift (ggf. plus Quellenname) wiederholt.

    Google News liefert als Beschreibung lediglich „Titel  Quelle“.
    """
    if not summary:
        return False
    s_key, t_key = _title_key(summary)[2:], _title_key(title)[2:]
    return s_key.startswith(t_key) and len(s_key) - len(t_key) <= 40


def _strip_source_suffix(title: str, source_name: str) -> str:
    source_name = source_name.strip()
    if source_name and title.endswith(f" - {source_name}"):
        return title[: -len(f" - {source_name}")].strip()
    return title


def _entry_datetime(entry: ET.Element) -> datetime | None:
    value = _text(entry, "published", "pubDate", "updated", "date", "issued")
    if not value:
        return None
    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(value)  # RFC 822 (RSS)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # ISO 8601 (Atom)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _image(entry: ET.Element) -> str | None:
    for name in ("thumbnail", "content"):
        for media in _children(entry, name):
            url = media.get("url")
            if url and (
                name == "thumbnail"
                or media.get("medium") == "image"
                or media.get("type", "").startswith("image")
            ):
                return url
    for enc in _children(entry, "enclosure"):
        if enc.get("type", "").startswith("image") and enc.get("url"):
            return enc.get("url")
    for link in _children(entry, "link"):
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("image"):
            return link.get("href")
    return None


def _link_key(link: str) -> str:
    parts = urlsplit(link.strip())
    host = (parts.hostname or "").removeprefix("www.")
    return "l:" + urlunsplit(("", host, parts.path.rstrip("/"), "", ""))


def _title_key(title: str) -> str:
    return "t:" + _NON_WORD_RE.sub(" ", title.lower()).strip()

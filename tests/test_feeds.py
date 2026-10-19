"""Tests der Feed-Logik (ohne Home Assistant lauffähig: python -m unittest)."""

from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paket laden, ohne __init__.py (Home-Assistant-Importe) auszuführen.
_PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "newsfeed"
_pkg = types.ModuleType("nf")
_pkg.__path__ = [str(_PKG_DIR)]
sys.modules.setdefault("nf", _pkg)

from nf.feeds import FeedError, Source, custom_source, parse_feed, rank  # noqa: E402
from nf.sources import TOPICS  # noqa: E402

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

HEISE_ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>heise online Top-News</title>
  <entry>
    <title type="html">Kritische L&#252;cke in OpenSSH</title>
    <link rel="alternate" type="text/html" href="https://www.heise.de/news/OpenSSH-123.html?wt_mc=rss"/>
    <published>2026-10-20T09:30:00+02:00</published>
    <updated>2026-10-20T10:00:00+02:00</updated>
    <summary type="html">&lt;p&gt;Admins sollten &lt;b&gt;sofort&lt;/b&gt; patchen.&lt;/p&gt;</summary>
    <link rel="enclosure" type="image/jpeg" href="https://heise.cloudimg.io/bild.jpg"/>
  </entry>
  <entry>
    <title>Alte Meldung</title>
    <link href="https://www.heise.de/news/alt-1.html"/>
    <updated>2026-10-01T08:00:00Z</updated>
  </entry>
</feed>"""

HEISE_SECURITY = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Kritische L\xc3\xbccke in OpenSSH</title>
    <link href="https://www.heise.de/news/OpenSSH-123.html"/>
    <updated>2026-10-20T07:31:00Z</updated>
  </entry>
  <entry>
    <title>Patchday bei SAP</title>
    <link href="https://www.heise.de/news/SAP-456.html"/>
    <updated>2026-10-20T11:00:00Z</updated>
  </entry>
</feed>"""

SPIEGEL_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>DER SPIEGEL - Politik</title>
  <item>
    <title>Bundestag beschlie\xc3\x9ft Haushalt</title>
    <link>https://www.spiegel.de/politik/deutschland/haushalt-a-1.html</link>
    <description>Nach langer Debatte &amp;ndash; Einigung.</description>
    <pubDate>Tue, 20 Oct 2026 10:15:00 +0200</pubDate>
    <enclosure type="image/jpeg" url="https://cdn.prod.www.spiegel.de/images/x.jpg"/>
  </item>
  <item>
    <title>Debatte \xc3\xbcber Rente</title>
    <link>https://www.spiegel.de/politik/rente-a-2.html</link>
    <pubDate>Tue, 20 Oct 2026 11:45:00 +0200</pubDate>
  </item>
  <item>
    <title>Kommentar von vor zwei Wochen</title>
    <link>https://www.spiegel.de/politik/alt-a-3.html</link>
    <pubDate>Sun, 04 Oct 2026 10:00:00 +0200</pubDate>
  </item>
</channel></rss>"""

SPIEGEL_SCHLAGZEILEN = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Bundestag beschlie\xc3\x9ft Haushalt</title>
    <link>https://www.spiegel.de/politik/deutschland/haushalt-a-1.html#ref=rss</link>
    <pubDate>Tue, 20 Oct 2026 10:15:00 +0200</pubDate>
  </item>
  <item>
    <title>Bayern gewinnt Topspiel</title>
    <link>https://www.spiegel.de/sport/bayern-a-9.html</link>
    <pubDate>Tue, 20 Oct 2026 11:00:00 +0200</pubDate>
  </item>
</channel></rss>"""

GOOGLE_NEWS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
  <item>
    <title>Neue Regeln f\xc3\xbcr die Dr\xc3\xbcckjagd - Wild und Hund</title>
    <link>https://news.google.com/rss/articles/CBMiABC?oc=5</link>
    <guid isPermaLink="false">CBMiABC</guid>
    <pubDate>Mon, 19 Oct 2026 16:00:00 GMT</pubDate>
    <description>&lt;a href="x"&gt;Neue Regeln&lt;/a&gt;</description>
    <source url="https://www.wildundhund.de">Wild und Hund</source>
  </item>
</channel></rss>"""

RDF = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel><title>Test</title></channel>
  <item><title>RDF-Meldung</title><link>https://example.org/a</link>
    <dc:date>2026-10-20T08:00:00Z</dc:date></item>
</rdf:RDF>"""


def src(key: str, priority: int = 1, **kw) -> Source:
    return Source(key, key, f"https://example.org/{key}", priority=priority, **kw)


class ParseTests(unittest.TestCase):
    def test_atom(self) -> None:
        items = parse_feed(HEISE_ATOM, src("heise"))
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first.title, "Kritische Lücke in OpenSSH")
        self.assertEqual(first.link, "https://www.heise.de/news/OpenSSH-123.html?wt_mc=rss")
        self.assertEqual(first.published, datetime(2026, 10, 20, 7, 30, tzinfo=timezone.utc))
        self.assertEqual(first.summary, "Admins sollten sofort patchen.")
        self.assertEqual(first.image, "https://heise.cloudimg.io/bild.jpg")

    def test_rss(self) -> None:
        items = parse_feed(SPIEGEL_RSS, src("spiegel"))
        self.assertEqual(items[0].title, "Bundestag beschließt Haushalt")
        self.assertEqual(items[0].published, datetime(2026, 10, 20, 8, 15, tzinfo=timezone.utc))
        self.assertEqual(items[0].summary, "Nach langer Debatte – Einigung.")
        self.assertEqual(items[0].image, "https://cdn.prod.www.spiegel.de/images/x.jpg")

    def test_google_news_suffix(self) -> None:
        source = src("wuh", strip_source_suffix=True)
        items = parse_feed(GOOGLE_NEWS, source)
        self.assertEqual(items[0].title, "Neue Regeln für die Drückjagd")
        self.assertTrue(items[0].link.startswith("https://news.google.com/"))

    def test_rdf(self) -> None:
        items = parse_feed(RDF, src("rdf"))
        self.assertEqual(items[0].title, "RDF-Meldung")
        self.assertEqual(items[0].published, datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc))

    def test_invalid(self) -> None:
        with self.assertRaises(FeedError):
            parse_feed(b"<html><body>Kein Feed</body></html>", src("x"))
        with self.assertRaises(FeedError):
            parse_feed(b"nicht einmal xml", src("x"))


class RankTests(unittest.TestCase):
    def test_window_dedupe_and_boost(self) -> None:
        top = src("heise_top", 3)
        sec = src("heise_security", 2)
        feeds = [
            (sec, parse_feed(HEISE_SECURITY, sec)),
            (top, parse_feed(HEISE_ATOM, top)),
        ]
        day = rank(feeds, timedelta(hours=24), 10, NOW)
        # "Alte Meldung" fällt aus dem Tagesfenster, OpenSSH ist zusammengeführt.
        self.assertEqual([a.title for a in day], ["Kritische Lücke in OpenSSH", "Patchday bei SAP"])
        self.assertEqual(day[0].score, 5)
        self.assertTrue(day[0].top)
        self.assertEqual(day[0].sources, ["heise_security", "heise_top"])
        week = rank(feeds, timedelta(days=30), 10, NOW)
        self.assertEqual(len(week), 3)

    def test_boost_only_does_not_add_articles(self) -> None:
        politik = src("spiegel_politik", 2)
        schlag = src("schlagzeilen", 3, boost_only=True)
        feeds = [
            (schlag, parse_feed(SPIEGEL_SCHLAGZEILEN, schlag)),
            (politik, parse_feed(SPIEGEL_RSS, politik)),
        ]
        day = rank(feeds, timedelta(hours=24), 10, NOW)
        titles = [a.title for a in day]
        self.assertNotIn("Bayern gewinnt Topspiel", titles)
        # Der Haushalt steht in den Schlagzeilen und rückt vor die neuere Renten-Meldung.
        self.assertEqual(titles, ["Bundestag beschließt Haushalt", "Debatte über Rente"])
        self.assertTrue(day[0].top)
        self.assertFalse(day[1].top)

    def test_max_items(self) -> None:
        s = src("s")
        self.assertEqual(len(rank([(s, parse_feed(SPIEGEL_RSS, s))], timedelta(days=30), 1, NOW)), 1)

    def test_as_dict(self) -> None:
        s = src("s")
        data = rank([(s, parse_feed(SPIEGEL_RSS, s))], timedelta(hours=24), 5, NOW)[0].as_dict()
        self.assertEqual(data["published"], "2026-10-20T09:45:00+00:00")
        self.assertEqual(set(data), {"title", "link", "source", "sources", "published", "summary", "image", "top", "score"})


class CatalogTests(unittest.TestCase):
    def test_catalog(self) -> None:
        self.assertEqual(set(TOPICS), {"it", "politik", "jagd"})
        for topic in TOPICS.values():
            keys = [s.key for s in topic.sources]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertTrue(topic.default_sources)
            for s in topic.sources:
                self.assertTrue(s.url.startswith("https://"))
        wuh = TOPICS["jagd"].source("wildundhund")
        self.assertIn("site%3Awildundhund.de+when%3A7d", wuh.url)

    def test_custom_source(self) -> None:
        s = custom_source("https://www.jagderleben.de/rss.xml")
        self.assertEqual(s.name, "jagderleben.de")
        self.assertTrue(s.key.startswith("custom_"))


if __name__ == "__main__":
    unittest.main()

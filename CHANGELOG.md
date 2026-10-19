# Changelog

## 1.1.0 – 2026-10-20

### Neu
- Thema **Metal**: METAL HAMMER, Rock Hard und metal.de als Standardquellen;
  optional Blabbermouth, Metal Injection und Metal Storm (englischsprachig).
- Google-News-Quellen können jetzt auch die englische Ausgabe nutzen.

### Behoben
- Thema Jagd zeigte kein Symbol (`mdi:deer` existiert nicht) – jetzt `mdi:pine-tree`.

### Dokumentation
- Beispiel-Dashboard mit Tile-Auswahl für Thema/Zeitraum und Markdown-Liste.
- Entity-IDs für englische und deutsche HA-Installationen im README.

**Hinweis:** Neue Themen in bestehenden Installationen über
*Geräte & Dienste → Newsfeed → Konfigurieren* aktivieren.

## 1.0.0 – 2026-10-20

- Erste Version: Themen IT (heise), Politik (SPIEGEL) und Jagd, wählbare Quellen,
  eigene Feeds, Tages-/Wochenfenster, Gewichtung nach redaktionellen Top-Listen,
  Event `newsfeed_new_article`.

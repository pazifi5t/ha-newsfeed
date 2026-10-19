# Newsfeed für Home Assistant

Kuratierte Nachrichten je Themengebiet – tages- oder wochenaktuell – direkt im Dashboard.
Du wählst Themen, pro Thema die Quellen, und die Integration liefert die wichtigsten
Meldungen als Sensor, sortiert nach redaktioneller Gewichtung und Aktualität.

## Themen und Quellen

| Thema | Standardquellen | Optional |
|---|---|---|
| **IT** | heise online Top-News, heise Security | iX, heise Developer, SPIEGEL Netzwelt |
| **Politik** | SPIEGEL Politik, SPIEGEL Schlagzeilen (nur Gewichtung) | SPIEGEL Ausland, SPIEGEL Wirtschaft |
| **Jagd** | WILD UND HUND, PIRSCH, jagderleben (JÄGER / Unsere Jagd) | Deutsche Jagdzeitung, Deutscher Jagdverband, Jagd in der Tagespresse |

Zu jedem Thema kannst du beliebige eigene RSS-/Atom-Feeds ergänzen (eine URL pro Zeile);
sie werden beim Speichern auf Gültigkeit geprüft.

**Jagd-Quellen:** Die Jagdmagazine werden über die Google-News-Suche eingebunden
(`site:wildundhund.de` usw.), weil nicht jedes Magazin einen verlässlichen eigenen Feed
anbietet. Die Links führen daher über news.google.com zum Artikel. Bietet ein Magazin
einen eigenen Feed, trage ihn als eigenen Feed ein und schalte die Google-News-Variante ab.

## Was heißt „die wichtigsten“?

RSS-Feeds liefern keine Klickzahlen. Die Rangfolge entsteht deshalb aus der Auswahl der
Redaktionen:

- Jede Quelle hat eine Priorität (3 = Top-/Schlagzeilen-Liste, 2 = Kernressort, 1 = Ergänzung).
- Erscheint ein Artikel in mehreren Quellen, addieren sich die Prioritäten. Eine Meldung, die
  heise zusätzlich in die Top-News nimmt oder die beim SPIEGEL in den Schlagzeilen steht,
  rückt nach oben und wird mit `top: true` markiert (im Beispiel-Dashboard ⭐).
- „SPIEGEL Schlagzeilen“ ist eine reine Gewichtungsquelle: Sie hebt Politik-Artikel an,
  bringt aber keine Sport- oder Panorama-Meldungen ins Thema Politik.
- Bei gleichem Gewicht entscheidet die Aktualität. Doppelte Meldungen werden zusammengeführt.

## Installation

**HACS (benutzerdefiniertes Repository):** HACS → ⋮ → Benutzerdefinierte Repositories →
`https://github.com/pazifi5t/ha-newsfeed`, Typ *Integration* → installieren → HA neu starten.

**Manuell:** Ordner `custom_components/newsfeed` nach `/config/custom_components/` kopieren
und Home Assistant neu starten.

Danach: *Einstellungen → Geräte & Dienste → Integration hinzufügen → Newsfeed*.
Themen, Quellen, Zeitraum, Artikelanzahl und Intervall lassen sich später über
*Konfigurieren* ändern. Zusätzliche Python-Pakete werden nicht benötigt.

## Entitäten

| Entität (deutsche HA-Sprache) | Zweck |
|---|---|
| `sensor.newsfeed_it`, `sensor.newsfeed_politik`, `sensor.newsfeed_jagd` | Artikel des Themas |
| `sensor.newsfeed_ausgewahlte_news` | Artikel des im Dashboard gewählten Themas |
| `select.newsfeed_thema` | Welches Thema der Auswahl-Sensor zeigt |
| `select.newsfeed_zeitraum` | Heute (24 h) oder Diese Woche (7 Tage) – gilt für alle Sensoren |

Zustand der Sensoren ist die Anzahl der Artikel. Attribute:

- `articles` – Liste mit `title`, `link`, `source`, `sources`, `published`, `summary`, `image`, `top`, `score`
- `headline`, `headline_link` – die wichtigste Meldung
- `topic`, `period`, `period_label`
- `unavailable_sources` – Quellen, die beim letzten Abruf nicht erreichbar waren
  (es werden dann die zuletzt geladenen Artikel weiterverwendet)

Die Artikellisten werden nicht in die Datenbank (Recorder) geschrieben.

## Dashboard

Ein fertiges Beispiel mit Themen-/Zeitraum-Umschalter und Markdown-Liste liegt in
[`examples/dashboard.yaml`](examples/dashboard.yaml).

## Benachrichtigung bei neuen Artikeln

Für jeden neuen Tagesartikel feuert die Integration das Event `newsfeed_new_article`
(höchstens 5 pro Thema und Abruf, nicht beim Start):

```yaml
automation:
  - alias: "Newsfeed: Top-Meldung IT aufs Handy"
    triggers:
      - trigger: event
        event_type: newsfeed_new_article
        event_data:
          topic: it
          top: true
    actions:
      - action: notify.mobile_app_mein_handy
        data:
          title: "{{ trigger.event.data.source }}"
          message: "{{ trigger.event.data.title }}"
          data:
            url: "{{ trigger.event.data.link }}"
```

## Entwicklung

```bash
python -m unittest discover tests
```

Die Feed-Logik (`feeds.py`) ist von Home Assistant unabhängig und kommt ohne Fremdpakete aus.

## Lizenz

MIT © pazifi5t. Die Inhalte der Feeds gehören den jeweiligen Verlagen; die Integration zeigt
nur Überschrift, Anreißer und Link wie jeder Feedreader.

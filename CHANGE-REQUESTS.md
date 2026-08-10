# Offene Änderungswünsche — Homepage

Aus der Änderungsliste der Gründerin (Screenshots, erfasst 2026-08-10).
Noch **nicht** umgesetzt. Reihenfolge = Reihenfolge der Liste.

---

## 1 · 06AUG2026 · Leistungen — „The Grove" umbenennen

| Sprache | neu |
|---|---|
| Deutsch | **Verbindung** |
| English | **Connection** |
| Español | **Conexión** |

*Grund:* Anpassung an die bereits geänderten Sessionnamen (Klarheit · Wandel ·
Balance).

⚠️ Der interne Schlüssel bleibt `grove` / `corp` — nur die sichtbaren Labels
ändern. Betrifft `index.html` (EN im Markup, `I18N.de`, `I18N.es`) und die
Erwähnungen in `portal/`, `ios-app/` und `llms.txt`, falls „The Grove" dort
sichtbar vorkommt.

---

## 2 · 10AUG2026 · Frauengesundheit — Abschnitt einfügen

Direkt **nach** dem Satz:

> „… Es geht nicht darum, immer gleich zu funktionieren. Es geht darum, den
> eigenen Körper besser zu verstehen und Ernährung, Gewohnheiten, Erholung und
> Rhythmus so zu gestalten, dass sie zur aktuellen Lebensphase passen."

einfügen:

> Gerade in Phasen wie Kinderwunsch, Schwangerschaft, Stillzeit, Wochenbett und
> Perimenopause verändern sich die Bedürfnisse des Körpers oft deutlich.
> Ernährung, Erholung und alltagstaugliche Gewohnheiten verdienen in diesen
> Zeiten besondere Aufmerksamkeit.
>
> Ein besonderer Schwerpunkt meiner Arbeit liegt auf Ernährung und Lebensstil in
> hormonell geprägten Lebensphasen – von Kinderwunsch und Schwangerschaft über
> Stillzeit und Wochenbett bis hin zur Perimenopause.

*Grund:* Die Beratungstätigkeit für Ernährung und Lifestyle in Schwangerschaft
und Stillzeit stärker positionieren.

⚠️ Deutsch ist die Master-Sprache — EN und ES werden aus diesem Text abgeleitet,
nicht unabhängig geschrieben.

---

## 3 · 10AUG2026 · Frauengesundheit — Themenliste ergänzen

| alt | neu |
|---|---|
| Kinderwunsch, Schwangerschaft und Wochenbett | **Kinderwunsch, Schwangerschaft, Stillzeit und Wochenbett** |

*Grund:* Vervollständigung, Anpassung an den neuen Text.

---

## 4 · 10AUG2026 · Frauengesundheit — Schriftgröße im Fließtext vereinheitlichen

*Grund:* Harmonisierung, Gewichtung korrigieren.

Der Abschnitt verwendet derzeit mehrere Fließtextgrößen nebeneinander. Alle auf
eine Größe bringen, damit kein Absatz optisch schwerer wirkt als ein anderer.

---

## 5 · 10AUG2026 · Frauengesundheit — „Stillzeit" ins Blumenbild aufnehmen

*Grund:* Vervollständigung, Anpassung an den neuen Text.

Die Grafik der Lebensphasen („Blumenbild") nennt Stillzeit bisher nicht. Muss
zur Themenliste aus Punkt 3 passen.

---

## 6 · 10AUG2026 · Frauengesundheit — Foto einfügen

Ober- oder unterhalb des Blumenbildes ein Foto von Desiree **während der
Schwangerschaft** einfügen.

*Grund:* Um den Abschnitt persönlicher zu machen.

---

## 7 · 10AUG2026 · Die Gründerin — Foto entfernen

*Grund:* „Foto mit Babybauch passt nicht."

⚠️ **Punkt 6 und 7 gehören zusammen:** `images/desiree-womens-health.jpg` zeigt
sie sichtbar schwanger und steht heute im Abschnitt *Die Gründerin*
(eingefügt 2026-08-05). Beide Wünsche zusammen heißen: **dieses Foto von
„Die Gründerin" nach „Frauengesundheit" verschieben**, ans Blumenbild.

Damit fällt auch die alte Warnung in CLAUDE.md weg, die Notiz „Desiree ist keine
Mutter" stamme aus der Zeit vor diesem Foto — nach der Verschiebung steht das
Foto genau dort, wo es inhaltlich hingehört.

---

## Reihenfolge der Umsetzung

1. Punkt 7 + 6 zusammen (Foto verschieben) — eine Änderung, nicht zwei.
2. Punkt 2 (neuer Text) — Deutsch zuerst, dann EN/ES ableiten.
3. Punkt 3 + 5 (Stillzeit in Liste und Grafik) — müssen zueinander passen.
4. Punkt 1 (Umbenennung) — betrifft mehrere Dateien, eigener Durchgang.
5. Punkt 4 (Schriftgrößen) — zuletzt, wenn der Text final ist.

## Prüfen vor dem Ausliefern

- DE/ES-Schlüsselparität unverändert, keine JS-Fehler.
- Jede Überschrift bei 360 px — die Visitenkarte verlangt `hyphens: none`,
  also keine Worttrennung, sondern kleinere Schrift bei langen Komposita.
- In allen drei Sprachen rendern.

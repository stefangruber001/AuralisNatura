# Auralis Natura — End-to-End-Simulation · 2026-08-10 10:13

Personas: **Sofia Ejemplo** (Kundin, Spanisch-Muttersprachlerin, bucht auf
Deutsch, wechselt im Portal zu Spanisch) und **Desiree** (Betriebskonsole).
Die Simulation läuft gegen die ECHTE Anwendung und lässt alle Daten stehen.

## Station 1 — Elena bucht das kostenlose Kennenlerngespräch (/book)
  ✅ Slots werden öffentlich angeboten
  ✅ Buchung angenommen (200, ok:true)
    Buchung `f6489cc032d5` für `2026-08-11T13:10:00+00:00`.
  ✅ WRITE bookings-DB: Buchung persistiert, Status confirmed
  ✅ WRITE .ics auf Platte (Audit)
  ✅ Einladung: METHOD:REQUEST + beide Teilnehmer + eine UID
  ✅ MAIL 1 Sofort-Bestätigung an Sofia (gesendet, nicht Entwurf)
  ✅   … auf Deutsch (Buchungssprache)
  ✅   … mit Date + Message-ID
  ✅ MAIL 2 Termin-Bestätigung mit Einladung (Entwurf-Pfad, .eml)
  ✅   … trägt die Kalender-Einladung
  ✅ MAIL 3 internes Briefing an team@ (gesendet)
  ✅   … trägt DIESELBE Einladung (Kalender-Eintrag ab Buchung)
  ✅   Logo (Lockup, cid) in ack
  ✅   Logo (Lockup, cid) in confirm
  ✅   Logo (Lockup, cid) in briefing
  ✅ WRITE clients.json: Lead automatisch angelegt
  ✅ Login-ID aus dem Namen abgeleitet
  ✅ WRITE Store (verschlüsselt): Vorab-Angaben am Datensatz
  ✅ Stage = lead (Funnel-Anfang)

## Station 2 — Desiree: Erstgespräch geführt, gewonnen, Zugang gesendet
  ✅ Stage → won
  ✅ Paket Wandel (bloom, 399 €) gesetzt
  ✅ Zugangsdaten erzeugt
  ✅ Antwort nennt die Login-ID (nicht die AN-Nummer)
  ✅ MAIL 4 Zugangsdaten-Karte (.eml)
  ✅   … enthält den Ein-Klick-Link (Fragebogen öffnen)
  ✅   … und die Fragebogen-Botschaft (speichert automatisch / gemeinsam im Gespräch)
  ✅ Store: Stage → invited

## Station 3 — Elena: Ein-Klick ins Portal, Fragebogen, Passwort, Programme
  ✅ Magic-Link: ohne ID/Passwort direkt im Fragebogen
  ✅ Schlüssel aus der Adresszeile entfernt
  ✅ Sprachwechsel im Portal → Spanisch
  ✅ Fragebogen abgesendet → Übersicht
  ✅ Keine JavaScript-Fehler
  ✅ WRITE Store: Intake verschlüsselt persistiert
  ✅ Intake trägt die PORTAL-Sprache (es)
  ✅ Red-Flag-Werte kanonisch (None of the above)
  ✅ Stage → intake→prep (Gesprächsvorbereitung wird direkt mitberechnet)
  ✅ READ Übersicht: Selbsteinschätzung sichtbar
  ✅ Passwort selbst geändert (Zugang-Tab)
  ✅ Programme-Tab: lokalisierte Namen (Claridad/Cambio/Equilibrio)
  ✅ Ihr Programm (Cambio) ist markiert
  ✅ Stripe-Links eingebunden
  ✅ Altes Passwort abgelehnt
  ✅ Neues Passwort + Namens-Login (case-insensitiv) funktioniert

## Station 4 — Desiree: Notizen, KI-Entwurf, Freigabe, PDF, Bericht-Mail
  ✅ WRITE Notizen (strukturiert) + Stage call
  ✅ Kundinnen-Sprache in der Konsole: es
  ✅ KI-Entwurf erstellt
  ✅ Bericht in Kundinnen-Sprache (es)
  ✅ Kein Red-Flag (keine angekreuzt)
  ✅ Bericht redigiert + FREIGEGEBEN (Gate)
  ✅ PDF gerendert + Bericht-Mail erstellt
  ✅ WRITE report.pdf auf Platte
  ✅ MAIL 5 Bericht-Mail, spanischer Betreff
  ✅   … PDF hängt an
  ✅   … Logo (Lockup, cid)
  ✅ Stage → sent

## Station 5 — Abschluss: bezahlt, Feedback-Anfrage (Flywheel)
  ✅ Bezahlt markiert (Umsatz zählt ins Cockpit)
  ✅ Stage → done
  ✅ MAIL 6 Feedback-Anfrage, spanisch

## Abschlussbild — Elenas Portal nach Berichtsversand
  ✅ Journey: vier Stationen ✓, Programm läuft
  ✅ Prioritäten aus dem Bericht sichtbar
  ✅ Bericht-Tab: Download angeboten

## Daten-Bestand (bewusst NICHT gelöscht)
- clients.json → `AN-0002` Sofia Ejemplo · login `sofia.ejemplo` · es · bezahlt
- Verschlüsselter Datensatz (auralis.db) → Vorab-Angaben, Intake, Notizen, freigegebener Bericht
- `output_docs/bookings/` → f6489cc032d5.ics + Bestätigung/Ack/Briefing (.eml)
- `output_docs/AN-0002/sent/` → Zugangsdaten-, Bericht-, Feedback-Mail (.eml)
- `output_docs/AN-0002/report/report.pdf` → das 12-Seiten-Dokument
- `portal/simulation/sofia-final-home.png` → Sofias Portal am Ende

**Ergebnis: 61/61 Prüfungen bestanden.**
Laufzeit 45s · Provider: stub (Konsole nutzt in Produktion die Claude CLI).

# Warum die Einladung im Spam landet — und die drei DNS-Einträge, die es lösen

**Stand 2026-08-10.** Eine Buchungsbestätigung, aus Gmail an eine `yahoo.de`-Adresse
weitergeleitet, ist direkt im Spam gelandet. Das lag nicht am Text und nicht am Design.

## Der Befund

`python3 portal/deploy/check_email_dns.py` sagt heute:

```
  SPF    MISSING
  DKIM   MISSING
  DMARC  MISSING
```

Die Domain `auralisnatura.com` liegt auf Google Workspace (MX: `smtp.google.com`),
aber sie sagt der Welt **nirgends**, dass Google für sie Mails verschicken darf, und
sie **signiert** ihre Mails nicht. Für Yahoo sieht eine Mail von
`team@auralisnatura.com` damit exakt so aus wie eine gefälschte. Seit Februar 2024
verlangen Yahoo **und** Gmail Authentifizierung; ohne sie ist der Spam-Ordner die
vorgesehene Behandlung, nicht ein Fehler.

Dazu kommt: **Weiterleiten zerstört die Authentifizierung zusätzlich.** Beim
Forward ändert Gmail Betreff und Struktur, die (hier ohnehin fehlende) DKIM-Signatur
bricht, und der sendende Server ist plötzlich nicht mehr der, den die Domain erlaubt.

## Die Lösung — drei Einträge, einmalig

DNS liegt bei **Cloudflare** (die Domain löst auf Cloudflare-IPs auf).
Dashboard → `auralisnatura.com` → **DNS** → **Add record**. Alle drei sind Typ **TXT**.
Bei Cloudflare bei allen dreien **Proxy off / DNS only** (TXT wird ohnehin nie geproxied).

### 1. SPF — „Google darf für mich senden"

| Feld | Wert |
|---|---|
| Type | `TXT` |
| Name | `@` |
| Content | `v=spf1 include:_spf.google.com ~all` |

⚠️ Es darf **genau einen** SPF-Eintrag geben. Falls später ein Newsletter-Dienst
dazukommt, wird dessen `include:` in **dieselbe** Zeile ergänzt — kein zweiter Eintrag.

### 2. DKIM — die Signatur

Das ist der einzige Schritt, der nicht in Cloudflare beginnt:

1. [admin.google.com](https://admin.google.com) → **Apps** → **Google Workspace** →
   **Gmail** → **Authenticate email** (DE: „E-Mail authentifizieren").
2. Domain `auralisnatura.com` wählen → **Generate new record** →
   **2048 bit**, Präfix/Selector **`google`** → **Generate**.
3. Google zeigt einen langen Wert (`v=DKIM1; k=rsa; p=MIIBIj…`). Diesen in Cloudflare
   eintragen:

| Feld | Wert |
|---|---|
| Type | `TXT` |
| Name | `google._domainkey` |
| Content | der von Google angezeigte Wert, vollständig |

4. Zurück in Google Admin: **Start authentication**. (Google prüft den Eintrag; das
   kann bis zu 48 h dauern, ist meist in Minuten erledigt.)

### 3. DMARC — die Regel

| Feld | Wert |
|---|---|
| Type | `TXT` |
| Name | `_dmarc` |
| Content | `v=DMARC1; p=none; rua=mailto:team@auralisnatura.com` |

`p=none` heißt: nur beobachten, nichts blockieren — der richtige Start. Wenn nach
ein paar Wochen die Reports sauber sind, kann daraus `p=quarantine` werden.

## Danach prüfen

```bash
python3 portal/deploy/check_email_dns.py
```

Muss alle drei als `ok` melden. Dann eine echte Testmail an eine `yahoo.de`- und eine
`gmail.com`-Adresse schicken, dort **„Original anzeigen"** öffnen und oben nachsehen:

```
spf=pass   dkim=pass   dmarc=pass
```

## Was am Ablauf ebenfalls hilft

- **Senden statt weiterleiten.** Der Entwurf im Postfach ist bereits korrekt an die
  Kundin adressiert — einfach **Senden** drücken. Ein Forward derselben Mail kommt bei
  Yahoo schlechter an als das Original, auch nach den DNS-Einträgen.
- **Der Termin-Link steht jetzt im Mailtext**, mit „In den Kalender eintragen"-Buttons
  für Google und Outlook. Die `.ics`-Datei hängt nur noch als Reserve dran. Mails, die
  fast nur aus einem Anhang bestehen, sind ein klassisches Spam-Muster — Text plus
  echte Links sind besser.
- **Kein Linkkürzer**, keine Tracking-Pixel, keine reinen Bild-Mails. Alle Auralis-Mails
  haben eine echte Text-Version neben dem HTML; das ist ein positives Signal und bleibt so.
- Wenn eine Kundin schreibt, die Mail sei im Spam gelandet: sie soll einmal
  **„Kein Spam"** klicken und `team@auralisnatura.com` zu den Kontakten hinzufügen.
  Das wirkt sofort und nur für sie — die drei DNS-Einträge wirken für alle.

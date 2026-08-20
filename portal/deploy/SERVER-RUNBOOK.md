# Auralis Natura — Server-Runbook

**Der Umzug vom MacBook auf den Hetzner-Server, und das Leben danach.**

Dieses Dokument hat zwei Teile:

| Teil | Für wen | Länge |
|---|---|---|
| **Teil 1 — Für Desiree** | die Gründerin | 2 Minuten, deutsch |
| **Teil 2–9 — For the admin** | whoever owns the box | the rest, English |

Der Server ist `178.105.10.156` (4 vCPU · 8 GB · 80 GB). **Auf derselben Maschine läuft
die Produktion einer anderen Firma („canei-erp").** Alles hier ist so gebaut, dass sich die
beiden niemals in die Quere kommen — siehe §7.

---

# Teil 1 — Für Desiree

## Was sich ändert

**Der Mac kann aus.** Zugeklappt, ausgeschaltet, im Schrank. Er wird für den laufenden
Betrieb nicht mehr gebraucht. Portal, Betriebskonsole, Buchung, Berichte und der
Cloudflare-Tunnel laufen jetzt rund um die Uhr auf einem Server, der nie schläft und sich
nach einem Stromausfall selbst wieder startet.

## Was sich **nicht** ändert

| | |
|---|---|
| **Die Adresse** | `https://api.auralisnatura.com` — identisch. Konsole weiterhin `/staff`, Klientinnen-Portal `/portal`, Buchung `/book`. |
| **Dein Login** | derselbe Staff-Key wie bisher, dieselbe Cloudflare-Access-Abfrage davor. |
| **Deine Arbeit** | Journey-Tabs, Freigabe-Gate, Sprache pro Kundin, E-Mail-Modus `draft` (Mails landen wie gewohnt als Gmail-Entwurf) — Station für Station unverändert. |
| **Deine Daten** | Kundinnen, Berichte, PDFs, Finanzen: alles ist mitgezogen und vollständig. |
| **Die „Office"-App** | funktioniert weiter, gleiche URL, gleiches Login. |

Es gibt **nichts Neues zu lernen.** Der Umzug ist unter der Motorhaube.

## Wenn etwas komisch aussieht

1. **Prüfen (10 Sekunden):** öffne <https://api.auralisnatura.com/health> im Browser.
   - Da steht `{"ok": true, ...}` → der Server läuft. Das Problem ist woanders (dein WLAN,
     eine einzelne Seite). Lade die Seite neu.
   - Da steht **„Error 1033"** oder gar nichts → der Server ist nicht erreichbar.
2. **Anrufen:** eine Person, der Admin — ☎ `________________` *(hier eintragen)*.
   Er sieht in zwei Minuten, was los ist.
3. **Nur wenn es dringend ist und er nicht erreichbar ist:** Mac aufklappen, Terminal
   öffnen, diese **eine Zeile** eingeben:

   ```bash
   cd ~/AuralisNatura && bash portal/deploy/rollback_to_mac.sh
   ```

   Das holt die Seite in etwa einer Minute zurück auf den Mac — genau wie früher. Der Mac
   muss dafür an bleiben. Nichts geht dabei kaputt; sag dem Admin danach Bescheid.

## Zwei Dinge, die du melden solltest

- **Ein Berichtsentwurf liest sich plötzlich generisch / nach Baukasten.** Dann arbeitet
  der Report-Agent im Notmodus („stub"). Der Text ist dann *nicht* der KI-Entwurf.
  **Nicht freigeben** — Admin anrufen.
- **Statt des 12-seitigen PDF kommt eine `.html`-Datei.** Auch das ist ein Notmodus.
  Nicht verschicken — Admin anrufen.

Beides fängt der Server normalerweise vorher ab. Aber falls doch: du bist die letzte
Kontrolle vor der Kundin, und das ist Absicht.

---
---

# Teil 2 — Migration: the exact steps

Everything below is English and assumes an admin who can read a systemd unit.

## 2.0 Before you start

Run these on **the Mac**, in the repo. All must be true:

- [ ] `portal/.env` exists and is the **live** one — in particular the real `AURALIS_DATA_KEY`.
- [ ] The portal currently works on the Mac (open `https://api.auralisnatura.com/staff`).
- [ ] `main` is pushed. The server tracks `origin/main`; anything unpushed will not exist there.
- [ ] SSH to the box works: `ssh root@178.105.10.156 true`.
- [ ] `~/.cloudflared/auralis.yml` is the **Auralis** tunnel, not Paramur's. (Running the wrong
      tunnel is exactly how Error 1033 happened before. The script asserts this; don't guess.)
- [ ] Claude Code is installed on the Mac and logged in (`claude --version`).
- [ ] You can add a **read-only Deploy Key** to `stefangruber001/AuralisNatura` on GitHub.

## 2.1 The three commands

There are three. Nothing else is typed by hand.

---

### Step 1 — Preflight. Nothing remote is touched.

```bash
cd ~/AuralisNatura
bash portal/deploy/migrate_to_server.sh --preflight-only
```

**Why this step exists.** It proves, on the Mac, the one invariant that has actually broken
this project: that the `AURALIS_DATA_KEY` in `portal/.env` really opens `portal/auralis.db`.
In July 2026 the staff console started 500-ing because a record had been encrypted with a
throwaway `.dev_data.key` while the server ran with the env key. Migrating with a mismatched
key would carry that fault to the server and make it permanent. `portal/lib/store.py`
exposes `key_matches_store() -> True | False | None` for precisely this, and the script
refuses to continue on `False`.

**What it looks like when it worked:**

```
   ✓ tools/preflight.py: all checks green
   ✓ AURALIS_DATA_KEY opens the live store (7 records)
   ...
✓ preflight only — everything local is green, nothing remote was touched.
```

**If it fails:** stop. Do not "try the next step anyway". A `MISMATCH` means restore the
correct key or the matching backup (`python3 portal/tools/restore.py --list`) — and **never
overwrite the store** to make the error go away.

---

### Step 2 — Install on the server. The Mac keeps serving the whole time.

```bash
bash portal/deploy/migrate_to_server.sh
```

**Why this is separate from the cutover.** The installer is invoked with
`AURALIS_SKIP_TUNNEL=1`, so the server gets code, data, venv, Chromium, systemd units and
a health-checked Flask process — but **no cloudflared**. There is therefore never a moment
when both the Mac and the server are connectors for the same tunnel id. If there were,
Cloudflare would load-balance between them and roughly half of all requests would hit the
*other* machine's database: a silent split brain that nobody notices until two clients'
data disagree.

**The script may stop and ask you for exactly two things:**

| It stops with | Why | What you do |
|---|---|---|
| `exit 30` + a printed `ssh-ed25519 …` key | The server needs read access to the private repo, and it generated its own key rather than reusing yours. | Paste it into GitHub → repo → Settings → Deploy keys → **Add**, *read-only*. Then re-run the same command unchanged. |
| `running 'claude setup-token' — a browser window will open` | `claude setup-token` is a documented CLI subcommand ("Set up a long-lived authentication token (requires Claude subscription)") and it is **interactive** — it cannot run on a headless server. So it runs here, on the Mac, and only the resulting token travels. | Finish the login in the browser. Offer to remember it in `~/.auralis/claude_oauth_token` (mode 0600) so re-runs never ask again. |

**What it looks like when it worked:**

```
   ✓ verify_server.sh: PASS
   ================ AURALIS INSTALL SUMMARY ================
     code      /opt/auralis/app @ main (97a437c)
     data      /var/lib/auralis (db 184320B · output_docs 12 files)
     chromium  /usr/bin/chromium (PDF verified)
     listen    http://127.0.0.1:5056   (loopback only)
     services  active auralis-portal · active update.timer · active backup.timer
     tunnel    NOT installed — the Mac still serves api.auralisnatura.com
```

That last line is **correct and intended** at this stage. The live site is still the Mac.

You can re-run step 2 as often as you like. Every stage is idempotent: units are compared
byte-for-byte before being rewritten, the repo is fast-forwarded rather than re-cloned, and
data files are checksum-compared (identical → no-op; different → refuse, unless
`--import-data`).

---

### Step 3 — Cutover. The point of no return.

```bash
bash portal/deploy/migrate_to_server.sh --cutover
```

**Why it needs a typed word.** This is the only step that changes what the public sees. It
re-ships a **fresh** snapshot (the Mac kept taking bookings during step 2), stops the Mac's
launchd agent `com.auralis.portal`, then starts `cloudflared-auralis.service` on the server.
Order matters: the Mac's connector must be gone *before* the server's appears.

No DNS change is involved — the server runs the **same tunnel id**, so the existing
`api.auralisnatura.com` CNAME already points at it.

```
   Type CUTOVER to switch the live site to the server: CUTOVER
```

**What it looks like when it worked:**

```
   ✓ https://api.auralisnatura.com answers 200 from the public internet

✓ Live on the server. The Mac can be switched off.
```

The script then prints the four checks to do yourself, in this order. Do them:

1. `https://api.auralisnatura.com/book` — the booking wizard loads.
2. `https://api.auralisnatura.com/staff` — your key works and the client list is **complete**
   (count the rows against what the Mac showed).
3. Pick one client → draft a report → the console log line must say provider **`claude_cli`**,
   never `stub` and never `stub (claude_cli failed: …)`.
4. Generate a PDF → it must be the 12-page PDF, **not** an `.html` fallback.

Only after all four are green should the Mac actually be switched off.

## 2.2 The `claude` CLI, and what happens without it

`install_server.sh` installs python, git, curl, fonts, a **non-snap** Chromium — and, in
stage 6, the **`claude` CLI**, using Anthropic's native installer run **as the `auralis`
user**. It lands in `/opt/auralis/.local/bin/claude`, which is already on the service
unit's `PATH`. Nothing goes into `/usr/local`, no apt source is added and no global node
toolchain is installed, so the co-tenant's host is untouched by it.

This used to be a manual step, and skipping it was invisible: `portal/lib/agent.py` gates
on `shutil.which("claude")`, and with no binary the provider silently falls back to `stub`
— a deterministic offline template, not a real draft. A shipped token with no binary to
use it is still a stub.

If the install fails (no egress, installer changed), the run **warns** and
`verify_server.sh` then **fails** on `preflight/agent`. Two ways forward:

- fix it: install by hand as the service user, then re-run —
  `runuser -u auralis -- bash -c 'curl -fsSL https://claude.ai/install.sh | bash'`
- accept it for now: re-run with `AURALIS_ALLOW_STUB=1` (or `MIGRATE.command --allow-stub`).
  That downgrades **only** `preflight/agent` to a warning, tagged
  `[--allow-stub: accepted, NOT fixed]`; everything else still has to pass. Never leave it
  set — stub drafts are boiler-plate and must not reach a client.

`AURALIS_SKIP_CLAUDE_CLI=1` skips the install step itself; only useful when the binary is
already there by another route.

See §5.4 for the symptom and §4.8 for the runtime probe that tells you whether the token
env var is actually being honoured.

## 2.3 Email mode is derived, not assumed

`mailer._imap_draft()` / `_smtp_send()` return the string
`"skipped — no AURALIS_SMTP_PASSWORD set"` and neither raises nor logs. So
`AURALIS_EMAIL_MODE=draft` **without** a password is the worst state available: it looks
configured and produces no client mail at all — no access details, no reminders, no
reports, no feedback requests.

The migrator and the installer therefore pick the mode from reality: `draft` when an
`AURALIS_SMTP_PASSWORD` is present, `off` when it is not, and both say so out loud.
`--email-mode` / `AURALIS_EMAIL_MODE` still pin it explicitly (you get a warning if you pin
`draft` with no password).

### Turning mail on — one command

Don't edit `portal.env` by hand. On the server, as root:

```bash
bash /opt/auralis/app/portal/deploy/enable_email.sh
```

It asks for the App Password (hidden), **proves it against the real Gmail servers
before changing anything**, then writes it, switches to `draft` and restarts. On a bad
credential nothing is touched. It backs the old env file up first and rolls back if the
service won't start with the new one.

Getting the App Password (the only part nobody can do for you): **myaccount.google.com**
as `team@auralisnatura.com` → **Security** → 2-Step Verification must be **on** → search
the page for **App passwords** → create one named "Auralis" → copy the 16 letters. The
spaces Google displays are cosmetic; the script strips them either way.

### Closing the purchase loop — one command

Stripe needs exactly one secret here, and it is **not an API key**: this system holds no
`sk_` and never will. Verifying a webhook needs only the endpoint's **signing secret**
(`whsec_…`), which cannot move money or read a customer.

```bash
bash /opt/auralis/app/portal/deploy/enable_stripe.sh          # ask, write, restart, prove
bash /opt/auralis/app/portal/deploy/enable_stripe.sh --check  # what is configured now
```

It proves the result instead of assuming it: after the restart it posts a deliberately
mis-signed event and requires a **400** ("bad signature"). While the secret is missing the
same request answers **503** ("not configured") — and 503 is the dangerous state, because
a real payment would be taken by Stripe and the portal would never hear about it.

Getting the secret (the part nobody can do for you): **dashboard.stripe.com** →
**Developers** → **Webhooks** → *Add endpoint* → URL
`https://api.auralisnatura.com/api/stripe/webhook`, event **`checkout.session.completed`**
→ create → reveal **Signing secret**.

⚠️ **Live mode and test mode have different secrets.** The payment links being sold are
live-mode links, so create the endpoint with the dashboard toggle on **Live**; a test-mode
secret rejects every real event and looks exactly like nothing happening.

`--shop-on` additionally sets `shop_enabled=true`, which is what puts buy buttons in front
of real customers. Only once the distance-selling terms are settled.

Useful afterwards:

| | |
|---|---|
| `enable_email.sh --retest` | re-test the stored password, change nothing (App Passwords die when the account's 2SV is reset) |
| `enable_email.sh --send-test-to you@example.com` | put one real message through the whole path |
| `enable_email.sh --mode off` | turn it off again |

### The drafts folder is discovered, never assumed

`mailer.drafts_mailbox()` finds the folder by its RFC 6154 `\Drafts` flag rather than by
name. Gmail localises system folders — a German-language account calls it
`[Gmail]/Entwürfe`, a Spanish one `[Gmail]/Borradores` — and `_imap_draft()` catches every
exception and returns a string in a dict that nothing reads, so appending to a hardcoded
`[Gmail]/Drafts` on such an account loses the report mail with no traceback and no log
line. `preflight.py --net` resolves the folder through the same function, so the check
cannot pass where the code path would fail. Regression test: `portal/tests/test_email.py`.

---

# Teil 3 — Architecture after the move

## 3.1 What runs where

```
   Klientin / Desiree
          │  https://api.auralisnatura.com
          ▼
   Cloudflare edge  ── Access policy still guards /staff ──┐
          │                                                │
          │  tunnel <AURALIS_TUNNEL_ID>                    │
          ▼                                                │
 ┌──────────────────── Hetzner 178.105.10.156 ─────────────┼───────────┐
 │                                                          │           │
 │  cloudflared-auralis.service  ── our OWN cloudflared instance        │
 │        │ http://127.0.0.1:5056                                       │
 │        ▼                                                             │
 │  auralis-portal.service   Flask, user `auralis`, loopback only       │
 │        │                                                             │
 │        ├─ reads /etc/auralis/portal.env      (secrets, 0640)         │
 │        ├─ code  /opt/auralis/app/portal      (git, branch main)      │
 │        ├─ venv  /opt/auralis/venv            (flask, cryptography)   │
 │        ├─ data  /var/lib/auralis/…           (via symlinks)          │
 │        ├─ PDFs  chromium --headless --print-to-pdf                   │
 │        └─ AI    `claude -p … --output-format text`                   │
 │                                                                      │
 │  auralis-update.timer  → every 2 min: git fetch, deploy if moved     │
 │  auralis-backup.timer  → 03:20 daily: tar.gz → /var/backups/auralis  │
 │                                                                      │
 │  ── everything else on this box is canei-erp and is NOT ours ──      │
 └──────────────────────────────────────────────────────────────────────┘
```

Nothing listens on a public interface. `config/config.json` sets `"host": "127.0.0.1"` and
the unit does not override it. The only way in from the internet is the tunnel.

## 3.2 The systemd units

All are prefixed so they can never collide with a canei-erp unit.

| Unit | Type | What it does | Replaces on the Mac |
|---|---|---|---|
| `auralis-portal.service` | simple, `Restart=always`, `RestartSec=3` | Runs `/opt/auralis/venv/bin/python /opt/auralis/app/portal/run.py` as `auralis`. `After=network-online.target`. Hardened: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome`, `ReadWritePaths=/var/lib/auralis /var/backups/auralis /opt/auralis`. | launchd `KeepAlive` |
| `auralis-update.service` | oneshot | Runs `/etc/auralis/update.sh`: `git fetch`; if `HEAD != origin/main` → `git reset --hard`, `pip install -r requirements.txt`, re-assert the three data symlinks, `systemctl restart auralis-portal`. A failed fetch logs and exits 0 — a network blip must never take the app down. | the 120 s loop in `start_auralis.command` |
| `auralis-update.timer` | timer | `OnBootSec=2min`, `OnUnitActiveSec=2min`, `AccuracySec=30s`. | — |
| `auralis-backup.service` | oneshot, user `auralis` | Runs `/etc/auralis/backup.sh`: SQLite **online-backup API** snapshot (WAL-safe) + `clients.json` + `output_docs` → `/var/backups/auralis/auralis-<ts>.tar.gz`; keeps the newest 14. | nothing — this is new |
| `auralis-backup.timer` | timer | `OnCalendar=*-*-* 03:20:00`, `RandomizedDelaySec=20min`, `Persistent=true` (so a missed run catches up after downtime). | — |
| `cloudflared-auralis.service` | simple, `Restart=always`, `RestartSec=5` | `cloudflared --no-autoupdate --config /etc/cloudflared/auralis.yml tunnel run`. Deliberately **not** named `cloudflared.service`. `--no-autoupdate` is mandatory: an autoupdate would replace the shared `/usr/bin/cloudflared` under the *other* company's tunnel too. | the tunnel supervisor in `start_auralis.command` |

The in-process hourly backup thread (`portal/lib/backup.py`, `backup.start_scheduler()`)
still runs as well, writing to `AURALIS_BACKUP_DIR=/var/lib/auralis/backups`
(`backup_interval_hours: 1`, `backup_keep: 48`). So there are **two** backup layers: 48
hourly snapshots inside the data dir, and 14 daily tarballs outside it.

## 3.3 Data layout, and why it is outside the git worktree

```
/var/lib/auralis/
├── auralis.db          the encrypted backbone (Fernet blobs + clear metadata)
├── clients.json        portal logins, e-mail, language, consent — NO health data
├── output_docs/        rendered report PDFs + .eml audit copies + booking .ics
└── backups/            48 rolling hourly snapshots (in-app scheduler)

/var/backups/auralis/   14 daily tar.gz (systemd timer)
/etc/auralis/portal.env the complete environment, 0640 root:auralis
/etc/auralis/update.sh  0750 root:auralis   ← root runs it; auralis can't rewrite it
/etc/auralis/backup.sh  0750 root:auralis
/opt/auralis/app        the git clone
/opt/auralis/venv       the virtualenv
/opt/auralis/.ssh/id_ed25519   deploy key, 0600 auralis:auralis
/etc/cloudflared/auralis.yml               ingress config
/etc/cloudflared/auralis-<TUNNELID>.json   tunnel credentials, 0640 root:auralis
```

Three symlinks reach into the worktree so the app finds its data transparently
(`portal/lib/cfg.py` computes `ROOT = Path(__file__).parent.parent`, i.e. the portal dir):

```
/opt/auralis/app/portal/auralis.db          -> /var/lib/auralis/auralis.db
/opt/auralis/app/portal/config/clients.json -> /var/lib/auralis/clients.json
/opt/auralis/app/portal/output_docs         -> /var/lib/auralis/output_docs
```

**Why not just keep the data in the repo?** Because `auralis-update.service` runs
`git reset --hard origin/main` every two minutes. Anything tracked would be reverted;
anything untracked-but-in-the-way would eventually collide. All three paths are listed in
`portal/.gitignore`, so the symlinks are invisible to git and survive the reset. Note the
gitignore entry is `output_docs` **without a trailing slash** — a trailing-slash pattern
only matches real directories, and the symlink would then show up untracked and be deleted
by a `git clean -fd`, orphaning every past report. That comment is in the file; leave it there.

`update.sh` re-asserts all three symlinks on every deploy anyway, as cheap insurance
against a bad tree state.

---

# Teil 4 — Day-2 operations

Unless stated otherwise, run these on the server as root
(`ssh root@178.105.10.156`).

## 4.0 The one recipe you will reuse: run something with the service's environment

The secrets live in `/etc/auralis/portal.env`. Do **not** source it into your shell or
splice it into a command line — it would land in your shell history, in `ps`, and possibly
in a log. Use systemd, which reads the file itself:

```bash
run_as_auralis() {   # run_as_auralis <binary> [args…]
  systemd-run --pipe --quiet --wait --collect \
    -p User=auralis -p Group=auralis \
    -p EnvironmentFile=/etc/auralis/portal.env \
    -p Environment=HOME=/opt/auralis \
    -p Environment=PATH=/opt/auralis/.local/bin:/opt/auralis/bin:/usr/local/bin:/usr/bin:/bin \
    -p WorkingDirectory=/opt/auralis/app/portal \
    "$@"
}
```

Everything in §4.5–§4.8 and most of §5 uses it.

## 4.1 Logs

```bash
journalctl -u auralis-portal -f                    # live
journalctl -u auralis-portal -n 200 --no-pager     # last 200 lines
journalctl -u auralis-portal --since '1 hour ago' --no-pager
journalctl -u cloudflared-auralis -n 100 --no-pager
journalctl -u auralis-update -n 50 --no-pager      # deploy history
journalctl -u auralis-backup -n 20 --no-pager
```

`SyslogIdentifier` is set on every unit, so `journalctl -t auralis-portal` works too.
The journal is **shared with canei-erp** — read it, never reconfigure it (§7.3).

## 4.2 Status and restart

```bash
systemctl status auralis-portal --no-pager
systemctl list-timers 'auralis-*' --no-pager
curl -sS http://127.0.0.1:5056/health            # → {"ok":true,"time":"…"}

systemctl restart auralis-portal                 # ~2 s of downtime
systemctl restart cloudflared-auralis            # ONLY ever the -auralis one
```

A restart is safe at any moment: SQLite is in WAL mode with a 15 s busy timeout, and every
write path goes through `store.upsert` / `update_existing` in a single transaction.

## 4.3 Deploy a change

```bash
# on your machine
git push origin main
```

That is the whole procedure. `auralis-update.timer` picks it up within ~2 minutes: fetch →
`reset --hard` → `pip install -r requirements.txt` → re-assert symlinks → restart.

To not wait:

```bash
systemctl start auralis-update.service && journalctl -u auralis-update -n 20 --no-pager
```

Look for `updating <old> -> <new>`. If it prints nothing, `origin/main` had not moved.

**Rolling back a bad commit** means pushing a revert — the server always tracks
`origin/main` and will undo any manual fix within two minutes (see §5.6).

## 4.4 The tunnel

```bash
systemctl is-active cloudflared-auralis
awk '/^tunnel:/ {print $2}' /etc/cloudflared/auralis.yml     # which tunnel id we run
journalctl -u cloudflared-auralis -n 40 --no-pager | grep -i 'registered\|connection'
curl -sS -o /dev/null -w '%{http_code}\n' https://api.auralisnatura.com/health
```

A healthy connector logs `Registered tunnel connection` four times (four edge locations).
The public `curl` is the only honest end-to-end proof — a loopback health check cannot tell
you whether Cloudflare can reach you.

## 4.5 Take a backup now

```bash
systemctl start auralis-backup.service
journalctl -u auralis-backup -n 5 --no-pager      # → backup written: /var/backups/auralis/auralis-…
ls -lh /var/backups/auralis/
```

Do this **before** any restore, any secret change and any risky experiment.

## 4.6 Restore a backup

```bash
# 1. stop the app AND the updater (so a deploy can't restart it mid-restore)
systemctl stop auralis-update.timer auralis-portal

# 2. unpack somewhere neutral and LOOK at it before trusting it
mkdir -p /var/lib/auralis/.restore && cd /var/lib/auralis/.restore
tar -xzf /var/backups/auralis/auralis-20260808-032011.tar.gz
ls -l                                  # expect auralis.db, clients.json, output_docs/

# 3. keep what is there now (never overwrite the only copy you have)
cp -a /var/lib/auralis/auralis.db /var/lib/auralis/auralis.pre-restore-$(date -u +%Y%m%d-%H%M%S).db

# 4. clear stale WAL/SHM, then put the files back
rm -f /var/lib/auralis/auralis.db-wal /var/lib/auralis/auralis.db-shm
cp -a auralis.db clients.json /var/lib/auralis/
cp -a output_docs/. /var/lib/auralis/output_docs/     # merge, never replace
chown -R auralis:auralis /var/lib/auralis
cd / && rm -rf /var/lib/auralis/.restore

# 5. PROVE the key still opens it before you let anyone in
systemctl start auralis-portal
journalctl -u auralis-portal -n 30 --no-pager | grep -i 'AURALIS_DATA_KEY' || echo "no key banner — good"
systemctl start auralis-update.timer
```

Step 3 and the WAL removal are not optional. Dropping a `.db` next to a stale `-wal` from a
different database is a reliable way to corrupt both.

The **hourly** in-app snapshots under `/var/lib/auralis/backups/auralis-<ts>/` have their own
tool, which also makes the safety copy for you:

```bash
run_as_auralis /opt/auralis/venv/bin/python tools/restore.py --list
run_as_auralis /opt/auralis/venv/bin/python tools/restore.py --latest
```

## 4.7 Rotate a secret

```bash
sudoedit /etc/auralis/portal.env          # preserves owner and mode
stat -c '%a %U:%G' /etc/auralis/portal.env    # must print: 640 root:auralis
systemctl restart auralis-portal
```

| Variable | Rotating it is… | Consequence |
|---|---|---|
| `AURALIS_API_KEY` | routine | Desiree must enter the new key in `/staff` once. |
| `AURALIS_SECRET` | routine | Every client's portal session token is invalidated; they log in again. Report-download tokens are 90 s, so nothing else breaks. |
| `AURALIS_SMTP_PASSWORD` | routine | Generate a new Gmail App Password for `team@auralisnatura.com`. |
| `CLAUDE_CODE_OAUTH_TOKEN` | routine | Must be re-minted **on the Mac** (`claude setup-token` is interactive). Verify with §4.8 afterwards, or reports silently become stubs. |
| **`AURALIS_DATA_KEY`** | **do not** | This key is the only thing that can decrypt `auralis.db`. There is **no re-encryption tool in this repo.** Changing it does not re-encrypt anything — it orphans every existing record, `key_matches_store()` goes `False`, and the console 500s on every client. If it truly must change, first export every client via the console's GDPR export **with the old key still in place**, and treat the migration as a data project, not a config change. |

Never put a secret in a git commit, a ticket, a chat message, or a shell command line.

## 4.8 Verify the whole thing, and the checks worth knowing individually

The full verifier, invoked exactly the way `migrate_to_server.sh` invokes it:

```bash
sudo -u auralis env HOME=/opt/auralis \
  AURALIS_PORT=5056 AURALIS_HOSTNAME=api.auralisnatura.com \
  AURALIS_ENV_FILE=/etc/auralis/portal.env \
  bash /opt/auralis/app/portal/deploy/verify_server.sh
```

Exit 0 = healthy. It is also runnable as a python self-check, importable or from the CLI:

```bash
run_as_auralis /opt/auralis/venv/bin/python tools/preflight.py          # human
run_as_auralis /opt/auralis/venv/bin/python tools/preflight.py --json   # {"ok":bool,"checks":[…]}
```

The three probes to know by heart, because they map onto the three worst failure modes:

```bash
# (a) does the data key open the store?  True | False | None
run_as_auralis /opt/auralis/venv/bin/python -c \
  'import sys;sys.path.insert(0,".");from lib import store;print(store.key_matches_store())'

# (b) will PDFs render, or silently degrade to .html?  path | None
run_as_auralis /opt/auralis/venv/bin/python -c \
  'import sys;sys.path.insert(0,".");from lib import render;print(render._chrome())'

# (c) is the report agent real, or a stub?
sudo -u auralis env HOME=/opt/auralis PATH=/opt/auralis/.local/bin:/usr/local/bin:/usr/bin:/bin \
  bash -lc 'command -v claude || echo "NO CLAUDE CLI -> provider will be stub"'
```

**On `CLAUDE_CODE_OAUTH_TOKEN` — read this honestly.** What is *verified*: the subcommand
`claude setup-token` exists and is documented as "Set up a long-lived authentication token
(requires Claude subscription)", it is interactive/browser-based, and `portal/lib/agent.py`
invokes `claude -p <prompt> --output-format text`. What is **not** verified is that this
version of the CLI reads that exact variable name. Do not assume it — **test it**, in a
clean environment, as the service user:

```bash
systemd-run --pipe --quiet --wait --collect \
  -p User=auralis -p EnvironmentFile=/etc/auralis/portal.env \
  -p Environment=HOME=/opt/auralis \
  -p Environment=PATH=/opt/auralis/.local/bin:/usr/local/bin:/usr/bin:/bin \
  /opt/auralis/.local/bin/claude -p 'Reply with the single word OK.' --output-format text
```

`OK` means the name is right *for this version*. An auth error means the CLI is not picking
the token up from that variable — find the name the installed version actually documents
(`claude --help`, `claude setup-token --help`), put the token under that name **as well**,
and re-run this exact probe. Never conclude from "the service started" that the agent works.

## 4.9 How the auto-update loop behaves — the rules

- It is a **pull**, every 2 minutes, of `origin/main`. Nothing pushes to the server.
- It uses `git reset --hard`. **Any uncommitted edit inside `/opt/auralis/app` is destroyed
  within two minutes.** See §5.6.
- It does **not** run `git clean`. Untracked files survive — which is why the data symlinks
  are safe, and also why stray files you leave behind will accumulate quietly.
- A failed `git fetch` (network blip, revoked deploy key) logs and exits 0. The app keeps
  running on the old commit. This is deliberate: an update mechanism must never be able to
  take the service down.
- A failed `pip install` logs `pip install failed — restarting with the old deps` and
  restarts anyway. If a commit adds a dependency and pip cannot reach PyPI, you get a
  running-but-broken app — check `journalctl -u auralis-update` after any dependency change.
  (The dependency set is deliberately tiny: `flask>=3.0` and `cryptography>=41`.)
- The restart is unconditional once `origin/main` has moved, so a push during a client's
  intake submission can drop that one request. Push outside working hours when you can.

---

# Teil 5 — Failure playbook, by symptom

Organised by what you *see*, because that is how this gets used at 2 a.m.

## 5.1 The site shows Cloudflare **Error 1033** (or times out)

**What you see.** `https://api.auralisnatura.com` returns Cloudflare's "Argo Tunnel error"
page. The portal, the console and the booking page are all gone at once. `/health` does not
answer either.

**Confirm it:**

```bash
systemctl is-active cloudflared-auralis
```

**Fix, in order:**

1. `inactive`/`failed` → `systemctl restart cloudflared-auralis && journalctl -u cloudflared-auralis -n 40 --no-pager`.
2. `active` but the site is still 1033 → the connector is running **the wrong tunnel**. This
   is the historical cause: Paramur's tunnel got run instead of Auralis's. Assert the identity,
   never guess it:
   ```bash
   awk '/^tunnel:|^credentials-file:/' /etc/cloudflared/auralis.yml
   # the id in tunnel: must equal the "TunnelID" inside the credentials JSON:
   python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["TunnelID"])' \
     /etc/cloudflared/auralis-<TUNNELID>.json
   ```
   Mismatch → fix `auralis.yml` (or re-run the installer with the right `AURALIS_TUNNEL_ID`)
   and restart **only** `cloudflared-auralis`.
3. Both fine, still 1033 → check whether **the Mac** is also a connector. Two connectors for
   one tunnel is not just a wrong-data problem, it also produces intermittent 1033s while
   one of them flaps. On the Mac: `launchctl list | grep com.auralis` — it must be empty
   after cutover.
4. Tunnel healthy but Flask is down → §5.2's first command; `cloudflared` will report
   `dial tcp 127.0.0.1:5056: connect: connection refused` in its log.

## 5.2 `/staff` returns **500** (or the client list is empty)

**What you see.** Booking and `/health` still work; the console loads its shell and then
errors, or shows zero clients where there were seven.

**Confirm it — this one command distinguishes the two causes:**

```bash
run_as_auralis /opt/auralis/venv/bin/python -c \
  'import sys;sys.path.insert(0,".");from lib import store;print(store.key_matches_store())'
```

- **`False`** → **the July failure mode.** `AURALIS_DATA_KEY` does not match the data. Every
  staff read raises `DecryptError` → 500. The app logs a huge banner at startup for exactly
  this (`server/app.py` `main()`), so also check
  `journalctl -u auralis-portal | grep -A2 'does NOT match'`.
  **Fix:** restore the *correct key*, not the data. Find the key that was in use when those
  records were written (`portal/.env` on the Mac is the canonical copy), put it in
  `/etc/auralis/portal.env`, restart. **Do not overwrite the store**, do not "reinitialise",
  do not delete records to make the error stop — the data is intact and recoverable only for
  as long as you leave it alone.
- **`None`** → the database file cannot be read at all. Check the symlink and permissions:
  ```bash
  ls -l /opt/auralis/app/portal/auralis.db /var/lib/auralis/auralis.db
  ```
  A dangling symlink (after a hand-run `git clean -fd`, say) is the usual cause →
  `systemctl start auralis-update.service` re-asserts all three.
- **`True`** → the key is fine; it is an ordinary application error.
  `journalctl -u auralis-portal -n 100 --no-pager` and read the traceback.

Empty-but-200 client list with `True` usually means `clients.json` is the fresh seed rather
than the real file: `wc -c /var/lib/auralis/clients.json` — a ~40-byte file is the empty seed.
Restore it from a backup (§4.6).

## 5.3 The report comes out as **`.html`** instead of the 12-page PDF

**What you see.** The console reports success, but the generated file is `report.html`, and
the client gets a web page instead of the branded PDF. `portal/lib/render.py` falls back to
writing `.html` when no Chrome is found *or* when the headless render fails — a silent
degradation, which is why the installer PDF-tests Chromium at install time.

**Confirm it:**

```bash
run_as_auralis /opt/auralis/venv/bin/python -c \
  'import sys;sys.path.insert(0,".");from lib import render;print(render._chrome())'
```

- Prints `None` → no Chromium. `apt-get install -y chromium` (Debian) — and it must **not**
  be a snap: a confined snap cannot read the temp HTML `render.py` writes to `/tmp`, so
  `--print-to-pdf` produces nothing and you land in the same fallback. Then set
  `AURALIS_CHROME=/usr/bin/chromium` in `/etc/auralis/portal.env` and restart.
- Prints a path → the binary exists but the render failed. Reproduce it by hand:
  ```bash
  run_as_auralis /usr/bin/chromium --headless --disable-gpu --no-sandbox \
    --print-to-pdf=/tmp/t.pdf about:blank ; ls -l /tmp/t.pdf
  ```
  Remember `PrivateTmp=yes` is set on the unit — the service's `/tmp` is its own. If it
  works by hand but not in the service, that is the difference to investigate.
- Missing fonts make the PDF render but look wrong: `fonts-liberation` is installed by the
  installer for this reason.

**Clean-up.** Any `.html` already produced should be regenerated, not sent. Delete the
stray file under `/var/lib/auralis/output_docs/<AN-xxxx>/report/` and generate again.

## 5.4 Report drafts suddenly read like the **stub**

**What you see.** Drafts are generic and formulaic — the same skeleton for every client, no
real synthesis. The console's log line for the draft says `report drafted (stub)` or
`report drafted (stub (claude_cli failed: …))` instead of `report drafted (claude_cli)`.

**Confirm it:**

```bash
journalctl -u auralis-portal --since '2 days ago' --no-pager | grep -i 'report drafted'
```

`agent.draft_report()` requires **both** `agent_provider == "claude_cli"` **and**
`shutil.which("claude")`; if the CLI then errors, it catches the exception and returns the
stub with the reason embedded in the provider string. So there are three causes and the
provider string tells you which:

| Provider string | Cause | Fix |
|---|---|---|
| `stub` | `AURALIS_AGENT_PROVIDER` is not `claude_cli`, **or** the `claude` binary is not on the service's `PATH`. | `grep -c '^AURALIS_AGENT_PROVIDER=claude_cli' /etc/auralis/portal.env` and the `command -v claude` probe in §4.8. Install the CLI **as the `auralis` user** so it lands in `/opt/auralis/.local/bin` (already on the unit's `PATH`). |
| `stub (claude_cli failed: …)` with an auth message | token missing, expired, or under the wrong variable name. | Re-mint on the Mac with `claude setup-token`, update `/etc/auralis/portal.env`, restart, then run the §4.8 clean-environment probe. Do not declare it fixed until that probe prints `OK`. |
| `stub (claude_cli failed: …)` with a timeout | The CLI call has a 180 s timeout in `agent.py`. Slow network or a very large intake. | Retry; check egress from the box. |

**This must never be silent.** A stub draft that reaches the approval gate looks plausible
enough to approve. Tell Desiree the rule from Teil 1: a generic-sounding draft is a bug
report, not a writing problem.

## 5.5 Disk filling

**What you see.** Writes fail, backups fail, SQLite throws `database or disk is full`. On a
shared box this hurts canei-erp too — treat it as urgent regardless of whose data grew.

**Confirm it:**

```bash
df -h / /var /opt
du -sh /var/lib/auralis/* /var/backups/auralis 2>/dev/null | sort -h
```

**Where Auralis growth actually comes from, in order of likelihood:**

1. **`/var/backups/auralis`** — the daily tarball includes `output_docs`, so you keep **14
   copies of every PDF and `.eml` ever produced**. This is the fastest-growing path by far.
   Reduce the retention in `/etc/auralis/backup.sh` (`tail -n +15` → a smaller number) — but
   note the file is marked *managed*: re-running `install_server.sh` rewrites it, so make the
   same change in `portal/deploy/install_server.sh` and push, or the fix evaporates on the
   next install.
2. **`/var/lib/auralis/backups`** — 48 hourly snapshots, each a full `auralis.db` copy.
   Lower `backup_keep` / raise `backup_interval_hours` in `portal/config/config.json`
   (tracked in git → push it; the update timer deploys it).
3. **`/var/lib/auralis/output_docs`** — grows with every report and every sent mail
   (`.eml` audit copies). Do not prune it casually: those `.eml` files are the delivery audit
   trail, and the PDFs are what a client may ask you to re-send.
4. **The journal** is system-wide. `journalctl --disk-usage` tells you the size, but
   **do not** change `journald.conf` or run a global vacuum — that is canei-erp's log too
   (§7.3). If the journal is the problem, that is a conversation with the other owner, not a
   unilateral fix.

**Never** free space by deleting something you have not identified, and never delete inside
another app's paths.

## 5.6 The update timer is fighting a local edit

**What you see.** You edit a file in `/opt/auralis/app` to test a fix; within two minutes the
edit is gone and the service restarts. Or: `journalctl -u auralis-update` shows an `updating
… -> …` line every couple of minutes for the same pair of hashes.

**Confirm it:**

```bash
systemctl list-timers 'auralis-*' --no-pager
git -C /opt/auralis/app status --short
git -C /opt/auralis/app log --oneline -1
```

**Fix.** The server is a **pull-only mirror of `origin/main`** and that is a feature, not an
obstacle: it guarantees that what runs in production is what is in the repo. So:

```bash
# to experiment on the box, first take the updater out of the loop
systemctl stop auralis-update.timer
#   … edit, test, learn …
# then throw the local edit away and fix it properly in the repo
git -C /opt/auralis/app checkout -- .
systemctl start auralis-update.timer          # ← DO NOT FORGET THIS
```

A stopped `auralis-update.timer` is a silent outage of your deploy pipeline: pushes stop
arriving and nobody notices for days. If you must leave it stopped, write yourself a
reminder. `systemctl list-timers 'auralis-*'` is the one command that catches it.

## 5.7 Two extra symptoms worth having in the same list

**Port 5056 is taken / the app restart-loops.**
```bash
systemctl status auralis-portal --no-pager ; ss -ltnp 'sport = :5056'
```
If the listener is a **foreign** process, do **not** kill it — that is the co-hosting rule
(§7.4), and it is also how a stale process once answered with the *wrong* data on the Mac.
Identify the owner, talk to them, and if necessary move Auralis to another loopback port via
`AURALIS_PORT` in `/etc/auralis/portal.env` **plus** the `service:` line in
`/etc/cloudflared/auralis.yml`, then restart both units.

**E-mails stop appearing as Gmail drafts.**
`AURALIS_EMAIL_MODE=draft` means `portal/lib/mailer.py` does an IMAP `APPEND` into
`"[Gmail]/Drafts"` with the App Password. The server is in a different country from the Mac,
so the first connections come from a new IP.
```bash
journalctl -u auralis-portal --since '1 day ago' --no-pager | grep -i 'imap\|smtp\|draft'
```
Read the actual error before assuming a Google block; a wrong/rotated App Password looks
identical from the outside. Check the Google account's security alerts as well.

---

# Teil 6 — Interaktive Checkliste nach jedem Eingriff

Nach *jeder* Änderung am Server, egal wie klein:

```bash
sudo -u auralis env HOME=/opt/auralis AURALIS_PORT=5056 \
  AURALIS_HOSTNAME=api.auralisnatura.com AURALIS_ENV_FILE=/etc/auralis/portal.env \
  bash /opt/auralis/app/portal/deploy/verify_server.sh
curl -sS -o /dev/null -w '%{http_code}\n' https://api.auralisnatura.com/health
systemctl list-timers 'auralis-*' --no-pager
```

Green, `200`, and both timers scheduled. Anything else: you are not done.

---

# Teil 7 — Co-hosting with canei-erp

This box runs another company's production ERP. The user is admin of both, which is
convenient and dangerous in exactly equal measure.

## 7.1 What is genuinely shared

| Shared | Consequence |
|---|---|
| **Kernel** | A kernel panic or an OOM kill takes both down. |
| **CPU — 4 vCPU** | A Chromium PDF render is a CPU spike. It is short (seconds) and rare (per report), but it is real. |
| **RAM — 8 GB** | The Linux OOM killer picks a victim by score, not by owner. It can kill canei-erp because Auralis rendered a PDF. See §7.5. |
| **Disk — 80 GB** | One filesystem. Auralis backups filling it will break canei-erp's writes. §5.5. |
| **Public IP `178.105.10.156`** | Both are reachable only via their own tunnels; but IP reputation (mail, rate limits, abuse reports) is shared. |
| **`/usr/bin/cloudflared`** | One binary, two instances. This is why our unit passes `--no-autoupdate`: an autoupdate would swap the binary under the other tunnel too. |
| **systemd, journald, apt** | Shared control plane. §7.3. |

## 7.2 What is **not** shared

Separate system user and group (`auralis`), separate home (`/opt/auralis`), separate data
(`/var/lib/auralis`), separate secrets (`/etc/auralis`), separate backups
(`/var/backups/auralis`), separate units (all prefixed `auralis-` or
`cloudflared-auralis`), separate tunnel and credentials
(`/etc/cloudflared/auralis*`), separate port (5056, **loopback only**).

`auralis-portal.service` also carries `ProtectSystem=strict`, `ProtectHome=true`,
`NoNewPrivileges=true`, `PrivateTmp=true` and an explicit
`ReadWritePaths=/var/lib/auralis /var/backups/auralis /opt/auralis`. **`strict`, not `full`,
is the load-bearing word.** `ProtectSystem=full` only makes `/usr`, `/boot` and `/etc`
read-only — `/var/lib`, `/srv` and `/opt` stay writable, so a `ReadWritePaths=` beside it
restricts nothing at all and the claim of containment is false. `strict` makes the whole
hierarchy read-only and `ReadWritePaths=` then genuinely is the complete list of what the
service can write.

It is also bounded, because headless Chromium forks per report render on a box that is only
4 vCPU / 8 GB and is shared: `MemoryHigh=1G`, `MemoryMax=1500M`, `CPUQuota=150%`,
`TasksMax=256` (override with `AURALIS_MEM_MAX=…` etc. and re-run the installer). Without
ceilings, one Auralis PDF render can push the host into the OOM killer, and the OOM killer
does not know that canei-erp matters more.

### The co-tenant separation tier

On top of that, both `auralis-portal.service` and `cloudflared-auralis.service` carry a
second block whose only purpose is separating the two companies. It is the difference
between *cannot damage* canei and *cannot see* canei:

| Directive | What it stops |
|---|---|
| `ProtectProc=invisible` + `ProcSubset=pid` | `/proc` shows only Auralis's own processes. Without it the `auralis` user can `ps aux` and read canei's **full command lines** — which is where database URLs and API tokens habitually leak. |
| `CapabilityBoundingSet=` (empty) | No capabilities at all. In particular this drops **`CAP_DAC_OVERRIDE` / `CAP_FOWNER`**, the capabilities that let a process bypass file permissions entirely — i.e. read canei's files regardless of ownership. |
| `InaccessiblePaths=` | The co-tenant's directories (auto-detected under `/srv`, `/var/www`, and anything matching `*canei*`) are not merely read-only, they are **absent** from the service's view of the filesystem. |
| `SystemCallFilter=@system-service` + deny `@privileged @resources @obsolete` | A seccomp allow-list. Mounting, module loading, ptrace and clock changes are refused by the kernel, not by convention. |
| `UMask=0077` | Anything Auralis creates is unreadable to every other account on the box, whatever the directory mode says. |
| `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX` | No packet or netlink sockets — no sniffing the shared interface. |
| `PrivateDevices` · `ProtectHostname` · `ProtectClock` | No raw device nodes; cannot rename the host or move its clock out from under canei's logs. |

Measured with `systemd-analyze security`, that block moves the portal from
**7.0 (MEDIUM)** to **2.2 (OK)**, and the tunnel sits at **1.5 (OK)**.

**It is applied adaptively, and this matters.** Headless Chromium is the fragile part: a
seccomp filter or `PrivateDevices` can break it, and a broken renderer means every client
report silently degrades from a 12-page PDF to `.html`. So the installer renders a real PDF
inside the exact sandbox first. If the strict tier fails that probe it **automatically drops
to the base tier and says so loudly**, rather than failing the install or shipping a service
that quietly produces the wrong file. Check which tier you got:

```bash
systemctl show auralis-portal -p CapabilityBoundingSet -p SystemCallFilter | head -2
systemd-analyze security auralis-portal.service | tail -1
```

An empty `CapabilityBoundingSet=` means you are on the strict tier.

**What none of this gives you: protection from root.** Anyone with root on this host can
read `/etc/auralis/portal.env`, take the Fernet key and decrypt the client database. The
separation above is between the two *services*, not between the two *administrators*. Since
you administer both companies that is a deliberate, accepted position — but it is the honest
limit of co-hosting, and it is why §8 says what it says about GDPR.

## 7.3 The paths Auralis owns — the complete list

```
/opt/auralis                       /var/lib/auralis
/etc/auralis                       /var/backups/auralis
/etc/cloudflared/auralis*          /etc/systemd/system/auralis-*
/etc/systemd/system/cloudflared-auralis.service
```

**Nothing outside this list is ours.** If a fix requires touching something outside it, that
is a conversation with the other owner, not a unilateral change.

## 7.4 Operational rules — the ones that keep the two apart

1. **Never `systemctl restart cloudflared`.** Always the full name
   `cloudflared-auralis`. Tab-completion after `cloudflared` will happily offer you the other
   company's unit. Type it out.
2. **Never `apt upgrade` / `apt dist-upgrade`.** Only `apt-get install -y <specific package>`.
   A distro upgrade on a shared production box is someone else's outage.
3. **Never touch the firewall.** No `ufw`, no `nft`, no `iptables -F`. Detect and *report*:
   `nft list ruleset | head -40` or `ufw status`. Report only.
4. **Never kill a process you did not start.** If port 5056 is held by a foreign process,
   abort and ask — `install_server.sh` exits 13 rather than kill it, and you should behave
   the same way by hand.
5. **Never run global cleanups.** No `docker system prune`, no `journalctl --vacuum-*`,
   no `find / -delete`, no `pip` / `npm -g` installs into system paths. Install python
   packages into `/opt/auralis/venv`, node/CLI tools into `/opt/auralis/.local`.
6. **Reboots.** If canei-erp needs one, Auralis comes back on its own — every unit is
   `enable`d and `auralis-backup.timer` is `Persistent=true` so a missed backup catches up.
   Run the §6 checklist afterwards anyway.
7. **Announce your maintenance windows to the other owner, and expect the same.** Shared
   kernel, shared consequences.

## 7.5 If the two ever actually compete for resources

Do **not** edit `auralis-portal.service` — `install_server.sh` compares units byte-for-byte
and will rewrite yours on the next install. Use a drop-in, which the installer does not
touch:

```bash
mkdir -p /etc/systemd/system/auralis-portal.service.d
cat > /etc/systemd/system/auralis-portal.service.d/limits.conf <<'EOF'
[Service]
MemoryMax=1200M
CPUWeight=50
EOF
systemctl daemon-reload && systemctl restart auralis-portal
```

Pick the numbers from measurement (`systemctl status auralis-portal` shows current memory),
not from a guess, and re-check that PDF rendering still succeeds afterwards — Chromium is
the memory-hungry part, and a `MemoryMax` that is too tight turns §5.3 into your new problem.

---

# Teil 8 — GDPR & security

## 8.1 What data this is

**Special-category personal data under GDPR Art. 9** — health data. Intake answers (energy,
sleep, digestion, life stage, medications, pregnancy, red-flag screen), call notes, and the
report drafts built from them. This is the highest tier of protection in the regulation.
Handle it accordingly: the convenience shortcut you would take with ordinary data is not
available here.

## 8.2 Where it sits, and how it is protected

| Path | Contents | Encrypted at rest? |
|---|---|---|
| `/var/lib/auralis/auralis.db` | One row per client. `client_id`, `stage`, `created`, `updated` in **clear**; intake, prep, notes and report in a **Fernet-encrypted blob** (`portal/lib/store.py`). Plus an `events` table with anonymous funnel events — no personal data, which is why they survive erasure and keep the KPIs truthful. | **Yes**, the blob. |
| `/var/lib/auralis/clients.json` | Name, e-mail, phone, language, status, PBKDF2-SHA256 password hash (240 000 rounds), consent record with timestamp + version. **No health data.** | **No.** |
| `/var/lib/auralis/output_docs/` | Rendered report PDFs, `.eml` audit copies of every mail, booking `.ics`. | **No — plaintext on disk.** |
| `/var/lib/auralis/backups/`, `/var/backups/auralis/` | Copies of all of the above. | Inherits the above: DB encrypted, PDFs not. |
| `/etc/auralis/portal.env` | `AURALIS_DATA_KEY` — the key to the blobs — plus the SMTP password, staff key and Claude token. `0640 root:auralis`. | No (it *is* the key). |

## 8.3 Who can read it — the honest answer

- **The `auralis` service user** — by design.
- **`root` on this host — completely.** Root reads `/etc/auralis/portal.env`, therefore holds
  `AURALIS_DATA_KEY`, therefore can decrypt every record; and the PDFs are plaintext anyway.
  There is no configuration of this system in which root cannot read client health data.
- **Therefore: everyone with root on this box is, in GDPR terms, personnel of the controller
  or of a processor** — including the admin who is primarily there for canei-erp. That has to
  be true on paper as well as in fact: a confidentiality undertaking, a named person, and a
  record of who has access. If you are not willing to write that down, the person should not
  have root.
- **Hetzner** is a **processor** (Art. 28). A signed data-processing agreement / AVV is
  required — Hetzner provides one in its console; make sure it is executed and filed with the
  business records. **Confirm and write down this server's datacentre region.** If it is
  outside the EEA, that is a transfer question that needs answering, not assuming.
- **Cloudflare** terminates TLS and is also a processor; `/staff` sits behind Cloudflare
  Access as a second factor in front of the staff key. That is unchanged by this migration —
  it is bound to the hostname and path, not to the machine.
- **Anthropic** sees only **pseudonymised** intake (`agent.pseudonymise()` strips
  identifiers before the prompt is built), and only when a draft is requested.

What the encryption actually buys you: a stolen disk, a leaked backup tarball, or a copied
`auralis.db` is useless **without** `/etc/auralis/portal.env`. That is a real and worthwhile
protection. It is not a protection against this host's own root, and you should never
describe it to a client as if it were.

## 8.4 Retention and erasure

- `portal/config/config.json` declares `retention_days: 1095` (three years). **Be honest
  about what that is:** a stated policy. **Nothing in this repo enforces it on a schedule.**
  There is no cron job that deletes aged records. If the privacy notice promises automatic
  deletion, that promise is currently kept by hand.
- **Erasure is per client, from the console** (`DELETE /api/client/<cid>`): it removes the
  encrypted DB row, the `clients.json` login, and `output_docs/<cid>/` (PDFs and `.eml`).
  The anonymous `events` rows deliberately remain — they contain no personal data.
- **Backups lag erasure.** An erased client still exists inside:
  - `/var/lib/auralis/backups/` — 48 hourly snapshots ⇒ up to **~2 days**;
  - `/var/backups/auralis/` — 14 daily tarballs ⇒ up to **14 days**.

  So the truthful erasure SLA is **"removed from the live system immediately, from all
  backups within 14 days."** Say that in the privacy notice; do not claim instant erasure.
  If a data subject demands faster, the only correct answer is to purge the specific archives
  by hand and record that you did.
- **GDPR export** (`GET /api/client/<cid>/gdpr-export`) returns the login record plus the full
  decrypted record — that file is as sensitive as the database. Do not leave it in
  `~/Downloads`.

## 8.5 What the admin must not do

1. **Do not copy `auralis.db`, `clients.json`, `output_docs/` or any backup tarball off this
   server** onto a laptop, a personal cloud drive, or a shared folder. If you need a copy to
   debug, work on the server; if you truly must move it, that is a documented transfer with a
   reason and a deletion date.
2. **Do not paste client data anywhere** — not into a ticket, a chat, a commit message, a
   pastebin, or an LLM prompt. The application pseudonymises before it talks to a model; you
   should meet the same bar.
3. **Do not put `AURALIS_DATA_KEY` anywhere except `/etc/auralis/portal.env` and the Mac's
   `portal/.env`.** Not in a commit (a `.p8` once ended up in this repo's history — see
   `CLAUDE.md`), not in a ticket, not in a note without a password.
4. **Do not bind the app to a public interface** and do not add a reverse proxy in front of
   it "for convenience". Loopback + tunnel is the entire security model.
5. **Do not switch `AURALIS_EMAIL_MODE` to `send`** without Desiree's explicit decision. The
   draft gate is a clinical-safety control, not a preference: it is what guarantees a human
   reads every word before a client does.
6. **Do not share the staff key**, and do not remove the Cloudflare Access policy on `/staff`.
7. **Do not "fix" a decryption error by reinitialising the store.** §5.2. The data is
   recoverable exactly as long as you leave it alone.
8. **Do not approve or generate anything on Desiree's behalf.** The approval gate is hers.
   AI output is assistive and human-led; that is a hard guardrail of this business
   (`CLAUDE.md` §2), not a workflow nicety.

---

# Teil 9 — Rollback: back on the Mac in under five minutes

## 9.1 The command

On **the Mac**, in the repo:

```bash
bash portal/deploy/rollback_to_mac.sh
```

Typical time: **about a minute**, dominated by the data rescue. `--no-pull` skips the rescue
and gets you well under a minute — use it only if the server never served real traffic.

## 9.2 What it does, in order

1. **Rescues the server's data first** (best effort): a consistent SQLite snapshot pulled to
   `~/auralis-rollback/<timestamp>/`. It is **never** promoted over the Mac's database
   automatically.
2. **Stops the server's tunnel first**, so Cloudflare stops routing there, *then* the portal
   and the timers. Everything is `disable`d as well, so a reboot cannot quietly bring the
   server back and create two live connectors.
3. **Brings the Mac back**: reloads the launchd agent `com.auralis.portal`, which starts both
   the Flask server and the Mac's tunnel.
4. **Verifies** `127.0.0.1:5056/health` and then the public URL.

Nothing on the server is deleted. The data stays there for a second attempt at migrating.

## 9.3 What you lose — the honest statement

**Everything written on the server after cutover lives in the server's database, not the
Mac's.** Roll back and the Mac resumes from the snapshot it had at cutover. Concretely, work
at risk is: bookings taken through `/book`, intakes submitted through `/portal`, call notes
and stage changes made in `/staff`, report drafts and approvals, and PDFs generated — all of
it since the moment you typed `CUTOVER`.

The script's step 1 pulls that delta down to `~/auralis-rollback/<timestamp>/`: the database
(`auralis.db`, via the online backup API on the server, not a raw copy), `clients.json`, and
`output_docs.tar.gz` — the generated report PDFs and the `.eml` delivery-audit copies. If any
of the three cannot be fetched the script says so per item and carries on; it never lets a
failed rescue block bringing the Mac back. **Read the printed path before you carry on
working on the Mac.** To actually adopt it:

```bash
bash portal/deploy/rollback_to_mac.sh --adopt-server-data
```

Before it replaces anything, that command now does three things in order, and refuses at the
first one that fails:

1. **stops the Mac's portal** and waits for it to exit, so nothing is mid-write;
2. **proves the rescued database decrypts with this Mac's `AURALIS_DATA_KEY`** and holds at
   least one record — `store.key_matches_store()`, the same probe the server runs at boot.
   `cfg.py` accepts a passphrase as well as a real Fernet key, so a server whose `portal.env`
   was ever retyped can hold a database this Mac will never open. If that is the case you get
   a refusal and an untouched Mac, not a swap followed by a 500;
3. **backs up what it is about to replace** — `auralis.db` via SQLite's online backup API so
   the **WAL is folded in**, plus `config/clients.json`. A plain `cp` of the `.db` is not a
   backup: with the portal running, the committed-but-not-checkpointed rows live only in
   `auralis.db-wal`, and a copy of the main file alone can come back with no `records` table
   at all. (Verified, not assumed.) The copies land at `portal/auralis.pre-rollback-<ts>.db`
   and `portal/config/clients.pre-rollback-<ts>.json`.

Adopt or don't — but decide deliberately, because once Desiree starts entering new work on
the Mac, merging the two databases is a manual job with no tooling behind it.

**The one case where rollback is genuinely risky: the server is unreachable.** Then step 1
cannot rescue anything (the delta is stranded, not lost) and — more importantly — step 2
cannot stop the server's `cloudflared`. If the server later comes back with its tunnel
running while the Mac is also a connector, Cloudflare will load-balance between them and
roughly half of all requests will hit a stale database. If you roll back without reaching
the server, **make stopping `cloudflared-auralis` there your very next task**:

```bash
ssh root@178.105.10.156 'systemctl disable --now cloudflared-auralis'
```

## 9.4 After a rollback

Say so out loud to Desiree — the failure modes in Teil 1 change meaning (the Mac must now
stay on and awake). Then diagnose calmly with §5, fix, and re-run the three steps in Teil 2.
Steps 1 and 2 are safe to repeat as often as you need; only step 3 moves the live site.

## 9.5 Removing Auralis from the server entirely

A rollback stops the server's units but leaves everything installed, which is what you want
between attempts. To actually take Auralis off the host — a clean decommission, or cleaning
up after an install that failed partway and left the timers enabled:

```bash
ssh root@178.105.10.156 'bash /opt/auralis/app/portal/deploy/uninstall_server.sh'
```

It stops and removes only the six `auralis-*` / `cloudflared-auralis` units and the code
(`/opt/auralis`, `/etc/auralis`, `/run/auralis`, `/etc/cloudflared/auralis*`), and **keeps all
data** — so a later `install_server.sh` picks the encrypted backbone straight back up.
`/etc/cloudflared` is only removed if it ends up empty, because the ERP's tunnel very likely
lives there too.

`--purge-data` additionally destroys `/var/lib/auralis` and `/var/backups/auralis`. That is
the encrypted health backbone, the portal logins and every generated report; it demands that
you type `DELETE`, and there is no undo. The user account is kept whenever data is kept, so
the files never end up owned by a bare uid that a future `useradd` could hand to someone else.

If something is still listening on port 5056 after the uninstall, the script tells you and
**does not kill it** — on this host, an unexplained listener is far more likely to belong to
canei-erp than to be a stale Auralis process.

---

## Appendix — command index

| I want to… | Command |
|---|---|
| See what the app is doing | `journalctl -u auralis-portal -f` |
| See deploy history | `journalctl -u auralis-update -n 50 --no-pager` |
| Restart the app | `systemctl restart auralis-portal` |
| Restart the tunnel (ours only!) | `systemctl restart cloudflared-auralis` |
| Deploy | `git push origin main` (≤2 min) — force: `systemctl start auralis-update.service` |
| Is it alive? | `curl -sS http://127.0.0.1:5056/health` · `curl -sS -o /dev/null -w '%{http_code}\n' https://api.auralisnatura.com/health` |
| Full health check | `sudo -u auralis env HOME=/opt/auralis AURALIS_PORT=5056 AURALIS_HOSTNAME=api.auralisnatura.com AURALIS_ENV_FILE=/etc/auralis/portal.env bash /opt/auralis/app/portal/deploy/verify_server.sh` |
| Self-check as JSON | `run_as_auralis /opt/auralis/venv/bin/python tools/preflight.py --json` (§4.0) |
| Does the key open the store? | see §4.8 (a) — `True` \| `False` \| `None` |
| Will PDFs render? | see §4.8 (b) — a path, or `None` |
| Is the AI agent real? | see §4.8 (c) and the token probe |
| Back up now | `systemctl start auralis-backup.service` |
| List backups | `ls -lh /var/backups/auralis/` |
| Restore | §4.6 |
| Edit secrets | `sudoedit /etc/auralis/portal.env` → `systemctl restart auralis-portal` |
| Pause auto-deploy | `systemctl stop auralis-update.timer` (**and remember to start it again**) |
| Are the timers running? | `systemctl list-timers 'auralis-*' --no-pager` |
| Which tunnel do we run? | `awk '/^tunnel:/ {print $2}' /etc/cloudflared/auralis.yml` |
| Get back to the Mac | on the Mac: `bash portal/deploy/rollback_to_mac.sh` |

## Appendix — related documents

- `portal/README.md` — what the application is and how the pipeline runs.
- `portal/deploy/install_server.sh` — the installer; its header is the authoritative contract
  (env vars consumed, payload files, exit codes 10–99, idempotence guarantees).
- `portal/deploy/migrate_to_server.sh` — the Mac-side migrator; `--help` lists every flag.
- `portal/deploy/verify_server.sh` — the post-install verifier (also runnable any time).
- `portal/tools/preflight.py` — the python self-check, importable and CLI.
- `portal/deploy/rollback_to_mac.sh` — the undo.
- `handover/auralis-portal/OPERATIONS-MANUAL.{html,pdf}` — the older Mac-era server/tunnel/
  backup setup. Superseded by this file for anything server-side; still useful for context.
- `handover/auralis-portal/OPERATOR-ONBOARDING.{html,pdf}` — Desiree's process onboarding,
  station by station. Unaffected by this migration.
- `CLAUDE.md` — project memory: guardrails (§2), the portal architecture section, and the
  standing founder preference for the low-cost option that is reliably good enough.

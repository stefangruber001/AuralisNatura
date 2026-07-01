# DEPLOYMENT_MAC — Running the Auralis Natura portal server on your Mac

This is the plain-language, step-by-step guide to running the **Auralis Natura
portal / Betriebskonsole / Cloud Report Agent** on Desiree's **Mac** — installing
it, keeping it running unattended, letting it update itself, backing it up, and
switching over to the Windows machine later.

> **Read once, top to bottom, before starting.** No developer skills required.
> Total one-time setup: **30–45 minutes**.

**What this server is (in one breath):** a small Python (Flask) program that runs
**only on your Mac**. It listens on `127.0.0.1:5056` — a private door that faces
*inward*, so nothing on the internet can reach it directly. Clients reach it only
through the **Cloudflare tunnel** (`api.auralisnatura.com`), which is set up
separately in `CLOUDFLARE_TUNNEL_AND_DOMAIN.md`. This guide is about the **server
itself** on the Mac.

The server hosts three things: the **Client-Portal** (`/portal`, intake form),
your **Betriebskonsole** (`/staff`, the cockpit), and the **Cloud Report Agent**
(the background Claude worker that drafts reports for your approval).

---

## 0 · The golden rules (read these first)

1. **Only ONE server ever runs at a time** — the Mac **or** the Windows machine,
   never both. Two at once = two copies writing different client data. Always stop
   one before starting the other.
2. **Secrets never live in the repo.** API keys, the SMTP password and the data
   encryption key are set as **environment variables** on the machine, never
   written into a file that gets committed to GitHub.
3. **A `git push` is the deploy button.** You change code by pushing to
   `stefangruber001/auralisnatura` on GitHub; within ~2 minutes the Mac pulls it
   and restarts itself. There is no separate "upload".
4. **The health data never touches an open port.** The tunnel is the only way in.

---

## 1 · Prerequisites (install these once)

You need three things on the Mac. Do them in this order.

### 1a · Xcode Command Line Tools (gives you `git`)
Open **Terminal** (`Cmd + Space`, type `Terminal`, Enter) and run:
```
xcode-select --install
```
Click **Install** in the dialog that appears (~5 min). This installs `git` and the
tools Python needs to build packages. If it says "already installed", good.

### 1b · Python 3.11 or newer
The Python that ships with macOS is too old. Get a fresh one:
1. Safari → **https://www.python.org/downloads/macos/**
2. Click the big **Download Python 3.x** button, open the `.pkg`, click through
   **Continue → Agree → Install** (enter your Mac password if asked).
3. Verify in Terminal:
   ```
   python3 --version
   ```
   You should see `Python 3.11.x` or higher. If you see "command not found", log
   out and back in, then try again.

### 1c · Git (already installed by 1a)
Confirm:
```
git --version
```
Any version is fine.

---

## 2 · One-time setup

### 2a · Get the code onto the Mac
```
cd ~/Documents
git clone https://github.com/stefangruber001/auralisnatura.git
```
The code now lives at `~/Documents/auralisnatura`. (The **portal server** lives
in the portal sub-folder of that repo — the launcher knows where it is.)

### 2b · Install the Python building blocks
```
cd ~/Documents/auralisnatura
python3 -m pip install --user -r requirements.txt
```
Wait ~1–2 minutes for `Successfully installed Flask-… …`. The self-update step
re-runs this automatically on every update, so you rarely do it by hand again.

### 2c · Create your secrets as environment variables (NOT files)
The server reads all its secrets from the environment. We store them once in your
login profile (`~/.zshrc`) so every Terminal — and the launcher — sees them.

First generate the two random keys you control:
```
python3 -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(48)); print('SECRET=' + secrets.token_urlsafe(48)); print('DATA_KEY=' + secrets.token_urlsafe(32))"
```
Copy the three values it prints. Then add all five secrets to your profile
(paste your real values in place of the `…`):
```
cat >> ~/.zshrc <<'EOF'

# --- Auralis Natura secrets (keep out of the repo) ---
export AURALIS_API_KEY="…"            # staff/API-key auth (from the command above)
export AURALIS_SECRET="…"             # session / cookie signing (from the command above)
export AURALIS_DATA_KEY="…"           # encrypts the health backbone (from the command above)
export AURALIS_SMTP_PASSWORD="…"      # Gmail App Password for team@auralisnatura.com
# No Anthropic API key: the agent runs via Claude Code on your Pro/Max subscription.
# Run `claude login` once on this Mac (sign in with the team@ Claude account).
export AURALIS_BACKUP_DIR="$HOME/Library/CloudStorage/…/Auralis_Backups"
EOF
```
Then load them into the current window:
```
source ~/.zshrc
```

Notes:
- **`AURALIS_DATA_KEY` is irreplaceable.** It encrypts the health backbone. If you
  lose it, the encrypted backups **cannot be decrypted**. Store a copy in your
  password manager (e.g. 1Password) the moment you create it.
- **Gmail App Password:** in the `team@auralisnatura.com` Google account →
  Security → turn on 2-Step Verification → search "App passwords" → create one
  labelled "Auralis" → paste the 16-character code as `AURALIS_SMTP_PASSWORD`.
- **Claude Code (Pro/Max):** run `claude login` once on this Mac, signed in with the team@auralisnatura.com Claude subscription. The agent runs on the subscription — no API key, no per-token charges (subject to the plan's usage limits).
- **Never** put any of these into `config.json` or any file you commit. `config.json`
  only references them by name (e.g. `"api_key_env": "AURALIS_API_KEY"`).

### 2d · Set the backup folder
`AURALIS_BACKUP_DIR` (above) points at an **EU cloud folder** that syncs off the
Mac — e.g. a Google Drive / Proton Drive / Tresorit folder set to an EU region.
Install that cloud client, sign into the `team@auralisnatura.com` account, and
point `AURALIS_BACKUP_DIR` at its synced folder. Backups written there are
**already encrypted** before they leave the Mac (with `AURALIS_DATA_KEY`), so the
cloud only ever holds ciphertext.

---

## 3 · The launcher — `start_auralis.command`

`start_auralis.command` is the **one file you double-click**. On start, and then
every ~120 seconds, it:

1. `git fetch origin main` and compares to what's running locally.
2. If GitHub is **newer**: `git pull` → `pip install -r requirements.txt` →
   **restart** the server with the new code.
3. Loads the secrets from your environment, binds `127.0.0.1:5056`, and serves
   `/portal`, `/staff`, `/api/*` and the agent worker.

So a `git push` reaches the Mac in about **2 minutes with no button**. You can
also force it immediately from the Betriebskonsole with the **"Jetzt holen /
Neustart"** (fetch-now / restart) button, or by stopping and re-launching.

### First launch
1. Finder → **Documents → auralisnatura**.
2. **First time only:** right-click `start_auralis.command` → **Open** → **Open**
   in the "unidentified developer" dialog. (After that, a normal double-click works.)
3. A Terminal window opens and after a few seconds prints something like:
   ```
   ============================================================
    Auralis Natura — Portal & Report Agent
    Portal:        http://localhost:5056/portal
    Betriebskonsole: http://localhost:5056/staff
    Health:        http://localhost:5056/health
   ============================================================
   ```
4. In Safari open **http://localhost:5056/health** — you should see
   `{"status":"ok", …}`. If you do, the server is live.

### Starting & stopping
- **Start:** double-click `start_auralis.command`.
- **Stop:** click the Terminal window and press **Ctrl + C** (or close the window).
  Everything already saved (encrypted backbone, generated docs) stays on disk.

---

## 4 · Keep it running unattended (auto-start + stay awake)

The Mac must be **on, awake and this server running** for clients to submit
intakes and for the agent to draft reports. Two settings make that reliable.

### 4a · Auto-start at login (Login Items)
So the server comes back after a reboot or power cut:
- **System Settings → General → Login Items → "Open at Login" → `+`** → choose
  `~/Documents/auralisnatura/start_auralis.command`.

Now every time the Mac logs in, the server starts and immediately checks for updates.

### 4b · Keep the Mac awake
- **System Settings → Lock Screen** → set "Turn display off…" as you like, but under
  **Battery / Energy** enable **"Prevent automatic sleeping when the display is off"**
  (shown when plugged in). Keep the Mac **plugged in**.
- The launcher also runs the server under macOS's **`caffeinate`** so the machine
  will not idle-sleep while the server is up. (If you ever run the server by hand,
  the equivalent is `caffeinate -s python3 …`.)

Result: a plugged-in Mac that stays awake and self-heals — it can receive intakes
and run the agent overnight without you touching it.

---

## 5 · Where your data lives (and what must never be committed)

Everything a client touches lives **locally on the Mac**, never in GitHub:

| What | Where | Notes |
|---|---|---|
| Generated docs per client | `output_docs/<CLIENT-ID>/<stage>/` | stages: `intake`, `prep`, `notes`, `report`, `sent`. One folder per client, documents versioned. |
| The health backbone | the encrypted store (SQLite w/ field-level encryption) | the intake answers + notes; **encrypted at rest** with `AURALIS_DATA_KEY`. |
| Client portal accounts | `clients.json` | logins + consent timestamps only — **no health answers**. |
| Email drafts | the Outbox (`.eml` files) | each generated mail before it becomes a Gmail draft. |

`.gitignore` in the repo already excludes `output_docs/`, the backbone, `clients.json`
and the outbox — **do not remove those lines**. If you ever add a file with real
client data, it must stay out of git. Code goes to GitHub; **client data never does.**

---

## 6 · Hourly encrypted backup + a tested restore

The running server backs up the backbone + `output_docs/` + `clients.json` to
`AURALIS_BACKUP_DIR` **every hour**, encrypted with `AURALIS_DATA_KEY`, and keeps
the **last 48** (two days). This is configured in `config.json`
(`backup_interval_hours: 1`, `backup_keep: 48`). Because the archive is encrypted
before it is written, the EU cloud folder only ever stores ciphertext.

Do a backup or restore by hand any time:
```
cd ~/Documents/auralisnatura
python3 tools/backup_auralis.py        # make an encrypted backup now
python3 tools/restore_auralis.py        # restore the NEWEST backup (asks first)
```

**Test the restore now, before you ever need it** (a backup you have not restored
is not a backup):
1. Stop the server (Ctrl + C).
2. Run `python3 tools/backup_auralis.py` and confirm a new file appears in your
   backup folder and shows up in the EU cloud web view.
3. Run `python3 tools/restore_auralis.py` → confirm → it decrypts with
   `AURALIS_DATA_KEY` and rewrites the backbone/docs.
4. Re-launch the server and open `/staff` — your clients are all still there.

If the restore fails to decrypt, your `AURALIS_DATA_KEY` does not match the one
the backup was made with — fix the environment variable before continuing.

---

## 7 · Later: migrating to the Windows "cellar" server

The plan is to move the always-on role to a **Windows machine in the cellar**
(runs 24/7, more reliable than a laptop). **Same code, same repo, same tunnel** —
only the launcher changes:

- On Windows the launcher is a **`start_auralis.ps1` / `.bat`** that does exactly
  what the `.command` does: poll `origin/main` every ~2 min, pull + `pip install`
  + restart, read the same `AURALIS_*` secrets (set with `setx` instead of
  `~/.zshrc`), back up hourly to the **same** EU cloud folder.
- Both machines sign into the **same** cloud account, so they see the **same**
  backup folder — this is what makes failover work.
- Both use the **same** Cloudflare named tunnel (its `<TUNNEL-ID>.json` copied to
  the Windows machine). Because only one server runs at a time, Cloudflare routes
  `api.auralisnatura.com` to whichever replica is currently connected — no DNS
  editing on a switch.

When Windows becomes primary, the Mac becomes the **one-click standby** (below).

---

## 8 · Failover runbook (Mac ⇄ Windows, active/passive)

Only one runs at a time; the other is a cold standby that restores the newest
backup and takes over on the same tunnel.

### When the primary is down → bring up the standby
1. **Make sure the failed machine is really stopped** (Ctrl + C / powered off) —
   never two at once.
2. On the standby, double-click the standby launcher
   (**`Notfall_Auralis_Start.command`** on the Mac / the `.bat` on Windows). It:
   pulls the latest code → **restores the newest encrypted backup** from the EU
   cloud folder (backbone + all docs) → starts the server.
3. Start the tunnel on the standby (`cloudflared tunnel run <name>`, or its login
   item). Cloudflare now routes `api.auralisnatura.com` here automatically.

Portal + Betriebskonsole work as normal. The standby keeps backing up hourly while
it covers.

### When the primary is back → hand control back
1. On the **standby**: Ctrl + C the server and stop its tunnel (its last hourly
   backup is already in the cloud).
2. On the **primary**: restore what the standby did, then resume:
   ```
   python3 tools/restore_auralis.py --yes   # (Windows: py tools\restore_auralis.py --yes)
   ```
   Then start the primary's launcher.

**Data-loss window:** failover restores the **last hourly backup**, so anything
entered in the final minutes before the primary died (up to ~1 h) may need
re-entering. Lower `backup_interval_hours` (e.g. `0.25` = every 15 min) if you
want that window tighter.

---

## 9 · Troubleshooting

| Problem | Likely cause & fix |
|---|---|
| `start_auralis.command` won't open ("unidentified developer") | First time only: right-click → **Open** → confirm. macOS remembers it after that. |
| Server not reachable at `localhost:5056` | Server isn't running → double-click the launcher. Terminal closed instantly? Run `bash ~/Documents/auralisnatura/start_auralis.command` to see the error. |
| "Address already in use" on 5056 | A copy is already running (maybe the Login Item). `pkill -f 5056` (or the server's process name) in Terminal, then re-launch. |
| `401`/"login required" in portal or console | A secret is missing from the environment → re-check §2c, then `source ~/.zshrc` and restart the server. |
| Tunnel down / `api.auralisnatura.com` unreachable but `localhost:5056` works | The server is fine; the **tunnel** is the problem. See `CLOUDFLARE_TUNNEL_AND_DOMAIN.md`: confirm `cloudflared` is running and the tunnel is connected. |
| Update didn't apply after a `git push` | Wait 2 min. Still nothing? In Terminal: `cd ~/Documents/auralisnatura && git pull` (fix any error it prints — often local edits blocking the pull), then restart. Or use "Jetzt holen / Neustart" in the console. |
| Agent errors / no report draft | Claude Code not logged in or the plan's usage limit hit → run `claude login`; wait for the limit window to reset, or use Claude Max for higher limits. |
| Backup missing from the cloud folder | Cloud client not signed in / not syncing, or `AURALIS_BACKUP_DIR` points to the wrong path → verify the folder path and that the EU cloud app is running and synced. |
| Restore won't decrypt | `AURALIS_DATA_KEY` differs from the one the backup was made with → set the correct key (from your password manager) and retry. |

**Logs** live in `output_docs/automation_log.jsonl` — open it if you need to see
what the server actually did.

---

## Quick reference card

```
START SERVER        double-click start_auralis.command
STOP SERVER         Ctrl + C in the Terminal window
AUTO-START          System Settings → Login Items → add start_auralis.command
STAY AWAKE          Energy: "Prevent sleep when display off" + keep plugged in
HEALTH CHECK        open http://localhost:5056/health
PORTAL              http://localhost:5056/portal
BETRIEBSKONSOLE     http://localhost:5056/staff
DEPLOY A CHANGE     git push  → Mac auto-pulls & restarts in ~2 min
FORCE UPDATE NOW    "Jetzt holen / Neustart" in the console, or re-launch
SECRETS             ~/.zshrc: AURALIS_API_KEY / _SECRET / _SMTP_PASSWORD /
                    _DATA_KEY / _BACKUP_DIR  (Claude via `claude login` — no key)  (never in the repo)
DATA LIVES          output_docs/<CLIENT-ID>/<stage>/ + the encrypted backbone
BACKUP NOW          python3 tools/backup_auralis.py   (hourly, encrypted, keep 48)
RESTORE NEWEST      python3 tools/restore_auralis.py
FAILOVER            stop the other machine → double-click Notfall_Auralis_Start
```

---

*Only one server runs at a time · secrets stay out of the repo · health data rides
only the Cloudflare tunnel · a `git push` is the deploy. Keep those four true and
the system runs itself.*

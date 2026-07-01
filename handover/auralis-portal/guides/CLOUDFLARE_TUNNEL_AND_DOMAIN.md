# Cloudflare + Domain — the Auralis Natura portal, in one control plane

This guide takes you, step by step, from **today** (website on GitHub Pages, the
`auralisnatura.com` domain sitting at **Squarespace**, and the portal/console/API
running only on your Mac) to the **target** setup:

- the **website** served by **Cloudflare Pages** with automatic branch previews you can
  review on your iPhone before anything goes live;
- the **portal + Betriebskonsole + API + agent** reachable at
  **`api.auralisnatura.com`** through a **Cloudflare named tunnel** — with the Flask app
  never opening a public port;
- the **Betriebskonsole (`/staff`)** double-locked behind **Cloudflare Access** (an
  emailed one-time code) on top of its API key;
- the **domain itself** moved to **Cloudflare Registrar** so everything — DNS, Pages,
  tunnel, Access — lives in one place and renews at wholesale cost.

Almost everything below is point-and-click in the **Cloudflare dashboard**; the only
command line is installing `cloudflared` (Part 3). No Flask code changes. Do the parts
**in order**: 1 → 2 → 3 → 4.

> **Repo:** `stefangruber001/auralisnatura` · **Domain:** `auralisnatura.com` ·
> **App port (local):** `127.0.0.1:5056` · **Mail:** stays exactly where it is.

---

## Part 1 — Move the domain: Squarespace → Cloudflare

### Why move it

- **Money.** Squarespace domains renew at a **retail premium**. **Cloudflare Registrar
  sells at wholesale — no markup, no upsell** (you pay the registry's cost + ICANN fee,
  and Cloudflare famously does not mark it up). For a domain you'll hold for years, that's
  a real recurring saving.
- **One control plane.** This system already uses Cloudflare for four things: **DNS**,
  **Pages** (website), the **named tunnel** (portal/API), and **Access** (the `/staff`
  gate). With the *registration* also at Cloudflare, all of it is edited on one screen
  instead of juggling two vendors and nameservers.
- **Security for free.** The tunnel + Access + TLS that protect your **health data** are
  Cloudflare features; keeping the domain there makes wiring them trivial.

### Two ways to do it (pick one)

Both end with **Cloudflare managing your DNS**; only the second also moves *billing*.

- **Option A — Change nameservers only (fastest, safest first move).** Add the site to
  Cloudflare, paste its two nameservers into Squarespace. DNS is now Cloudflare's and
  Pages/tunnel/Access all work — but the domain is **still registered (and billed) at
  Squarespace**. Reversible; transfer the registration later.
- **Option B — Transfer the registration to Cloudflare Registrar (the money-saver).**
  Moves DNS **and** billing to Cloudflare. Requires the domain to be **≥60 days old since
  registration or its last transfer** (an ICANN rule) — a long-held domain qualifies.

Do **A now, B later** if unsure; B just needs A's zone already in place.

### Before you touch anything — save the current DNS

In the **Squarespace domains dashboard**, open **DNS settings** for `auralisnatura.com`
and **write down every record**, especially the **MX** records (email routing), the **TXT**
records for **SPF / DKIM / DMARC** (deliverability), any subdomain **CNAME/A** entries, and
the current website records (the GitHub Pages entries — these we *will* replace in Part 2).
Losing MX/SPF/DKIM would break email, so this list is your safety net.

### Step 1 — Add the site to Cloudflare (needed for both options)

1. Create a free account at **dash.cloudflare.com** (use `team@auralisnatura.com`).
2. **Add a site** → type `auralisnatura.com` → choose the **Free** plan.
3. Cloudflare **scans your existing DNS** and imports what it finds. **Compare it against
   your saved list** and re-add anything missing — *especially MX and the SPF/DKIM/DMARC
   TXT records*. Do **not** delete mail records.
4. Cloudflare shows you **two nameservers** (e.g. `xxx.ns.cloudflare.com`). Copy them.

### Step 2 — Point the domain at Cloudflare (nameservers)

1. In **Squarespace → Domains → `auralisnatura.com` → Nameservers / DNS**, switch to
   **custom nameservers** and paste the two Cloudflare nameservers.
2. Save. Propagation is usually minutes, sometimes up to a day. Cloudflare emails you
   "**Great news! Cloudflare is now protecting your site**" when it's active.

At this point DNS is live on Cloudflare and you can proceed to **Part 2** (Pages) and
**Part 3** (tunnel). Email keeps flowing because you preserved the MX/TXT records.

### Step 3 — (Option B) Transfer the registration to Cloudflare Registrar

Only after Step 2 is active, and only if the domain is **≥60 days old**:

1. **At Squarespace:**
   - **Unlock** the domain (turn off the transfer lock / registrar lock).
   - **Request the EPP / authorization ("auth") code** — Squarespace shows or emails it.
   - **Temporarily disable WHOIS privacy** (some transfers stall while it's on; you can
     re-enable Cloudflare's free WHOIS redaction afterwards — Cloudflare turns it on by
     default).
   - Make sure the domain's **admin email is one you can receive** — you may get an
     approval link there.
2. **At Cloudflare → your account → Registrar → Transfer Domains.**
   - Select `auralisnatura.com`, paste the **auth code**, confirm the contact details.
   - Pay the (wholesale) transfer fee — this **adds a year** to the registration, so
     you're not double-paying, just prepaying the next year at the cheaper rate.
3. **Approve the transfer.** Click the confirmation link Cloudflare/registry email you.
   The transfer can take **a few days** (ICANN's process); the site stays up the whole
   time because DNS is already on Cloudflare from Step 2.
4. When it completes, **re-enable WHOIS privacy** (Cloudflare's is free and on by
   default) and you can **cancel the Squarespace domain auto-renew** to avoid a stray
   charge.

> **Rules to remember:** ≥60 days since registration/last transfer; domain unlocked; valid
> auth code; privacy off during the move; mail records preserved. If a transfer is blocked
> by the 60-day rule, just stay on **Option A** (nameservers) until the window opens, then
> transfer — no rush, nothing breaks.

---

## Part 2 — The website on Cloudflare Pages (dev + prod)

This replaces **GitHub Pages** as the host of the static site. The code stays in the repo;
Cloudflare builds from it and gives you preview URLs.

### What you get

| Branch you push | URL it appears at |
|---|---|
| `main` (production) | `https://auralisnatura.com` **and** `https://www.auralisnatura.com` |
| any other branch, e.g. `redesign` | `https://redesign.auralisnatura.pages.dev` (unique, automatic) |

So your workflow becomes:

1. `git checkout -b redesign` → edit → `git push origin redesign`.
2. Cloudflare builds it in ~30 seconds and gives you a **preview link**.
3. Open that link **on your iPhone**, review it calmly.
4. Happy? **Merge the branch into `main`** (or push to `main`). The same build promotes to
   `auralisnatura.com`. **That single merge is "go live".**

### One-time setup

1. **Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git.**
2. Authorise GitHub and pick **`stefangruber001/auralisnatura`**.
3. Build settings (the site is plain HTML — no build step):
   - **Production branch:** `main`
   - **Framework preset:** `None`
   - **Build command:** leave **empty**
   - **Build output directory:** `/` (repository root, where `index.html` lives)
   - Save and deploy. The first build gives you a `*.pages.dev` URL — open it and confirm
     the homepage renders, the seal shows, and the fonts load.
4. **Check the deploy artifact is complete.** With no build step, Cloudflare serves the
   repo files as-is — the same set GitHub Pages served. Confirm the published output has
   `index.html`, **`impressum.html`** (imprint/legal), **`robots.txt`**, **`sitemap.xml`**,
   **`llms.txt`**, and the **`images/`** folder (seal, portraits). Keep all of them in the
   repo so Pages picks them up directly.
5. **Add the custom domain in Pages:** the Pages project → **Custom domains** → *Set up a
   custom domain* → add **`auralisnatura.com`**, then again for **`www.auralisnatura.com`**.
   Cloudflare offers to **create/replace the DNS records** for you — accept it.
   - This **replaces** the old GitHub-Pages records (apex + `www` pointing at
     `stefangruber001.github.io`) with records pointing at the Pages project.
   - **`api.auralisnatura.com`** (the tunnel, Part 3) and your **MX / SPF / DKIM / DMARC**
     records are **untouched**.
6. **Preview deployments are on by default.** Every non-`main` branch you push gets its own
   `https://<branch>.auralisnatura.pages.dev` link automatically — find it under the
   project's **Deployments** tab, or on the commit in GitHub.
7. Once `auralisnatura.com` resolves through Pages and looks right, **disable GitHub Pages**
   in the repo's **Settings → Pages** so only one host is authoritative. (You can leave it
   on as a fallback for a day or two first — just don't point DNS at both.)

### Notes specific to Auralis

- **Pages hosts only the static site.** `/portal` and `/staff` are served by the **Flask
  app via the tunnel** (Part 3), not by Pages. Pages = the marketing homepage + legal
  pages + assets. That's why Part 4 protects the Flask side, not Pages.
- **Previews talk to the real API.** A preview build still calls `api.auralisnatura.com`
  (the tunnel), so it shows real behaviour — great for review, but a preview is **not** a
  separate database. If you ever want a true sandbox, run a second tunnel
  (`api-dev.auralisnatura.com`) and point a dev branch at it; not needed for visual review.

---

## Part 3 — The named tunnel for the local app (`api.auralisnatura.com`)

The portal, Betriebskonsole, API and report agent all run in **one Flask app** bound to
**`127.0.0.1:5056`** on the Mac. The **named tunnel** is the *only* way the internet reaches
it: `cloudflared` makes an **outbound** connection to Cloudflare, which forwards
`api.auralisnatura.com` down that connection to your local port.

**Why this matters for health data:** the Flask app **never opens a public port**, there's
no inbound firewall hole, and **TLS terminates at Cloudflare** — the special-category health
data never rides an exposed port on your Mac. The tunnel is the security boundary.

### Step 1 — Install cloudflared on the Mac

```bash
brew install cloudflared
cloudflared --version   # confirm it installed
```

### Step 2 — Log in and create the tunnel

```bash
cloudflared tunnel login          # opens a browser → pick the auralisnatura.com zone
cloudflared tunnel create auralis # creates the tunnel + a credentials file (~/.cloudflared/<UUID>.json)
```

Note the tunnel's **UUID** printed at the end — you'll see it in the config file.

### Step 3 — Route the hostname to the local app

Create **`~/.cloudflared/config.yml`**:

```yaml
tunnel: auralis
credentials-file: /Users/desiree/.cloudflared/<UUID>.json

ingress:
  - hostname: api.auralisnatura.com
    service: http://127.0.0.1:5056
  - service: http_status:404
```

Then create the DNS record that points the hostname at this tunnel (Cloudflare writes a
proxied CNAME to `<UUID>.cfargotunnel.com` for you):

```bash
cloudflared tunnel route dns auralis api.auralisnatura.com
```

### Step 4 — Test it, then run it as a service

Test in the foreground first (start your Flask app on 5056 in another terminal):

```bash
cloudflared tunnel run auralis
# now open https://api.auralisnatura.com/portal in a browser — it should reach Flask
```

Once it works, install it as a **background service** so it starts on boot and restarts if
it drops:

```bash
sudo cloudflared service install
```

That's it — `cloudflared` now runs headless. On the later **Windows** machine the same
`config.yml` + `cloudflared service install` pattern applies (both machines can share the
tunnel for the Mac↔Windows failover described in the architecture guide).

> **The app never changes.** Flask keeps binding `127.0.0.1:5056`; the auto-update
> launcher and any local scripts talk to `127.0.0.1:5056` directly and never touch
> Cloudflare. Only *browser* traffic to `api.auralisnatura.com` goes through the tunnel.

---

## Part 4 — Cloudflare Access in front of `/staff` (email one-time code)

The Betriebskonsole holds health data, so it gets **two independent locks**: the app's own
**API key** *and* a **Cloudflare Access** email-code gate in front of it. Access shows a
Cloudflare login screen on `api.auralisnatura.com/staff`; only an allowed email that enters
the emailed one-time code gets through — *then* the app's API-key check still applies.

**"Do I log in every time?" — no.** You set the **Session Duration** to up to **1 month**.
After entering the code once on a device, that device stays in for the whole session; you
only re-enter when it expires or you switch device/browser.

### One-time setup

1. **Cloudflare dashboard → Zero Trust** (left sidebar). If prompted for a team name and
   plan, pick the **Free** plan (covers up to 50 users — plenty).
2. **Settings → Authentication → Login methods:** confirm **One-time PIN** is present
   (it's on by default — this is what emails the code). No Google/GitHub login needed.
3. **Access → Applications → Add an application → Self-hosted.**
   - **Application name:** `Auralis Betriebskonsole`
   - **Session Duration:** **1 month** (the "don't ask every time" setting).
   - **Application domain:** `api.auralisnatura.com`, path **`staff`**
     (protects `https://api.auralisnatura.com/staff` and everything under it).
   - Leave the **homepage** and **`/portal`** **out** so clients aren't blocked. (If you
     prefer belt-and-braces on the portal too, add a second app for
     `api.auralisnatura.com` `/portal`; otherwise leave `/portal` to the app's own client
     login — that's the recommended default, since clients can't receive *your* staff
     codes anyway.)
4. **Add a policy:**
   - **Policy name:** `Allowed staff`
   - **Action:** Allow
   - **Include → Emails** → add Desiree's address (and any other trusted staff). Use
     *Emails* for named people, or *Emails ending in* `@auralisnatura.com` for the whole
     domain.
   - Save.
5. **Save the application.** Open `https://api.auralisnatura.com/staff` in a private window:
   you should get the Cloudflare email-code screen → enter the code from your inbox → land
   on the Betriebskonsole → the app's API-key prompt still applies underneath. Two locks,
   as intended.

### Letting the app still reach itself

Cloudflare Access protects **browser** traffic only. Flask, the update launcher and any
local scripts talk to `127.0.0.1:5056`, which never goes through Cloudflare — unaffected.
The `/api/...` calls the staff page makes **from the browser** do go through Cloudflare and
**inherit your logged-in Access session**, so they keep working after you've entered the
code. No extra config.

If you later add a **server-to-server** integration (e.g. Make calling the API without a
browser), create an Access **Service Token** and add it to the policy
(*Include → Service Auth*) so the machine authenticates without a human code — never expose
the raw API by removing Access.

---

## The final DNS picture

After all four parts, `auralisnatura.com`'s DNS (managed at Cloudflare) reads:

| Record | Name | Points at | Proxied | Purpose |
|---|---|---|---|---|
| Pages | `auralisnatura.com` (apex) | Cloudflare Pages project | yes | the website |
| Pages | `www` | Cloudflare Pages project | yes | `www` → website |
| CNAME | `api` | `<UUID>.cfargotunnel.com` (tunnel) | yes | portal / console / API / agent |
| **MX** | `@` | **your mail host — UNCHANGED** | n/a | email delivery |
| **TXT** | SPF / DKIM / DMARC | **UNCHANGED** | n/a | email trust |

The apex + `www` go to **Pages**; `api` goes to the **tunnel**; **mail records are left
exactly as they were**. That separation is the whole design: public site and private app on
the same domain, one control plane, mail untouched.

---

## How the homepage should call the API

The static site (on Pages) and the app (on the tunnel) live on different hostnames, so the
homepage JS should **detect its host and target `api.auralisnatura.com`** for portal/API
calls. A tiny helper keeps it working on the live site, on `www`, and on `*.pages.dev`
previews alike:

```js
// One source of truth for where the backend lives.
const API_BASE =
  location.hostname.endsWith("auralisnatura.com") || location.hostname.endsWith("pages.dev")
    ? "https://api.auralisnatura.com"   // live site, www, and preview builds
    : "";                                // local dev falls back to same-origin :5056

// "Client Login" → the portal served by Flask via the tunnel:
function openPortal() { window.location.href = `${API_BASE}/portal`; }

// Any API call from the page:
async function api(path, opts) {
  return fetch(`${API_BASE}${path}`, { credentials: "include", ...opts });
}
```

Because `API_BASE` resolves to `https://api.auralisnatura.com` on every deployed host, an
iPhone preview at `redesign.auralisnatura.pages.dev` exercises the **real** portal and API —
exactly what you want when reviewing before you merge to `main`.

---

## Quick reference

| Goal | Where | Key setting |
|---|---|---|
| Cheaper renewal + one control plane | Cloudflare Registrar | transfer (≥60 days, auth code) |
| Preview a branch on the phone | Pages → Deployments | auto `*.pages.dev` URL |
| Go live | merge/push to `main` | promotes to `auralisnatura.com` |
| Reach the local app publicly | `cloudflared` tunnel | `api → 127.0.0.1:5056`, run as service |
| No public port on the Mac | the tunnel | tunnel is the only ingress, TLS at Cloudflare |
| Lock down `/staff` | Zero Trust → Access → Applications | path `staff`, Allow policy |
| Don't log in every time | the Access app | Session Duration = 1 month |
| Who may enter `/staff` | the Access policy | Include → Emails / `@auralisnatura.com` |
| Keep email working | Cloudflare DNS | MX + SPF/DKIM/DMARC unchanged |

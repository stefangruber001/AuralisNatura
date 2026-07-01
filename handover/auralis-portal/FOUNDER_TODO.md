# What I need from you — Auralis Portal (concise)

I do all the building. These are the few things only you can do. Nothing here is urgent to
start; I can build most of Phases 1–4 first and slot your inputs in as they arrive.

## Accounts / access (create with team@auralisnatura.com)
1. **Cloudflare** account (free) — for the tunnel, Access, Pages and DNS.
2. **Anthropic API** key (for the Cloud Report Agent) — you'll paste it into the server's
   env as `AURALIS_ANTHROPIC_KEY`; never send it to me in chat.
3. **Gmail App Password** for team@auralisnatura.com (Google Account → Security → App
   passwords) — lets the server drop finished emails into your Drafts. Env
   `AURALIS_SMTP_PASSWORD`.
4. **Cal.com** — one event type "Report review call" (free). Send me its link.
5. **GitHub** — confirm I can use the existing `stefangruber001/auralisnatura` repo (or a
   new private repo) for the portal/console code.

## Decisions (one line each — reply inline)
6. **Domain:** OK to transfer `auralisnatura.com` from Squarespace to **Cloudflare
   Registrar** (cheaper + one control plane + the security tunnel)? (Recommended — yes.)
7. **Report language default** for a client: follow the intake language automatically? (Recommended — yes.)
8. **Client access:** auto-create a portal login when someone **books/pays**, or **you
   invite** each client manually at first? (Recommended — invite-only for the first clients.)
9. **Legal:** add your **NIF + registered address** to `company.json` (for the report/
   invoice footer). And confirm with your **gestor** the IVA treatment of coaching.

## The one hardware note
- The server runs on your **Mac now → Windows later** (exactly like Paramur). It must be
  **on and awake** to receive intakes / run the agent. I'll set the launcher to auto-start
  and stay awake; failover to the other machine is one double-click.

## You do NOT need to
- Write any code, touch the server internals, manage keys in files (they live in env /
  the tunnel), or handle any client data by hand — the console does all of it.

---
When you've done **1–5** and answered **6–9**, tell me and I'll wire the live pieces.
Until then I'll keep building the portal, console, agent and renderer against test data.

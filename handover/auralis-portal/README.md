# Auralis Natura — Portal & Report-Engine Concept Pack

The full concept + documentation to build, for Auralis Natura, the same kind of system
Paramur runs: a **Client-Portal** (login → premium health intake), a **Betriebskonsole**
(Desiree's back-office cockpit), and a **Cloud Report Agent** (Claude drafts the premium
report → she reviews & approves → one click renders the PDF and drops a ready email, with a
review-call booking link, into Gmail drafts).

## Start here
1. **`concept/Auralis-Portal-Concept-Overview.pdf`** — the visual 2-page overview (read first).
2. **`AURALIS_PORTAL_CONCEPT.md`** — the full concept / knowledge base.
3. **`FOUNDER_TODO.md`** — the short list of what only you can do.

## Contents
```
auralis-portal/
├── AURALIS_PORTAL_CONCEPT.md          the master concept & knowledge base
├── FOUNDER_TODO.md                    what I need from you (concise)
├── concept/
│   ├── Auralis-Portal-Concept-Overview.pdf   visual overview
│   └── concept-overview.html                 source
├── config_templates/                  the JSON single-sources-of-truth
│   ├── company.json                   legal + brand master
│   ├── config.json                    runtime (secrets via env)
│   ├── clients.template.json          client portal logins (no health data here)
│   └── report_engine.json             the Cloud Report Agent config
└── guides/
    ├── ARCHITECTURE.md                surfaces, routes, encrypted data model, layout
    ├── SECURITY_GDPR.md               binding: special-category health data
    ├── REPORT_AGENT.md                the Cloud Report Agent design + contract
    ├── DEPLOYMENT_MAC.md              run the server on the Mac (→ Windows later)
    ├── CLOUDFLARE_TUNNEL_AND_DOMAIN.md  Pages, tunnel, Access, Squarespace→Cloudflare
    └── BUILD_PLAN.md                  the phased implementation plan
```

## The model in one line
Reuse ~90 % of the proven Paramur engine (Flask + portal/console auth + Gmail-draft email +
self-updating Mac/Windows launchers + backup/failover + Cloudflare tunnel & Pages); swap the
config + branding to Auralis; build the health-specific pieces (the premium intake, the Cloud
Report Agent, the visual report renderer). Health data is special-category — security &
GDPR are first-class. The human-approval gate is mandatory: the agent drafts, Desiree
approves, then it sends.

*Private — lives under `handover/`, never published by the site's deploy workflow.*

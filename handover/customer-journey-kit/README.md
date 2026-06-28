# Auralis Natura — Customer Journey Kit (macOS)

Everything to run the client journey **from first booking to invoice** on your MacBook.
**Start with the PDF:** `setup-guide/Auralis-Customer-Journey-Setup-macOS.pdf`.

## What's inside
```
customer-journey-kit/
├── setup-guide/
│   ├── Auralis-Customer-Journey-Setup-macOS.pdf   ← READ THIS FIRST (full step-by-step)
│   └── setup-guide.html                            ← source of the PDF
├── templates/
│   ├── report-EN.html / report-DE.html             ← client report → fill in → ⌘P → Save as PDF
│   ├── invoice-EN.html / invoice-DE.html           ← invoice (Stripe backup / manual)
│   └── emails-EN.md / emails-DE.md                 ← every email, ready to paste
├── claude/
│   ├── report-engine-system-prompt.md              ← paste into a Claude Project
│   ├── intake-questions-EN.md / intake-questions-DE.md   ← build the Tally form
└── assets/
    └── seal.png                                    ← brand mark (templates load it from here)
```

## The 60-second version
1. Create the accounts (Cal.com, Stripe, Tally, Make, Claude) — see guide §2.
2. Wire booking + payment (Cal.com + Stripe), intake (Tally), glue (Make), AI (Claude Project).
3. Per client: discovery call → they pay → intake arrives → Claude drafts →
   **you review & approve** → paste into the report template → ⌘P → Save as PDF →
   deliver → invoice + review request fire automatically.

## Three rules that never bend
- Coaching & education, **never** medical care. "Dr." = Dr. rer. nat. (chemistry), not a physician.
- **You approve every report** before it reaches a client.
- Real testimonials only; GDPR-careful with health data (EU hosting, consent, minimisation).

## How to open the templates
Double-click any `.html` → it opens in your browser (use **Chrome**). Click the dashed
boxes to type/paste. ⌘P → **Save as PDF** → turn **ON "Background graphics"**.
Keep files inside this folder so they can load the seal from `assets/`.

#!/usr/bin/env python3
"""Check that auralisnatura.com is allowed to send mail — SPF, DKIM, DMARC.

Run it before and after changing DNS:

    python3 portal/deploy/check_email_dns.py

Why this exists: on 2026-08-10 a booking confirmation forwarded from Gmail to a
yahoo.de address went straight to spam. The domain had NO SPF record, NO DKIM
key and NO DMARC policy — so every receiver had to decide, with no evidence at
all, whether mail claiming to be from team@auralisnatura.com really was. Since
February 2024 Yahoo and Gmail both answer that question "no" by default.

No dependencies: it speaks DNS over UDP to the system resolver, because dnspython
is not installed on the server and dig is not either.
"""
from __future__ import annotations
import re
import random
import socket
import struct
import sys

DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "auralisnatura.com"
DKIM_SELECTORS = ("google", "default", "s1", "selector1")


def _resolver() -> str:
    try:
        for line in open("/etc/resolv.conf"):
            m = re.match(r"\s*nameserver\s+(\S+)", line)
            if m:
                return m.group(1)
    except OSError:
        pass
    return "8.8.8.8"


def _qname(name: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"


def query(name: str, qtype: int) -> list[str]:
    pkt = (struct.pack(">HHHHHH", random.randint(0, 65535), 0x0100, 1, 0, 0, 0)
           + _qname(name) + struct.pack(">HH", qtype, 1))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(8)
    try:
        s.sendto(pkt, (_resolver(), 53))
        data, _ = s.recvfrom(8192)
    finally:
        s.close()
    qd, an = struct.unpack(">HH", data[4:8])
    i = 12
    for _ in range(qd):                       # skip the question section
        while data[i]:
            i += 1 + data[i]
        i += 5
    out = []
    for _ in range(an):
        if data[i] & 0xC0 == 0xC0:            # compressed owner name
            i += 2
        else:
            while data[i]:
                i += 1 + data[i]
            i += 1
        t, _c, _ttl, dl = struct.unpack(">HHIH", data[i:i + 10])
        i += 10
        rd, i = data[i:i + dl], i + dl
        if t == 16:                           # TXT: one or more length-prefixed chunks
            j, parts = 0, []
            while j < len(rd):
                parts.append(rd[j + 1:j + 1 + rd[j]].decode("utf-8", "replace"))
                j += 1 + rd[j]
            out.append("".join(parts))
        elif t == 15:                         # MX: preference + name
            out.append(str(struct.unpack(">H", rd[:2])[0]))
    return out


def main() -> int:
    print(f"Mail authentication for {DOMAIN}\n")
    fails: list[str] = []

    txt = query(DOMAIN, 16)
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    if not spf:
        fails.append("SPF")
        print("  SPF    MISSING  — add a TXT record on the root:")
        print("                    v=spf1 include:_spf.google.com ~all")
    elif "_spf.google.com" not in spf[0]:
        fails.append("SPF")
        print(f"  SPF    present but does NOT authorise Google: {spf[0]}")
    else:
        print(f"  SPF    ok       {spf[0]}")

    found = [s for s in DKIM_SELECTORS
             if any("p=" in t for t in (query(f"{s}._domainkey.{DOMAIN}", 16) or []))]
    if found:
        print(f"  DKIM   ok       selector '{found[0]}' published")
    else:
        fails.append("DKIM")
        print("  DKIM   MISSING  — Google Admin > Apps > Google Workspace > Gmail >")
        print("                    Authenticate email > Generate (2048-bit, selector")
        print("                    'google'), publish the TXT, then Start authentication")

    dmarc = [t for t in query(f"_dmarc.{DOMAIN}", 16) if t.lower().startswith("v=dmarc1")]
    if not dmarc:
        fails.append("DMARC")
        print("  DMARC  MISSING  — add a TXT record on _dmarc:")
        print(f"                    v=DMARC1; p=none; rua=mailto:team@{DOMAIN}")
    else:
        print(f"  DMARC  ok       {dmarc[0]}")

    print()
    if fails:
        print(f"{len(fails)} of 3 missing ({', '.join(fails)}) — mail from this domain is "
              "unauthenticated,\nand Yahoo, Gmail and Outlook are entitled to treat it as spam.")
        return 1
    print("All three present. Send a test to a yahoo.de address and check the headers "
          "show\nspf=pass, dkim=pass and dmarc=pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

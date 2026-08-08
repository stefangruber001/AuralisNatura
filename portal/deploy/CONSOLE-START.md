# Bringing Auralis Natura up on the server — from a browser, one paste

This is the shortest path when there is no Mac. Everything happens in the Hetzner
Cloud Console's root terminal plus two browser approvals you can do on a phone.

**Total: one paste here, one paste into GitHub, two "approve" clicks.**

---

## Before you start

Open <https://console.hetzner.com> → project **canei-erp** → server
**canei-erp-prod** → the **`>_ Console`** button (top right). That gives you a root
shell in the browser; no SSH client and no laptop needed.

If it asks for a root password you do not have, use **Reset root password** on the
same page first — Hetzner shows you a new one.

Pasting into that console is not ⌘V. Use its clipboard / "send text" button, or
paste the block in a few smaller pieces. It is one logical block either way.

---

## The one paste

```bash
set -e
mkdir -p /root/.ssh && chmod 700 /root/.ssh
command -v git >/dev/null || { apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y git; }
[ -f /root/.ssh/auralis_deploy ] || ssh-keygen -q -t ed25519 -N '' -C auralis-deploy -f /root/.ssh/auralis_deploy
echo; echo "==================== COPY THE LINE BELOW ===================="
cat /root/.ssh/auralis_deploy.pub
echo "============================================================="
echo "Add it at: https://github.com/stefangruber001/AuralisNatura/settings/keys/new"
echo "  title: auralis server   ·   Allow write access: LEAVE OFF"
echo
export GIT_SSH_COMMAND='ssh -i /root/.ssh/auralis_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'
echo -n "Waiting for the key to be authorised"
n=0
until git ls-remote git@github.com:stefangruber001/AuralisNatura.git >/dev/null 2>&1; do
  n=$((n+1)); [ "$n" -gt 360 ] && { echo; echo "Gave up after 30 min — re-paste this block when the key is added."; exit 1; }
  echo -n "."; sleep 5
done
echo " authorised."
rm -rf /root/auralis-src
git clone -q --branch claude/webpage-launch-styling-rrtfdl \
  git@github.com:stefangruber001/AuralisNatura.git /root/auralis-src
AURALIS_BRANCH=claude/webpage-launch-styling-rrtfdl \
  bash /root/auralis-src/portal/deploy/bootstrap_server.sh
```

It prints an SSH public key and then **waits**, checking every 5 seconds. Paste
that key into GitHub while it waits; the moment it is accepted the script carries
on by itself. Nothing to re-run.

---

## What it asks you, and what to answer

| Prompt | Answer |
|---|---|
| `Continue with a fresh install?` | `y` — but read the data warning below first |
| `Gmail app password` | paste it, or press Enter to skip and add it later |
| `Run \`claude setup-token\` now?` | `y` — it prints a URL; open it on your phone and approve |
| Cloudflare login | it prints a URL; open it, pick the **auralisnatura.com** zone, approve |

Then it runs the installer unattended and, at the end, prints your **staff console
key once**. Copy it into a password manager there and then. (It is also in
`/etc/auralis/portal.env`, which is root-only, if you lose it.)

---

## The one thing to decide before you type `y`

A fresh install creates a **new encryption key and an empty database**.

The old portal database can only ever be opened by the old `AURALIS_DATA_KEY`,
which lived in `portal/.env` on the Mac and was deliberately never committed to
git. If that Mac is gone, so is anything real that was ever entered through
`/portal` — there is no other copy and no way to recover it.

So: if there is **any** chance of getting files off that Mac (someone still has
it, a Time Machine disk, an iCloud backup), check before you run this. You need
**both** `portal/.env` and `portal/auralis.db` — either one alone is useless.

If the portal only ever held test entries, none of this matters and a fresh start
is the right answer.

If the old key and database turn up **later**, the bootstrap prints the exact
adoption procedure when it finishes. It works, with one caveat: adopting the old
database replaces whatever the server has accumulated since, so back that up first.

---

## When it is done

- console: `https://api.auralisnatura.com/staff`
- portal: `https://api.auralisnatura.com/portal`
- health: `https://api.auralisnatura.com/health` → `{"ok":true,...}`

Check it survives a reboot, because that is the whole point of leaving the Mac
behind:

```bash
reboot
# wait ~30s, reconnect to the console, then:
systemctl is-active auralis-portal cloudflared-auralis
curl -s localhost:5056/health
```

Both should say `active`, and health should return `ok:true` with nobody having
touched anything.

Day-to-day operations, the failure playbook and the rollback are in
[`SERVER-RUNBOOK.md`](SERVER-RUNBOOK.md). If you ever need to take Auralis back
off this host, that is `uninstall_server.sh` — it keeps the data by default and
never touches canei-erp.

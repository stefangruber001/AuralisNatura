# Bringing Auralis Natura up — from an iPhone, start to finish

Roughly 20 minutes. You need: the Hetzner login, the GitHub login, the Cloudflare
login and the Claude login. Nothing else, no computer.

## Why not the Hetzner web console

It works for typing, but you **cannot copy text out of it on iOS** — it is a
picture of a screen, not text. During setup, three things have to be copied
*out*: a deploy key, a Cloudflare login URL and a Claude login URL. All three are
too long to retype. So use a proper SSH app instead; it also gives you a terminal
you can scroll, reconnect to, and reuse forever.

---

## Step 1 — Install Termius

App Store → **Termius**. Free tier is enough. Skip the account prompt if you like
(tap *Continue offline* / *Skip*).

## Step 2 — Get the root password

1. Safari → **console.hetzner.com**
2. Top-left project selector → **canei-erp**
3. **Servers** → **canei-erp-prod**
4. Scroll to the bottom → **Reset root password** → confirm
5. Hetzner shows a password **once**. Long-press → **Copy**, and paste it
   somewhere safe for a minute (Notes).

> This resets only the root password. It does not restart the server and does not
> affect canei-erp's services.

## Step 3 — Connect in Termius

1. Termius → **+** → **New Host**
2. **Address**: `178.105.10.156`
3. **Username**: `root`
4. **Password**: paste from step 2
5. Save → tap the host to connect → accept the fingerprint prompt

You should land on a `root@canei-erp-prod:~#` prompt.

**If it refuses the password** (some images disable root password login), fall
back once to the Hetzner web console — server page → **`>_ Console`** — and there
type this one short line to allow it, then retry Termius:

```
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && systemctl reload ssh && echo OK
```

Set it back to `prohibit-password` once you are finished if you prefer.

## Step 4 — Paste the setup block

In Termius, tap the terminal, then paste (long-press → Paste). Termius also has
**Snippets** if you want to save this for later.

```bash
set -e
mkdir -p /root/.ssh && chmod 700 /root/.ssh
command -v git >/dev/null || { apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y git; }
[ -f /root/.ssh/auralis_deploy ] || ssh-keygen -q -t ed25519 -N '' -C auralis-deploy -f /root/.ssh/auralis_deploy
echo; echo "==================== COPY THE LINE BELOW ===================="
cat /root/.ssh/auralis_deploy.pub
echo "============================================================="
echo "Add it at: https://github.com/stefangruber001/AuralisNatura/settings/keys/new"
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

It prints a key starting `ssh-ed25519 AAAA…` and then waits, printing a dot every
five seconds. **Leave it running.**

## Step 5 — Put that key into GitHub

1. In Termius, long-press the `ssh-ed25519 …` line → select the whole line →
   **Copy**
2. Safari → `github.com/stefangruber001/AuralisNatura/settings/keys/new`
3. **Title**: `auralis server`
4. **Key**: paste
5. **Allow write access**: leave **OFF**
6. **Add key**

Switch back to Termius. Within five seconds the dots stop and it prints
`authorised.` and carries on by itself. Nothing to re-run.

## Step 6 — Answer four questions

| It asks | You answer |
|---|---|
| `Continue with a fresh install?` | `y` *(read §"Before you say yes" below first)* |
| `Gmail app password` | paste it, or just press **Return** to skip — skipping means **no client mail at all** until you add it later |
| `Run \`claude setup-token\` now?` | `y` |
| Cloudflare login | see step 7 |

## Step 7 — The two browser logins

Both print a long URL in the terminal. For each: long-press the URL → **Copy** →
switch to Safari → paste → approve → switch back to Termius.

- **Claude**: approve with your Claude account. It then prints a token — long-press,
  copy it, switch back and paste it when asked. (Input is hidden; that is normal.)
- **Cloudflare**: a page opens asking which zone. Pick **auralisnatura.com** and
  authorise.

## Step 8 — Wait, then save the key it prints

The installer runs for a few minutes with no input needed. At the very end it
prints your **staff console key** — a long random string, shown **once**.

Long-press → Copy → save it in your password manager immediately. (It also lives
in `/etc/auralis/portal.env` on the server, readable only by root, if you lose it.)

## Step 9 — Check it worked

Still in Termius:

```
systemctl is-active auralis-portal cloudflared-auralis
```

Both should print `active`. Then in Safari:

- `https://api.auralisnatura.com/health` → `{"ok":true,…}`
- `https://api.auralisnatura.com/staff` → the console, which asks for the key you saved

Finally, prove it survives a reboot — that is the entire point of leaving the Mac
behind:

```
reboot
```

Termius will disconnect. Wait about 30 seconds, reconnect, and run the
`systemctl is-active` line again. Both `active` with nobody touching anything
means you are done.

---

## Before you say yes

A fresh install creates a **new encryption key and an empty database**. The old
portal data can only ever be opened by the old `AURALIS_DATA_KEY`, which lived in
`portal/.env` on the Mac and was never committed to git.

If there is any chance of getting files off that Mac — someone still has it, a
Time Machine disk, an iCloud backup — check before you type `y`. You need **both**
`portal/.env` and `portal/auralis.db`; either one alone is useless. If the portal
only ever held test entries, ignore this.

## If something goes wrong

Nothing here touches canei-erp, and nothing is irreversible except the data point
above. Paste the error into the chat.

To remove Auralis from the server entirely and start over:

```
bash /root/auralis-src/portal/deploy/uninstall_server.sh
```

Day-to-day operations and the failure playbook: [`SERVER-RUNBOOK.md`](SERVER-RUNBOOK.md).

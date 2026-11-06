# ADR-032 — pulsai-pi is shared as a recipe (official image + our first-boot files), not as a copy of a card

IMPORTERS/CALLERS: read by whoever sets up another Raspberry Pi for PulsAI, or proposes publishing a Pi image;
`infra/raspberry_pi/flash.sh`, `infra/raspberry_pi/common/os/*` (cloud-init `user-data` / `network-config`, `install.sh`).
AFFECTED API: none. DATA SCHEMAS: none -- no image is built or hosted by this decision.

- Status: **accepted** (agent decision, 2026-11-03); revisit on a trigger below
- Deciders: agent (lead architect); a published image, when one exists, ships only on the owner's go
- Asked by the owner, 2026-11-03: _"is that ready to be packed as image and uploaded to s3 cloudflare and share it with
  other users/dev that have raspberry pi and an sd card? ... image can be run from mac dmg or windows exe or linux? ...
  plugged inside a raspberry pi, laptop, pc ...? ... a/b partition just like gwanlo versioning?"_
- Companions: `infra/raspberry_pi/README.md`, `apps/api/tests/unit/infrastructure/test_raspberry_pi_setup.py`.

## Context -- measured on the card and the Pi, 2026-11-03

1. **The card is set up entirely at first boot.** `flash.sh` writes the official Raspberry Pi OS Lite 64-bit (trixie,
   2026-10-06; its download and decompressed SHA-256 are pinned in the script) with Raspberry Pi Imager, hands Imager our
   cloud-init `user-data` and `network-config`, and copies `infra/raspberry_pi/` to the boot partition. On first boot
   cloud-init runs `install.sh` from that copy. Nothing is typed on the Pi; `pulsai-verify-pi` checks the result (10
   checks, all ok on the device, and FAIL with exit 1 when a check is broken on purpose).
2. **A running card is not generic.** It holds this Pi's SSH host keys and machine id, our one login key, cloud-init's
   record that its first boot already ran, its journal, and -- once added -- the Wi-Fi password in NetworkManager's
   store. A byte copy of it hands all of that to whoever flashes it, and two Pis from one copy share an identity.
3. **The image is a Raspberry Pi disk image, ARM64.** It boots a Raspberry Pi that runs 64-bit Raspberry Pi OS (Pi 3,
   4, 400, 5, 500, Zero 2 W), not a laptop or a PC: they have another processor and another boot firmware. An SD card
   holds the whole system, so the card moves between Pis; it does not move to other computers.
4. **The writer runs anywhere.** Raspberry Pi Imager is published for macOS, Windows and Ubuntu, and its command line
   takes the same two cloud-init files. Our `flash.sh` (the disk checks, the pinned hashes, the folder copy) is macOS
   only today; on Linux the same `rpi-imager --cli` line works, on Windows the CLI is NOT verified.
5. **One Pi, one user, today.** No second person or board needs this yet.

## Decision

Share the RECIPE, not an image: the official image (its hash pinned), `user-data` with each person's OWN public key, and
this folder. That gives any Pi the same system in one flash, puts no key or identity in a shared file, and leaves
nothing for us to host or patch -- the operating system comes from Raspberry Pi, signed and current.

## When to build an image instead, and how

Build one when ANY of these holds: a second Pi or a second person needs the setup; first boot needs packages it cannot
install offline (the watcher's Python environment is the likely first); or a flash must work with no network.

- Build it with **pi-gen** (Raspberry Pi's own image builder), a stage on top of Lite, from this folder -- never a copy
  of a used card. No key, host key, machine id or password inside; each person's key goes in at flash time through
  Imager's customisation, and host keys are made on first boot.
- Host it on **Cloudflare R2** beside the checksums and an Imager repository file (the JSON list Imager reads with
  `--repo`), so Imager on macOS / Windows / Linux shows it in its own list. Publishing is the owner's go.
- **A/B partitions** (two root file systems, boot the new one once, keep it only if it comes up -- Raspberry Pi's
  `tryboot`, Pi 4 / 5) are for a fleet updated remotely with no one at the device; the earlier project used them for
  that. One Pi on the desk is re-flashed in five minutes, so A/B waits for a fleet.

## Consequences

- Good: nothing secret is ever in a shared file; no image to host, patch or version; the OS stays upstream's.
- Bad: each new Pi downloads the official image and runs first boot (about five minutes); `flash.sh` is macOS only.
- Pinned by tests: the first boot runs the installer from the card's copy and logs in by key only; the network is
  explicit wired DHCP; the journald drop-in sorts after the OS's own; flash refuses an internal or missing disk; Imager
  gets the decompressed hash; nothing in the folder names an earlier project.

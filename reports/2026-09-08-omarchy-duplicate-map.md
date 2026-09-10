# omacom/omarchy — duplicate map for verification

**Read the two boxes below before the map. Nothing here has been posted anywhere,
and nothing goes upstream from this document.**

---

## What this is

600 clusters covering **756 tickets** that an automated pass over the open queue
says are redundant with another ticket. Each line is one claim: keep this one, these others
say the same thing. They are banded by how much the claim is worth checking first.

It is in two parts, because the original 756 counted two different things:

| Part | Clusters | Tickets | The question |
|---|---:|---:|---|
| **One — duplicated work** | 381 | 537 | Did two people do the same job? |
| **Two — a ticket and its own fix** | 219 | 219 | Does this patch close this ticket? |

Bands inside part one:

| Band | Clusters | Tickets | What it means |
|---|---:|---:|---|
| **Near certain** | 12 | 14 | Somebody already wrote the link down: a collaborator saying duplicate on the thread, or one person submitting the same text twice. |
| **High confidence** | 98 | 149 | Two patches deleting the same source lines, two patches declaring the same close target, or near-identical titles. |
| **Some confidence** | 125 | 191 | The two share a rare literal — an error string, a path, a symbol — but nothing more. |
| **Uncertain** | 75 | 97 | Grouped by wording, or by nothing much. |
| **We think these are NOT duplicates** | 71 | 86 | Grouped by the first pass, and the evidence now says no. |

**How to read a line.** `C042` `R` **7022** + 9323 9925 — cluster id, kind, the ticket to keep,
then the tickets claimed redundant with it. Then the surface, then the one thing tying them.
A `⏱` means at least one ticket in that cluster has already been merged or closed since the
snapshot, so check its state before anything else.

Kinds: **`R`** two reports of one bug &middot; **`P`** two patches doing one job &middot;
**`F`** a ticket and the patch that declares it closes it. Only `R` and `P` are duplicated
effort; `F` is a fix landing, and it leaves the queue for a different reason.

## Disclaimer on the methods — read this before trusting a band

**The grouping is rough and it is known to be rough.** Items were grouped by tf-idf cosine
over title and body plus GitHub's link metadata, then banded by a second pass over patch
hunks, declared close references, thread comments and rare shared literals. Neither pass
read anything for meaning.

**Measured, by reading 83 randomly sampled pairs in full:**

| Claim | How many | How often it held |
|---|---:|---|
| A ticket its own patch declares it closes | 129 | 42 of 42 |
| A patch duplicating another patch | 329 | 13 of 30 — 43% (95% CI 27–61%) |
| A report duplicating another report | 208 | 15 of 30 — 50% (95% CI 33–67%) |
| A ticket a patch *might* close, undeclared | 90 | 6 of 18 — 33% |

Four things that will otherwise waste your time:

1. **Same surface is not the same work.** About nine in ten pairs really do share a file, a
   function or a service. Only about half are redundant. The rest are two faults in one
   place, or one job deliberately split across two patches.
2. **A shared rare literal proves a shared subsystem, not a shared defect.** It is the
   evidence behind most of the `SOME` band and it is the weakest thing in this file.
3. **The queue moves.** 113 of the 1,072 tickets here settled in the 15 hours after the
   snapshot was taken. Re-fetch state before you judge anything.
4. **This is one automated reading plus one human-style sampling pass.** It is a triage
   prior. It is not a verdict, and no line here is evidence of anything on its own.

Full method, the 83 judgements and the falsification tests: `reports/2026-09-08-omarchy-duplicate-likelihood.html`.

## What you are being asked to do

For each cluster, **try to disprove it first.** Changing a non-problem is worse than leaving
it. Work `DISPUTED` and `CERTAIN` first — they are the two bands where the answer is cheapest
to establish and most consequential to get wrong.

Per kind, the check and the thing that would invalidate it:

| Kind | Confirm it by | It is INVALID if |
|---|---|---|
| `R` two reports | Both name the same defect: same command, same file, same wrong behaviour. | Either names a cause, a device, a code path or a config the other rules out — or one says in its own text that it is not the other. |
| `P` two patches | Both change the same code toward the same end; merging one makes the other redundant or conflicting. | One is contained in the other as a stack or a follow-up, or they change different things in one file, or they are the same author's two halves of one job. |
| `F` ticket + fix | The patch's diff addresses everything the ticket reports. | The ticket carries findings the patch does not touch, or the patch's declared target is a different ticket. |

**Hard constraints:**

- **Read-only.** Do not comment, close, label, edit, reopen or react to anything on GitHub.
- **Nothing upstream.** No output of this work is posted to the repository, on any band, at
  any confidence, for any reason. Hand the result back here.
- Report each cluster as `confirmed` / `refuted` / `unsure`, with the one fact that decided
  it. Where you refute, say what the two tickets actually are.
- A human reviews the confirmed list afterward. Write for that reader.

---

# PART ONE — duplicated work (381 clusters, 537 tickets)

Somebody wrote the same report, or the same patch, twice. This is the part worth an
agent's time.

## Near certain — 12 clusters, 14 tickets

Somebody already wrote the link down: a collaborator saying duplicate on the thread, or one person submitting the same text twice. Two cautions. Most of those comments are @omarchybot, a bot holding collaborator standing, so it is a machine's judgement wearing a person's badge. And *same author filed it twice* now requires the two bodies to be 70% the same text — without that gate it caught twelve authors filing a **series** of related tickets and called each one a copy of the last.

- `C130` `R` **10303** + 10304 10305 — Lock screen crash: MultiEffect blur with high GPU load causes QM — same author filed it twice
- `C131` `R` **10512** + 10514 10516 — Quickshell module not found - missing quickshell-coreplugin — same author filed it twice
- `C132` `R` **6977** + 7060 — `omarchy debug` and four other commands are unreachable inside t — @omarchybot already called it a duplicate on the thread
- `C133` `R` **7217** + 7640 — screenrecord: NVENC fallback doesn't trigger on API version mism — @omarchybot already called it a duplicate on the thread
- `C134` `R` **7233** + 7378 — Emoji not sent to clipboard — @axelfontaine already called it a duplicate on the thread
- `C135` `R` **7679** + 8813 — Low battery notification can fire on boot after resuming from a  — @omarchybot already called it a duplicate on the thread
- `C136` `R` **7721** + 8502 — omarchy-hyprland-window-pop resizes unconditionally after a floa — both quote `hypr_dispatch`
- `C137` `R` **8239** + 9953 — Omarchy 'omarchy update' — both quote `env_reset`, `/usr/bin/omarchy-update-dev`
- `C138` `R` **8248** + 8363 — OpenSSH daemon bound to all interfaces — both quote `sshd_config`
- `C139` `R` **8271** + 8274 — Installer erases T1/T2 firmware on Apple hardware, permanently d — same author filed it twice
- `C140` `R` **8290** + 8789 — [Quattro] Screen lock moves the default audio sink to the intern — both quote `default-sink`
- `C141` `R` **9517** + 9518 — Bluetooth panel cannot re-enable an rfkill-blocked adapter — @omarchybot already called it a duplicate on the thread

## High confidence — 98 clusters, 149 tickets

Two patches deleting the same source lines, two patches declaring the same close target, or near-identical titles. Strong, but a patch can overlap another and still be a different change — this is the band where a stack or a superset hides.

- `C142` `P` **10623** + 7023 9074 9102 9369 9455 9970 10099 10635 — omarchy toggle bar on/off has inverted semantics (hides bar on ' — 8 identical deleted lines and 7 identical added lines in bin/omarchy-toggle-bar
- `C143` `P` **6477** + 6485 6902 7200 7394 8280 8649 9840 — Add Kimi Code and Grok Build usage collectors — 3 identical deleted lines and 112 identical added lines in bin/omarchy-agent-usage-grok
- `C144` `P` **5212** + 6863 7935 8336 9782 — Add face unlock via howdy — 5 identical deleted lines and 145 identical added lines in shell/plugins/lock/LockView.qml
- `C145` `P` **6604** + 6827 6969 7087 8450 — Add Cursor agent usage collector — 10 identical deleted lines and 450 identical added lines in bin/omarchy-agent-usage-cursor
- `C146` `P` **6845** + 7138 7186 9106 10392 — Battery percent in the top bar shows only BAT0 — 15 identical deleted lines and 7 identical added lines in bin/omarchy-battery-status
- `C147` `P` **8370** + 7995 8374 8429 9033 — [Security] omarchy debug and omarchy upload log stage root-colle — 6 identical deleted lines and 4 identical added lines in bin/omarchy-debug
- `C148` `P` **7895** + 7915 10196 10502 — Power panel shows UPower's hwdb charge limit (75-80%) instead of — both patches declare they close #7803
- `C149` `P` **8005** + 7463 8974 9036 — grammar typo in Manual - Navigation — 1 identical deleted line and 1 identical added line in manual/04-navigation.md
- `C150` `P` **8894** + 8824 8992 9511 — omarchy update -y hangs on the orphaned-packages prompt — both patches declare they close #8780
- `C151` `P` **10388** + 8876 10212 10562 — omarchy-menu-keybindings hangs forever when a user Lua config it — 1 identical deleted line and 10 identical added lines in bin/omarchy-menu-keybindings
- `C152` `P` **4928** + 3690 7700 — Bug regarding "omarchy-launch-or-focus" and ghostty — both patches declare they close #3669 · 7700 reached only through another ticket, not directly
- `C153` `P` **6958** + 8597 9971 — omarchy font set resets Foot font size to 9, ignoring omarchy di — 1 identical deleted line in bin/omarchy-font-set
- `C154` `P` **7905** + 7491 9991 — Dictation indicator opens the config instead of toggling dictati — both quote `indicator-contract-test`
- `C155` `P` **8145** + 8808 10664 — Clamshell watcher ignores desc: rules for the internal panel and — both quote `single-line` · 10664 reached only through another ticket, not directly
- `C156` `P` **8341** + 6449 8236 — Bitwarden Chrome Extension popup locked to 875x600 since 2026.5. — both patches declare they close #6075
- `C157` `P` **8452** + 6572 8955 — [Quattro] D-Bus idle inhibits are silently dropped since hypridl — both patches declare they close #6475
- `C158` `P` **8590** + 9164 9980 — Omarchy 'omarchy update' — both patches declare they close #8369
- `C159` `P` **9041** + 9107 9215 — Default Enter keybindings never match on keyboards that emit KP_ — both patches declare they close #9030
- `C160` `P` **9131** + 7880 9965 — omarchy-upgrade-to-quattro enables bt-agent.service but orphans  — both touch default/systemd/user/bt-agent.service
- `C161` `P` **9275** + 9270 9287 — Cloned theme without [colors.selection] gets selection == foregr — both patches declare they close #9266
- `C162` `P` **9328** + 8700 8945 — Obsidian user-flags.conf default has single-dash typo (-disable- — both patches declare they close #8538
- `C163` `P` **9605** + 9564 10046 — windows-vm: chmod 0700 preserves directory setgid bit, causing l — both patches declare they close #9374
- `C164` `P` **9651** + 7334 9667 — Steam idle-inhibit rule matches the client but not steam_app gam — both patches declare they close #9636
- `C165` `P` **5545** + 6532 — Ctrl+C during sudo password prompt in pkg-install/pkg-aur-instal — both patches declare they close #4869
- `C166` `P` **5548** + 6531 — Browser managed policy directories are world-writable — both patches declare they close #5547
- `C167` `P` **6104** + 4836 — Add native WezTerm support — 16 identical added lines in bin/omarchy-restart-terminal
- `C168` `P` **6464** + 7765 — Agents panel: Separate OpenCode usage into its own collector ins — both touch shell/plugins/agents/README.md
- `C169` `P` **6533** + 5424 — Keyboard backlight settings inconsistently jump in steps of 9 or — both patches declare they close #5414
- `C170` `P` **6679** + 6705 ⏱ — Add QR code capture — 25 identical added lines in bin/omarchy-capture-qr
- `C171` `P` **6812** + 6521 — Map Omarchy light/dark to Grok built-in themes — 2 identical deleted lines and 14 identical added lines in bin/omarchy-theme-set-grok
- `C172` `P` **6896** + 9762 — SDDM greeter always uses US keyboard layout, ignoring the system — both patches declare they close #6880
- `C173` `P` **6924** + 7171 — Prevent togglesplit error in scrolling layout — 1 identical deleted line and 2 identical added lines in default/hypr/bindings/tiling.lua
- `C174` `P` **7039** + 9172 — launch webapp fails when default browser is Firefox (no Chromium — both patches declare they close #7034
- `C175` `P` **7042** + 7513 — Add Ctrl-N and Ctrl-P menu navigation — 2 identical deleted lines in shell/plugins/menu/Menu.qml
- `C176` `P` **7065** + 7048 — Bluetooth widget disappears from shell when turned off — 7 identical deleted lines and 15 identical added lines in shell/plugins/panels/bluetooth/Panel.qml
- `C177` `P` **7140** + 9516 — Install CS8409 speaker driver on 2016-2017 MacBook Pros — 2 identical deleted lines and 85 identical added lines in bin/omarchy-hw-apple-cs8409
- `C178` `P` **7177** + 10267 — Mark the T2 Mac internal trackpad as internal — 26 identical added lines in install/hardware/all.sh
- `C179` `P` **7359** + 9979 — `omarchy install service sunshine` fails: "Unit sunshine.service — 1 identical deleted line and 5 identical added lines in bin/omarchy-install-service-sunshine
- `C180` `P` **7444** + 7457 — Zen installer writes policies to unused /opt/zen-browser path — 1 identical deleted line and 3 identical added lines in bin/omarchy-install-browser
- `C181` `P` **7519** + 6710 — [Quattro] Display panel scale is per-monitor at runtime but pers — 18 identical deleted lines and 6 identical added lines in bin/omarchy-hyprland-monitor-scaling
- `C182` `P` **7798** + 9945 — Support for Github Copilot with the omarchy quickshell agents pl — 1 identical deleted line and 53 identical added lines in bin/omarchy-agent-usage-copilot
- `C183` `P` **8086** + 8595 — Changing `idle.screensaver` / `idle.lock` in `shell.json` silent — 1 identical deleted line and 6 identical added lines in shell/plugins/services/idle/Service.qml
- `C184` `P` **8146** + 8752 — Cloning a "kind: bar" plugin (omarchy plugin clone omarchy.bar)  — 2 identical deleted lines and 1 identical added line in shell/shell.qml
- `C185` `P` **8147** + 8141 — omarchy-install-and-launch: "Press any key to close" races the a — both patches declare they close #8122
- `C186` `P` **8171** + 9620 — Quote launcher arguments so they survive the launch-or-focus re- — 3 identical deleted lines and 1 identical added line in bin/omarchy-launch-or-focus-tui
- `C187` `P` **8258** + 8043 — omarchy-theme-set-browser hangs when brave-origin is running but — 1 identical deleted line and 1 identical added line in bin/omarchy-theme-set-browser
- `C188` `P` **8325** + 7975 — Make the tray the bar's organizer: drag any widget in, around, a — 18 identical deleted lines and 4 identical added lines in manual/42-common-tweaks.md
- `C189` `P` **8383** + 8499 — Dropbox widget hides the tray icon without replacing its menu: n — 2 identical deleted lines and 3 identical added lines in shell/plugins/panels/dropbox/Service.qml
- `C190` `P` **8408** + 8584 — Theme GTK4 apps with Omarchy colors — 1 identical deleted line and 29 identical added lines in bin/omarchy-theme-set
- `C191` `P` **8486** + 9524 — Fingerprint setup misses Broadcom BCM58200 ControlVault 3 (vendo — 1 identical added line in bin/omarchy-hw-fingerprint
- `C192` `P` **8493** + 9981 — omarchy-hook runs every hook via bash, ignoring the shebang — si — 2 identical deleted lines and 3 identical added lines in bin/omarchy-hook
- `C193` `P` **8498** + 9239 — User password update in menu leaves old root password active — 1 identical deleted line and 10 identical added lines in bin/omarchy-user-password
- `C194` `P` **8506** + 8885 — omarchy-hyprland-window-pop resizes unconditionally after a floa — both patches declare they close #8502
- `C195` `P` **8507** + 8884 — omarchy-menu-images runs awk against index.tsv once per thumbnai — both patches declare they close #8503
- `C196` `P` **8512** + 8525 — No way to share the clipboard as a QR code from Trigger > Share — both patches declare they close #8509
- `C197` `P` **8529** + 8035 — Feature: manage NetworkManager VPN profiles from the built-in ne — 31 identical added lines in bin/omarchy-network-vpn
- `C198` `P` **8588** + 9655 ⏱ — system-sleep hooks installed by omarchy-hibernation-setup and om — 2 identical deleted lines in bin/omarchy-hibernation-setup
- `C199` `P` **8792** + 9306 — screenrecord --with-webcam: overlay locks to YUYV @5fps instead  — both patches declare they close #7300
- `C200` `P` **8881** + 8872 — omarchy-notification-wait treats its timeout argument as an atte — both patches declare they close #8870
- `C201` `P` **8882** + 8524 — omarchy-brightness-display: Brightness trapped at 0% on displays — both patches declare they close #8523
- `C202` `P` **8895** + 8838 — Low battery notification can fire on boot after resuming from a  — both patches declare they close #8813
- `C203` `P` **8975** + 9725 — Add support for detached bar with margin and radius properties — 7 identical deleted lines and 34 identical added lines in default/themed/shell.toml.tpl
- `C204` `P` **9133** + 10468 — omarchy-menu-keybindings: code: binds always displayed with US s — both patches declare they close #8999
- `C205` `P` **9150** + 10692 — Harden tui launcher install and removal — 11 identical deleted lines and 46 identical added lines in bin/omarchy-tui-install
- `C206` `P` **9170** + 7578 — No way to disable the idle lock while keeping the screensaver —  — 1 identical deleted line and 1 identical added line in shell/plugins/services/idle/IdleModel.js
- `C207` `P` **9244** + 9329 — Voxtype pause_media silently fails: playerctl not installed by o — 1 identical deleted line and 1 identical added line in bin/omarchy-voxtype-install
- `C208` `P` **9299** + 9358 — Offer Korean as an install-time keyboard choice — 2 identical added lines in bin/omarchy-provision-owner
- `C209` `P` **9343** + 7130 — Cannot run Migration (1786643346) because an "browser window is  — both patches declare they close #7078
- `C210` `P` **9398** + 9402 — omarchy-drive-password: "No encrypted drives available" due to u — 3 identical deleted lines and 1 identical added line in bin/omarchy-drive-password
- `C211` `P` **9563** + 9562 — XDG_DESKTOP_DIR="$HOME" makes apps scatter .desktop shortcuts in — both patches declare they close #9556
- `C212` `P` **9618** + 10733 ⏱ — Restrict third-party plugin access to authentication services — 47 identical deleted lines and 1328 identical added lines in agents/skills/shell-dev.md
- `C213` `P` **9653** + 7837 — Bluetooth panel shows the device's raw hardware Name instead of  — both patches declare they close #9603
- `C214` `P` **9656** + 9673 — Sublime Text install does not expose sublime_text on PATH, so De — both patches declare they close #9643
- `C215` `P` **9694** + 9777 — Add Dim and Kimi Code to the agent roster and Install > AI — 2 identical deleted lines and 4 identical added lines in bin/omarchy-agent
- `C216` `P` **9757** + 9135 — Menu blocks on-screen keyboard input: Exclusive keyboard focus r — near-identical titles
- `C217` `P` **9978** + 10024 — 4.0.x: user ~/.config/hypr/envs.lua is never loaded — user env o — both patches declare they close #9902
- `C218` `P` **10160** + 7370 — omarchy-font-set: terminal restart notifications never fire — -g — both patches declare they close #7183
- `C219` `P` **10293** + 10301 — Support selecting installed Linux kernel in direct boot setup — 4 identical deleted lines and 5 identical added lines in bin/omarchy-setup-direct-boot
- `C220` `P` **10294** + 8537 — Add Alfred/Raycast-style live query plugins to the menu — 1 identical deleted line and 2 identical added lines in shell/plugins/menu/Menu.qml
- `C221` `P` **10390** + 10424 — Bar: custom command module with empty "text" renders the raw JSO — both patches declare they close #10319
- `C222` `P` **10430** + 8164 — Hyprsunset is reset when/after screen locks — 3 identical deleted lines and 1 identical added line in bin/omarchy-toggle-nightlight
- `C223` `P` **10476** + 9939 — Calendar grid duplicates September 5 and shifts dates in month v — both patches declare they close #9635
- `C224` `P` **10513** + 10569 — omarchy-chromium-ytdlp-host does not unset LD_PRELOAD from Chrom — both patches declare they close #10469
- `C225` `P` **10520** + 9521 — Cycle a theme's backgrounds with up and down in the theme picker — 4 identical deleted lines and 4 identical added lines in manual/06-themes.md
- `C226` `P` **10535** + 10536 — Clipboard manager cannot paste images into terminal apps: Shift+ — both patches declare they close #10526
- `C227` `P` **10570** + 10585 — Monitor scaling changes leave GDK_SCALE stale in the app-launch  — both patches declare they close #10555
- `C228` `P` **10577** + 10539 — Stock XF86TouchpadToggle binding never fires (Hyprland resolve_b — both patches declare they close #10449
- `C229` `P` **10588** + 9483 — LIBVA_DRIVER_NAME=nvidia is set even when the NVIDIA GPU drives  — 1 identical deleted line and 6 identical added lines in bin/omarchy-hw-nvidia-drives-display
- `C230` `P` **10739** + 7766 — Add FIGlet screensaver branding picker — 3 identical deleted lines and 2 identical added lines in bin/omarchy-branding-screensaver
- `C231` `R` **7022** + 9323 9925 10156 10621 — omarchy toggle bar on/off has inverted semantics (hides bar on ' — near-identical titles
- `C232` `R` **6957** + 9415 9954 — omarchy font set resets Foot font size to 9, ignoring omarchy di — near-identical titles
- `C233` `R` **6987** + 8445 10000 — Agents bar widget: Claude collector shows 'Waiting for auth' wit — both quote `fireworks`
- `C234` `R` **7371** + 8960 — SUPER+C/V/X universal clipboard shortcuts fail with "send_key_st — near-identical titles
- `C235` `R` **7752** + 9048 — sunshine package built without CUDA support — NVENC silently fal — near-identical titles
- `C236` `R` **8007** + 8334 — Cloning a "kind: bar" plugin (omarchy plugin clone omarchy.bar)  — near-identical titles
- `C237` `R` **8158** + 10666 — omarchy-theme-set-browser hangs when brave-origin is running but — near-identical titles
- `C238` `R` **8790** + 9592 — Screensaver only dismisses on keyboard input, not mouse movement — near-identical titles
- `C239` `R` **9374** + 10608 — windows-vm: chmod 0700 preserves directory setgid bit, causing l — both quote `shared_fd`, `prepare_caller_mounts`

## Some confidence — 125 clusters, 191 tickets

The two share a rare literal — an error string, a path, a symbol — but nothing more. Measured: this proves a shared subsystem, not a shared defect. Expect roughly half of this band to survive.

- `C240` `P` **6464** + 6526 6779 7082 7157 7687 8065 8823 8873 — Agents panel: Separate OpenCode usage into its own collector ins — 72 identical added lines in bin/omarchy-agent-usage-opencode-go · 8873 reached only through another ticket, not directly
- `C241` `P` **9130** + 6419 7285 7375 10247 — SUPER+C/V/X universal clipboard shortcuts fail with "send_key_st — 3 identical deleted lines in default/hypr/bindings/clipboard.lua
- `C242` `P` **4928** + 9614 9927 9987 — Bug regarding "omarchy-launch-or-focus" and ghostty — 1 identical deleted line in bin/omarchy-launch-or-focus
- `C243` `P` **7449** + 6892 7351 8573 — Emoji not sent to clipboard — 17 identical deleted lines in bin/omarchy-menu-emoji-insert
- `C244` `P` **9131** + 6877 8572 8929 — omarchy-upgrade-to-quattro enables bt-agent.service but orphans  — 5 identical deleted lines in default/systemd/user/bt-agent.service
- `C245` `P` **9988** + 8548 9165 9704 — SUPER+J runs dwindle-only togglesplit on scrolling workspaces — 1 identical deleted line in default/hypr/bindings/tiling.lua
- `C246` `P` **7333** + 7180 7589 — Work around Apple BCM4350 suspend failures — 133 identical added lines in bin/omarchy-hw-brcmfmac-suspend
- `C247` `P` **7465** + 9119 10034 — Obsidian shortcut never focuses a running window: ^obsidian$ no  — 1 identical deleted line in default/hypr/bindings/applications.lua
- `C248` `P` **7579** + 9140 9900 — Keep scratchpad separate from Quake console — 1 identical deleted line in default/hypr/qconsole.lua
- `C249` `P` **7708** + 8277 8278 — Weather unit mismatch in Omarchy 4 — 1 identical added line in test/shell.d/weather-test.sh
- `C250` `P` **8145** + 7146 7408 — Clamshell watcher ignores desc: rules for the internal panel and — both quote `multi-line`, `nwg-displays` · 7146 reached only through another ticket, not directly
- `C251` `P` **8175** + 9282 9568 — Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev  — both quote `xkbcli compile-compose`, `compile-compose`, `/usr/share/omarchy/default/xcompose`
- `C252` `P` **8205** + 8371 9910 — Read actual gmux display brightness — both quote `actual_brightness`, `gmux_backlight`
- `C253` `P` **8258** + 9423 10645 — omarchy-theme-set-browser hangs when brave-origin is running but — both touch bin/omarchy-theme-set-browser
- `C254` `P` **8424** + 7992 10413 — [Security] omarchy-refresh-config will write outside ~/.config g — 2 identical deleted lines in bin/omarchy-refresh-config
- `C255` `P` **8590** + 8771 9966 — Omarchy 'omarchy update' — 6 identical added lines in bin/omarchy-update-dev
- `C256` `P` **8739** + 9219 10389 — Cloning the bar plugin blanks the bar (broken Loader.Error fallb — 1 identical deleted line in shell/shell.qml
- `C257` `P` **8980** + 9010 10296 — fix(shell): keep notification dismiss button visible — 3 identical deleted lines in shell/plugins/notifications/components/NotificationCard.qml
- `C258` `P` **5212** + 7040 — Add face unlock via howdy — both quote `pamcontext`, `/etc/pam.d/omarchy-lock-face`
- `C259` `P` **6477** + 7261 — Add Kimi Code and Grok Build usage collectors — both quote `kimi-code`
- `C260` `P` **6845** + 10384 — Battery percent in the top bar shows only BAT0 — 14 identical deleted lines in bin/omarchy-battery-status
- `C261` `P` **6897** + 5431 — feat(hardware): sync ThinkBook mute LEDs with WirePlumber state — both quote `platform::micmute`, `platform::mute`, `wpctl`
- `C262` `P` **6958** + 8609 — omarchy font set resets Foot font size to 9, ignoring omarchy di — both quote `/omarchy-font-set`, `bin/omarchy-font-set`
- `C263` `P` **7037** + 6641 — Quattro: Route app audio to individual outputs — 15 identical added lines in shell/plugins/panels/audio/Model.js
- `C264` `P` **7039** + 9206 — launch webapp fails when default browser is Firefox (no Chromium — 2 identical deleted lines in bin/omarchy-launch-webapp
- `C265` `P` **7140** + 8285 — Install CS8409 speaker driver on 2016-2017 MacBook Pros — 2 identical added lines in install/hardware/all.sh
- `C266` `P` **7147** + 7273 — feat: allow output volume over-amplification to 150% — 5 identical added lines in bin/omarchy-audio-output-volume
- `C267` `P` **7151** + 7231 — Clicking workspaces in BarWidget is sluggish vs keybinds — both quote `util.execdetached`, `/etc/profile`
- `C268` `P` **7239** + 9290 — `omarchy debug` and four other commands are unreachable inside t — both quote `omarchy-nvim`, `omarchy-emacs`, `omarchy-fish`
- `C269` `P` **7336** + 8532 — Re-detect Apple display when cached hiddev node stops responding — both quote `omarchy-brightness-display-apple`, `asdcontrol`
- `C270` `P` **7417** + 8351 — Add NetBird mesh VPN integration — 689 identical added lines in bin/omarchy-install-service-netbird
- `C271` `P` **7469** + 8539 ⏱ — Add Hermes as a desktop app and a coding agent — 253 identical added lines in bin/omarchy-install-hermes-cli
- `C272` `P` **7497** + 8300 — Stop monitor scaling from persisting a scale the reload will und — 11 identical added lines in bin/omarchy-hyprland-monitor-scaling
- `C273` `P` **7780** + 8048 — [Quattro] Screensaver only exits on a keypress inside its own te — both quote `closewindow`, `handlescreensaverwindowclosed`, `onisidlechanged`
- `C274` `P` **7798** + 8972 — Support for Github Copilot with the omarchy quickshell agents pl — 56 identical added lines in bin/omarchy-agent-usage-copilot
- `C275` `P` **7907** + 8606 — Qt.formatDate/Qt.formatDateTime ignore system locale for day/mon — 4 identical deleted lines in shell/plugins/panels/clock/BarWidget.qml
- `C276` `P` **7945** + 6019 — nautilus takes 25s to start — both quote `org.freedesktop.impl.portal.filechooser`, `xdg-desktop-portal-gnome`, `org.gnome.nautilus`
- `C277` `P` **7998** + 8781 — Timestamp the limine and pacman refresh backups — both quote `omarchy-refresh-pacman`, `pre-refresh-pacman`, `/etc/pacman.conf`
- `C278` `P` **8005** + 8995 — grammar typo in Manual - Navigation — 1 identical deleted line in manual/04-navigation.md
- `C279` `P` **8067** + 8174 ⏱ — Guard plugin-add against git transport-helper URLs (match theme- — 3 identical added lines in bin/omarchy-plugin-add
- `C280` `P` **8069** + 8852 — SDDM authenticates empty username ("") after interrupted/resumed — both quote `usermodel`, `state.conf`
- `C281` `P` **8117** + 8191 — Add US International keyboard layout — 1 identical added line in install/provisioning/setup-form.sh
- `C282` `P` **8136** + 9104 — omarchy install service sunshine fails to enable unit on fresh i — 1 identical deleted line in bin/omarchy-install-service-sunshine
- `C283` `P` **8171** + 9490 — Quote launcher arguments so they survive the launch-or-focus re- — 2 identical deleted lines in bin/omarchy-launch-or-focus-tui
- `C284` `P` **8370** + 8430 — [Security] omarchy debug and omarchy upload log stage root-colle — both quote `/tmp/omarchy-battlenet-installer.log`, `omarchy-battlenet-installer`
- `C285` `P` **8383** + 9191 — Dropbox widget hides the tray icon without replacing its menu: n — 1 identical deleted line in shell/plugins/panels/dropbox/status.py
- `C286` `P` **8406** + 10552 — Keep system binaries ahead of the mise shims in the uwsm session — both quote `ssh-command-path`, `/config/ssh-command-path.sh`, `install/config/ssh-command-path.sh`
- `C287` `P` **8496** + 8473 ⏱ — [Security] omarchy-webapp-install writes javascript:/file: URLs  — both quote `percent-encoded`, `user-agent`, `//example.com/`
- `C288` `P` **8497** + 10040 — Agents bar widget: Claude collector shows 'Waiting for auth' wit — 1 identical deleted line in shell/plugins/agents/Panel.qml
- `C289` `P` **8506** + 7910 — omarchy-hyprland-window-pop resizes unconditionally after a floa — 1 identical deleted line in bin/omarchy-hyprland-window-pop
- `C290` `P` **8683** + 8741 — Show IPv6 address and gateway in the network panel — 2 identical added lines in shell/plugins/panels/network/Panel.qml
- `C291` `P` **8820** + 5317 — [Quattro] Screen lock moves the default audio sink to the intern — both quote `single-sink`, `hdmi-stereo`
- `C292` `P` **8895** + 8284 — Low battery notification can fire on boot after resuming from a  — both touch shell/plugins/services/battery/Service.qml
- `C293` `P` **9039** + 8034 — tsl and hsl silently do nothing on a non-numeric pane count inst — both quote `bash test/shell.d/herdr-functions-test.sh`, `/shell.d/herdr-functions-test.sh`, `herdr-functions-test`
- `C294` `P` **9161** + 7599 — Web app installer saves non-PNG icons with a .png extension — 11 identical added lines in bin/omarchy-webapp-install
- `C295` `P` **9227** + 9795 — Require interactive confirmation for AUR installs and updates — 4 identical deleted lines in bin/omarchy-install-editor-emacs
- `C296` `P` **9637** + 10462 — Lid-open binding does not restore display brightness after suspe — 2 identical deleted lines in default/hypr/bindings/utilities.lua
- `C297` `P` **9651** + 10447 — Steam idle-inhibit rule matches the client but not steam_app gam — both touch default/hypr/apps/steam.lua
- `C298` `P` **9754** + 7951 — Stale ACPI lid state turns external-monitor hotplug into clamshe — 8 identical added lines in bin/omarchy-hw-laptop-closed
- `C299` `P` **10185** + 5686 — Brave has no speechSynthesis voices on a default Omarchy install — 2 identical added lines in install/omarchy-base.packages
- `C300` `P` **10396** + 9844 — sddm.sh strips pam_gnome_keyring.so auth from /etc/pam.d/sddm bu — 3 identical added lines in install/login/sddm.sh
- `C301` `P` **10408** + 10414 — Screensaver interrupts video playback: the Inhibit portal routes — both quote `portals.conf`, `org.gnome.sessionmanager`, `/xdg-desktop-portal/hyprland-portals.conf`
- `C302` `P` **10430** + 9554 — Hyprsunset is reset when/after screen locks — 2 identical added lines in bin/omarchy-toggle-nightlight
- `C303` `P` **10530** + 8018 — Numlock problem after boot and suspend — 2 identical added lines in shell/plugins/polkit/PolkitAgent.qml
- `C304` `P` **10567** + 8932 — Tile the Battle.net client instead of floating it — 2 identical added lines in default/hypr/apps/battlenet.lua
- `C305` `R` **7084** + 7326 7498 8103 8123 8335 — Clamshell watcher ignores desc: rules for the internal panel and — both quote `/omarchy-hyprland-monitor-clamshell`, ` position = \`, ` mode = \`
- `C306` `R` **7025** + 8819 9052 10214 10737 — omarchy-menu-keybindings hangs forever when a user Lua config it — near-identical titles
- `C307` `R` **7556** + 8220 8993 9146 9726 — SUPER+J runs dwindle-only togglesplit on scrolling workspaces — both quote `/usr/share/omarchy/default/hypr/bindings/tiling.lua`
- `C308` `R` **9374** + 9540 9567 10441 10486 — windows-vm: chmod 0700 preserves directory setgid bit, causing l — both quote `drwx--s---`
- `C309` `R` **3224** + 7162 8176 8552 — Numlock problem after boot and suspend — both quote `numlock_by_default` · 8176 reached only through another ticket, not directly
- `C310` `R` **6992** + 7879 8485 9676 — omarchy-upgrade-to-quattro enables bt-agent.service but orphans  — both quote `/usr/lib/systemd/user/bt-agent.service` · 7879 reached only through another ticket, not directly
- `C311` `R` **7374** + 7803 10193 10344 — Power panel shows UPower's hwdb charge limit (75-80%) instead of — both quote `charge_limit=75,80`, `charge_control_start_threshold`
- `C312` `R` **7662** + 8483 8562 9507 — Fingerprint setup misses Broadcom BCM58200 ControlVault 3 (vendo — both quote `/usr/share/omarchy/bin/omarchy-hw-fingerprint`, `fingerprint_vendors`, `27c6 138a 06cb 08ff 1c7a 147e`
- `C313` `R` **7967** + 9099 9710 9775 — omarchy install service sunshine fails to enable unit on fresh i — both quote `/webapp/autostart`, `failed to enable unit: unit sunshine.service does not exist`
- `C314` `R` **8352** + 10037 10039 10061 — Hibernation resume fails on hybrid Intel+NVIDIA laptops — nvidia — both quote `$mkinitcpio_conf`
- `C315` `R` **4579** + 7867 8358 — [Bug/Dual Boot] After installation on HDD partition, only "EFI f — both quote `efi fallback`
- `C316` `R` **4821** + 7458 8359 — # No Sound Fix: ASUS ROG Strix G16 (2025) on Omarchy 3.4.1 — both quote `amixer`, `analog-output-headphones`, `headphone`
- `C317` `R` **7172** + 7176 9453 — Lock screen fingerprint retry livelocks after resume: overlappin — both quote `verify-match`, `fingerprintauthenticating`
- `C318` `R` **7178** + 7506 9674 — No way to disable the idle lock while keeping the screensaver —  — both quote `locktimeoutseconds`, `never lock`, `lockdelayseconds` · 9674 reached only through another ticket, not directly
- `C319` `R` **7418** + 9116 10745 — Cloning the bar plugin blanks the bar (broken Loader.Error fallb — both quote `failed to load, falling back to`, `shell.failedbarid`
- `C320` `R` **7481** + 7760 8600 — Qt.formatDate/Qt.formatDateTime ignore system locale for day/mon — both quote `omarchy plugin clone omarchy.clock`, `formatted`, `/plugins/panels/clock/barwidget.qml`
- `C321` `R` **8158** + 8212 10636 — omarchy-theme-set-browser hangs when brave-origin is running but — both quote `brave-origin-bin`
- `C322` `R` **8189** + 9136 10325 — Cloned bar plugin (kind: bar) never renders — required propertie — both quote `barmanifestfor`, `createobject`
- `C323` `R` **8492** + 9294 9845 — omarchy-hook runs every hook via bash, ignoring the shebang — si — both quote `$hook_path`, `|| echo`, `$hook_dir`
- `C324` `R` **9628** + 10170 10250 — Lid-open binding does not restore display brightness after suspe — both quote `switch:off:lid switch`
- `C325` `R` **10404** + 10439 10698 — Cloned service plugins are invisible to firstPartyServiceFor() ( — both quote `/plugins/bar/indicators/stayawake.qml`, `_services`, `idleservice`
- `C326` `R` **4891** + 5274 — Suspend/resume causes compositor freeze on NVIDIA hybrid GPU lap — both quote `systemd_sleep_freeze_user_sessions=false`, `nvidia-no-freeze-session`
- `C327` `R` **4901** + 8989 — Hybrid Intel+NVIDIA: Chromium hardware acceleration requires man — both quote `intel-media-driver`, `vainfo`, `eglcreateimage`
- `C328` `R` **5676** + 7697 — Intel IPU6 MIPI camera Raptor Lake not working — both quote `intel-ipu6-camera-hal-git`
- `C329` `R` **5827** + 5989 — linux-ptl: iwlwifi skbuff runaway OOM under wlan0 TX load on Del — both quote `skbuff_head_cache`, `skbuff_small_head`
- `C330` `R` **6475** + 7220 — [Quattro] D-Bus idle inhibits are silently dropped since hypridl — both quote `org.freedesktop.screensaver`, `inhibit`
- `C331` `R` **6633** + 8047 — installer: ship subvolid + x-systemd.remount=false in /etc/fstab — both quote `/etc/default/limine`, `systemd-remount-fs`, `omarchy-snapshot`
- `C332` `R` **6673** + 7242 — [Quattro] Display panel scale is per-monitor at runtime but pers — both quote `auto-reload`, `per-monitor`
- `C333` `R` **6833** + 8964 — Keyboard layout bar widget can switch the wrong device on T2 Mac — both quote `hl-virtual-keyboard`, `selectkeyboard`, `/plugins/bar/widgets/keyboardlayoutmodel.js`
- `C334` `R` **6876** + 8471 — omarchy_hooks.conf replaces HOOKS instead of extending it, dropp — both quote `/etc/mkinitcpio.conf`
- `C335` `R` **6880** + 9421 — SDDM greeter always uses US keyboard layout, ignoring the system — both quote `/etc/sddm.conf.d/10-wayland.conf`, `compositorcommand`, `/usr/share/sddm/hyprland.lua`
- `C336` `R` **6947** + 9636 — Steam idle-inhibit rule matches the client but not steam_app gam — both quote `float = true`, `steam_app_<appid>`, ` { float = true, idle_inhibit =`
- `C337` `R` **6956** + 7936 — Bluetooth widget disappears from shell when turned off — both quote `!adapter`, `visible: adapter !== null`, `rfkill unblock bluetooth`
- `C338` `R` **6977** + 7185 — `omarchy debug` and four other commands are unreachable inside t — both quote `$(dirname --`, `/usr/bin/omarchy-debug`, `omarchy debug idle`
- `C339` `R` **7022** + 10357 — omarchy toggle bar on/off has inverted semantics (hides bar on ' — both quote `toggle`, `${1:-toggle`
- `C340` `R` **7034** + 9197 — launch webapp fails when default browser is Firefox (no Chromium — both quote `xdg-settings get default-web-browser`
- `C341` `R` **7174** + 8961 — First-agent OAuth browser opens tiled under the 875×600 setup te — both quote `gpu_data_manager_impl_private`, `set your default agent`
- `C342` `R` **7183** + 10133 — omarchy-font-set: terminal restart notifications never fire — -g — both quote `path-or-uri`, `app-name`
- `C343` `R` **7233** + 7350 — Emoji not sent to clipboard — both quote `super+ctrl+e`, `/omarchy-menu-emoji-insert`, `bin/omarchy-menu-emoji-insert`
- `C344` `R` **7253** + 10556 — Cloned or third-party bar plugin fails to load, leaving no bar a — both quote `shell`, `manifest`
- `C345` `R` **7255** + 7440 — Quattro migration doesn't update kb_options, trapping Caps Lock  — both quote `shift:both_capslock_cancel`, `compose:caps,shift:both_capslock_cancel`, `compose:caps`
- `C346` `R` **7388** + 10691 — Apple Studio Display over USB4 flashes: stock preferred is 5K@12 — both quote `boltctl`, `/thunderbolt`, `mode = "preferred`
- `C347` `R` **7464** + 8902 — Obsidian shortcut never focuses a running window: ^obsidian$ no  — both quote `default/hypr/bindings/applications.lua:18`, `single-instance`, `^obsidian$`
- `C348` `R` **7597** + 10356 — Dropbox widget shows wrong quota for Basic accounts with bonus s — both quote `/plugins/panels/dropbox/status.py`, `get_space_usage`, `/2/users/get_space_usage`
- `C349` `R` **7624** + 10696 — Light themes render the Chromium tab strip bright yellow — both quote `#ffde5a`, `max-min`, `/etc/chromium/policies/managed/color.json`
- `C350` `R` **7635** + 9701 — Bar: every inline command module logs TypeError: Cannot assign t — both quote `customcommandmodule`, `injectprops`, `entry`
- `C351` `R` **7752** + 10282 — sunshine package built without CUDA support — NVENC silently fal — both quote `couldn't scale frame: invalid argument`, `/moonlight`, `hevc_nvenc`
- `C352` `R` **7810** + 9672 — omarchy default editor <gui-editor> does not update XDG MIME def — both quote `xdg-open`, `xdg-mime`, `nvim.desktop`
- `C353` `R` **7834** + 10145 — Notification replacement hints honoured by mako are ignored by t — both quote `replaces_id`, `/plugins/notifications/service.qml`
- `C354` `R` **7900** + 9675 — Dictation indicator opens the config instead of toggling dictati — both quote `/plugins/bar/indicators/dictation.qml`, `omarchy-voxtype-status`, `dictation.qml`
- `C355` `R` **7918** + 8240 — Invisible mouse cursor in VMware guest: vmwgfx hardware cursor p — both quote `no_hardware_cursors`, `fix-nouveau-cursor`, `/user/hardware/fix-nouveau-cursor.sh`
- `C356` `R` **8007** + 9669 — Cloning a "kind: bar" plugin (omarchy plugin clone omarchy.bar)  — both quote `kind: bar`, `panelwindow`
- `C357` `R` **8173** + 9241 — Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev  — both quote `/.xcompose`, `%h/.local/share/omarchy/default/xcompose`, `/.local/share/omarchy/default/xcompose`
- `C358` `R` **8475** + 8826 — Missing gst-libav, gst-plugins-bad and gst-plugins-ugly — both quote `gst-plugins-bad`, `gst-libav`
- `C359` `R` **8547** + 10372 — Quickshell SIGSEGV tearing down the workspaces Repeater when Hyp — both quote `/bar/widgets/workspaces.qml`, `plugins/bar/widgets/workspaces.qml`
- `C360` `R` **8780** + 8986 — omarchy update -y hangs on the orphaned-packages prompt — both quote `omarchy-update-system-pkgs-when`, `omarchy update -y`, `omarchy-update-restart`
- `C361` `R` **8868** + 9357 — Agents bar widget: Codex limits always show "unavailable" (stale — both quote `codex -s read-only -a untrusted app-server`, `codex-cli`, `account/read`
- `C362` `R` **9064** + 10732 — stable-mirror.omarchy.org Arch repo databases stale (~5 days beh — both quote `stable-mirror`, `extra`, `stable-mirror.omarchy.org`
- `C363` `R` **9569** + 9572 — omarchy-remove-gaming-heroic leaves ~/.config/heroic behind ($HO — both quote `/root`, `omarchy:requires-sudo=true`, `omarchy-apply-lock`
- `C364` `R` **9648** + 9905 — Lock screen retries fingerprint auth every 250ms forever with no — both quote `onerror`, `fingerprintauthenticating`

## Uncertain — 75 clusters, 97 tickets

Grouped by wording, or by nothing much. These are here so they are not silently dropped, not because they are believed.

- `C455` `P` **5343** + 5968 7363 — Open in Ghostty gone in Nautilus — both quote `nautilus-open-any-terminal` · 5968 reached only through another ticket, not directly
- `C456` `P` **6958** + 6959 9095 — omarchy font set resets Foot font size to 9, ignoring omarchy di — no direct link to 6958 — every ticket here reaches it through a third one
- `C457` `P` **7680** + 7815 8019 — Add a reveal toggle to the lock screen password field — no direct link to 7680 — every ticket here reaches it through a third one
- `C458` `P` **8145** + 7000 7495 — Clamshell watcher ignores desc: rules for the internal panel and — both touch bin/omarchy-hyprland-monitor-scaling
- `C459` `P` **8888** + 7258 9686 — omarchy_hooks.conf replaces HOOKS instead of extending it, dropp — no direct link to 8888 — every ticket here reaches it through a third one
- `C460` `P` **5144** + 5533 — Add battery charging threshold to toggle menu — no direct link to 5144 — every ticket here reaches it through a third one
- `C461` `P` **5312** + 7851 — Hybrid Intel+NVIDIA: Chromium hardware acceleration requires man — no direct link to 5312 — every ticket here reaches it through a third one
- `C462` `P` **5514** + 10095 — omarchy-capture-screenshot toggle leaves stale hyprpicker overla — both touch bin/omarchy-capture-screenshot
- `C463` `P` **5567** + 7459 — # No Sound Fix: ASUS ROG Strix G16 (2025) on Omarchy 3.4.1 — both quote `speaker`
- `C464` `P` **6499** + 6529 ⏱ — Add Setup > Network menu with DNS, QR Code, and Speed Test — both touch shell/plugins/panels/network/SpeedTestPanel.qml
- `C465` `P` **6627** + 6491 ⏱ — (4.0a) Improper Wraping of Long Lines in About — both quote `disablelinewrap`
- `C466` `P` **6646** + 6740 ⏱ — Issue with the omarchy.keyboard-layout plugin not visually switc — both touch shell/plugins/bar/widgets/KeyboardLayout.qml
- `C467` `P` **7029** + 9201 — Show the new track on the media OSD instead of the player name — both touch shell/plugins/services/media/MediaModel.js
- `C468` `P` **7063** + 8287 — NVIDIA 50xx Users - Can't Install - Boots to black screen — both quote `nomodeset`
- `C469` `P` **7225** + 7400 — The agents widget can be added to the bar twice, permanently — no direct link to 7225 — every ticket here reaches it through a third one
- `C470` `P` **7319** + 8874 — omarchy remove service dropbox and tailscale are committed witho — both quote `omarchy-remove-service-dropbox`
- `C471` `P` **7500** + 7717 — Cant Increase Width on Last window when on Scrolling workspace L — both quote `colresize`
- `C472` `P` **7606** + 9493 — feat: add screensaver options (Default, Neo Matrix, CBonsai, Pip — no direct link to 7606 — every ticket here reaches it through a third one
- `C473` `P` **7673** + 8581 — Display never blanks after lock: blank/wake silently stops worki — both touch shell/plugins/lock/Service.qml
- `C474` `P` **7773** + 5678 — Intel IPU6 MIPI camera Raptor Lake not working — no direct link to 7773 — every ticket here reaches it through a third one
- `C475` `P` **7831** + 7004 — RTL8852BE Wi-Fi dead after s2idle; rtw89 resume wedges the chip — both quote `omarchy-restart-wifi`
- `C476` `P` **7890** + 8149 — Skip incompatible Bun-based agents on CPUs below their instructi — no direct link to 7890 — every ticket here reaches it through a third one
- `C477` `P` **8132** + 8241 — Invisible mouse cursor in VMware guest: vmwgfx hardware cursor p — no direct link to 8132 — every ticket here reaches it through a third one
- `C478` `P` **8160** + 10383 — Tray icons are unclickable: clicks fall through to the bar's ges — both touch shell/plugins/bar/widgets/Tray.qml
- `C479` `P` **8452** + 7877 — [Quattro] D-Bus idle inhibits are silently dropped since hypridl — both quote `idle-inhibit`, `idlemonitor`
- `C480` `P` **8511** + 8155 — Theme backgrounds can cycle forward but not backward — near-identical titles · 8155 reached only through another ticket, not directly
- `C481` `P` **8627** + 8951 ⏱ — Harden CUPS printer discovery — both quote `cups-browsed`
- `C482` `P` **8894** + 10714 — omarchy update -y hangs on the orphaned-packages prompt — no direct link to 8894 — every ticket here reaches it through a third one
- `C483` `P` **9040** + 10361 — First-agent OAuth browser opens tiled under the 875×600 setup te — both quote `browser`, `omarchy-launch-browser`
- `C484` `P` **9056** + 9093 — Spamming a menu-summoning keybinding (Super+K) leaks orphaned om — both quote `omarchy-menu-select`
- `C485` `P` **9170** + 9697 — No way to disable the idle lock while keeping the screensaver —  — no direct link to 9170 — every ticket here reaches it through a third one
- `C486` `P` **9343** + 7026 — Cannot run Migration (1786643346) because an "browser window is  — no direct link to 9343 — every ticket here reaches it through a third one
- `C487` `P` **9460** + 9461 — [codex] OM-SEC-04: Require package authenticity during Quattro — no direct link to 9460 — every ticket here reaches it through a third one
- `C488` `P` **9520** + 9838 — Multi-window session not fully restored after reboot — close-all — no direct link to 9520 — every ticket here reaches it through a third one
- `C489` `P` **9679** + 6105 — Make webapps profile-aware for Chromium-based browsers — both quote `profile-aware`
- `C490` `P` **10283** + 10284 — Stage upload-log payloads in a private temp directory — no direct link to 10283 — every ticket here reaches it through a third one
- `C491` `P` **10331** + 8025 — Add automatic display brightness — both touch test/shell.d/config-test.sh
- `C492` `R` **6885** + 6895 7214 7897 7916 8521 9026 10244 — Battery percent in the top bar shows only BAT0 — no direct link to 6885 — every ticket here reaches it through a third one
- `C493` `R` **8189** + 8775 9115 9588 9599 — Cloned bar plugin (kind: bar) never renders — required propertie — both quote `activebarsourceurl`, `activebarmanifest`
- `C494` `R` **3669** + 7154 9544 9901 — Bug regarding "omarchy-launch-or-focus" and ghostty — no direct link to 3669 — every ticket here reaches it through a third one
- `C495` `R` **7050** + 7218 8582 — `omarchy install service sunshine` fails: "Unit sunshine.service — both quote `omarchy-install-service-sunshine`
- `C496` `R` **7233** + 7379 8206 — Emoji not sent to clipboard — no direct link to 7233 — every ticket here reaches it through a third one
- `C497` `R` **7253** + 8202 9593 — Cloned or third-party bar plugin fails to load, leaving no bar a — both quote `shell/plugins/bar/bar.qml`, `omarchypath`
- `C498` `R` **7835** + 8113 8604 — I am trying to install and run Omarchy inside VMware, but I cons — no direct link to 7835 — every ticket here reaches it through a third one
- `C499` `R` **8758** + 9922 10690 — Boot with the lid closed on a dock: logind suspends before the d — both quote `handlelidswitch=suspend` · 9922 reached only through another ticket, not directly
- `C500` `R` **8780** + 9501 10021 — omarchy update -y hangs on the orphaned-packages prompt — both quote `omarchy-update-restart` · 9501 reached only through another ticket, not directly
- `C501` `R` **1434** + 8161 — Hyprsunset is reset when/after screen locks — no direct link to 1434 — every ticket here reaches it through a third one
- `C502` `R` **2728** + 2831 — Mise Python conflicting with system  python — no direct link to 2728 — every ticket here reaches it through a third one
- `C503` `R` **2798** + 8543 — nautilus takes 25s to start — both quote `xdg-desktop-por`
- `C504` `R` **3224** + 8912 — Numlock problem after boot and suspend — both quote `numlock_by_default`
- `C505` `R` **3669** + 4927 — Bug regarding "omarchy-launch-or-focus" and ghostty — no direct link to 3669 — every ticket here reaches it through a third one
- `C506` `R` **4579** + 7515 — [Bug/Dual Boot] After installation on HDD partition, only "EFI f — no direct link to 4579 — every ticket here reaches it through a third one
- `C507` `R` **5506** + 8797 — omarchy-capture-screenshot toggle leaves stale hyprpicker overla — both quote `omarchy-capture-screenshot`
- `C508` `R` **6475** + 7199 — [Quattro] D-Bus idle inhibits are silently dropped since hypridl — no direct link to 6475 — every ticket here reaches it through a third one
- `C509` `R` **6823** + 8530 — Dictation bar icon errors when voxtype isn't installed (missing  — both quote `voxtype-bin`
- `C510` `R` **7019** + 7078 — Cannot run Migration (1786643346) because an "browser window is  — no direct link to 7019 — every ticket here reaches it through a third one
- `C511` `R` **7022** + 10044 — omarchy toggle bar on/off has inverted semantics (hides bar on ' — both quote `off-screen`, `toggle`
- `C512` `R` **7025** + 9395 — omarchy-menu-keybindings hangs forever when a user Lua config it — both quote `omarchy-menu-keybindings --print`
- `C513` `R` **7045** + 7061 — NVIDIA 50xx Users - Can't Install - Boots to black screen — no direct link to 7045 — every ticket here reaches it through a third one
- `C514` `R` **7085** + 9837 — Multi-window session not fully restored after reboot — close-all — no direct link to 7085 — every ticket here reaches it through a third one
- `C515` `R` **7128** + 7221 — The agents widget can be added to the bar twice, permanently — no direct link to 7128 — every ticket here reaches it through a third one
- `C516` `R` **7172** + 7229 — Lock screen fingerprint retry livelocks after resume: overlappin — no direct link to 7172 — every ticket here reaches it through a third one
- `C517` `R` **7255** + 7346 — Quattro migration doesn't update kb_options, trapping Caps Lock  — no direct link to 7255 — every ticket here reaches it through a third one
- `C518` `R` **7388** + 7939 — Apple Studio Display over USB4 flashes: stock preferred is 5K@12 — both quote `preferred`, ` position =`
- `C519` `R` **7418** + 10324 — Cloning the bar plugin blanks the bar (broken Loader.Error fallb — both quote `pluginbarloader.errorstring`
- `C520` `R` **7539** + 9147 — User password update in menu leaves old root password active — no direct link to 7539 — every ticket here reaches it through a third one
- `C521` `R` **7632** + 7633 — Add Cursor CLI as default agent option in menu — no direct link to 7632 — every ticket here reaches it through a third one
- `C522` `R` **7652** + 8580 — Display never blanks after lock: blank/wake silently stops worki — both quote `lock-requested`, `runwake`
- `C523` `R` **7834** + 9671 — Notification replacement hints honoured by mako are ignored by t — no direct link to 7834 — every ticket here reaches it through a third one
- `C524` `R` **7835** + 10620 — I am trying to install and run Omarchy inside VMware, but I cons — no direct link to 7835 — every ticket here reaches it through a third one
- `C525` `R` **7881** + 7883 — Skip incompatible Bun-based agents on CPUs below their instructi — no direct link to 7881 — every ticket here reaches it through a third one
- `C526` `R` **8173** + 9541 — Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev  — both quote `omarchy-fcitx5`, `~/.xcompose`
- `C527` `R` **8183** + 8364 — Regression: Quickshell workspace indicator shows globally focuse — no direct link to 8183 — every ticket here reaches it through a third one
- `C528` `R` **8832** + 8833 ⏱ — Migration 1787515927 failed — no direct link to 8832 — every ticket here reaches it through a third one
- `C529` `R` **9635** + 10401 — Calendar grid duplicates September 5 and shifts dates in month v — no direct link to 9635 — every ticket here reaches it through a third one

## We think these are NOT duplicates — 71 clusters, 86 tickets

Grouped by the first pass, and the evidence now says no. Three shapes live here: the same author on both patches (a job split, not a copy); one author filing a series of related tickets, which the first map mistook for re-submission and put in its top band; and a body that names the other ticket to distinguish itself from it — including politely, *"similar in spirit to #9194"*, which reads as agreement to a machine and as difference to a person. Highest value to check, because the original worklist proposes closing them.

- `C530` `P` **9070** + 9071 9072 9073 — Make package ownership the Quattro update boundary — same author, same area — probably one job split across patches, not a copy
- `C531` `P` **9469** + 9467 9472 9474 — [codex] OM-SEC-12: Bind update inhibitor cleanup to process iden — same author, same area — probably one job split across patches, not a copy
- `C532` `P` **4793** + 7699 7720 — hibernation setup installs keyboard-backlight system-sleep hook  — both touch bin/omarchy-toggle-hybrid-gpu
- `C533` `P` **7343** + 7348 7410 — fnmode=2 is forced on every install: a no-op for the keyboards i — same author, same area — probably one job split across patches, not a copy
- `C534` `P` **8802** + 8804 9094 — Show every Hyprland workspace in the bar, not only 1-10 — same author, same area — probably one job split across patches, not a copy
- `C535` `P` **9088** + 9080 9087 — Update basecamp/omarchy references to omacom/omarchy in contribu — the text names the other ticket and says it is not it
- `C536` `P` **9456** + 7158 8531 — Lock screen fingerprint retry livelocks after resume: overlappin — the text names the other ticket and says it is not it
- `C537` `P` **10503** + 10504 10505 — [Security] Keep the 1Password lock flock out of world-writable / — same author, same area — probably one job split across patches, not a copy
- `C538` `P` **1661** + 9399 — add ssh-agent support to store SSH key passphrases — the text names the other ticket and says it is not it
- `C539` `P` **5193** + 5194 — fix(hardware): add Alienware Area-51 iwd boot-delay workaround — same author, same area — probably one job split across patches, not a copy
- `C540` `P` **6098** + 6802 — feat(webapps): add Zen browser support to launcher — same author, same area — probably one job split across patches, not a copy
- `C541` `P` **6122** + 6986 — fix: multi-monitor window highlighting in slurp capture — same author, same area — probably one job split across patches, not a copy
- `C542` `P` **6433** + 6435 ⏱ — Plugin cloning via menu — same author, same area — probably one job split across patches, not a copy
- `C543` `P` **6477** + 7274 — Add Kimi Code and Grok Build usage collectors — the text names the other ticket and says it is not it
- `C544` `P` **6499** + 6598 ⏱ — Add Setup > Network menu with DNS, QR Code, and Speed Test — same author, same area — probably one job split across patches, not a copy
- `C545` `P` **6604** + 9257 — Add Cursor agent usage collector — the text names the other ticket and says it is not it
- `C546` `P` **6621** + 6680 ⏱ — Add deferred first-boot provisioning and factory reset — same author, same area — probably one job split across patches, not a copy
- `C547` `P` **6645** + 6647 — Add Hermes usage to agents monitor — same author, same area — probably one job split across patches, not a copy
- `C548` `P` **6656** + 6674 ⏱ — Carry tmux's tab moves, zoom flag, and hostname into herdr — same author, same area — probably one job split across patches, not a copy
- `C549` `P` **6713** + 6721 ⏱ — Offer the Quattro upgrade from the Update menu — same author, same area — probably one job split across patches, not a copy
- `C550` `P` **6749** + 6755 ⏱ — Shell tests dump core instead of skipping when WAYLAND_DISPLAY i — the text names the other ticket and says it is not it
- `C551` `P` **6832** + 8631 — Dictation bar icon errors when voxtype isn't installed (missing  — the text names the other ticket and says it is not it
- `C552` `P` **6834** + 9129 — Keyboard layout bar widget can switch the wrong device on T2 Mac — same author, same area — probably one job split across patches, not a copy
- `C553` `P` **6988** + 6994 ⏱ — Keep the calendar's day names in English — same author, same area — probably one job split across patches, not a copy
- `C554` `P` **7029** + 7168 — Show the new track on the media OSD instead of the player name — the text names the other ticket and says it is not it · 7168 reached only through another ticket, not directly
- `C555` `P` **7039** + 8299 — launch webapp fails when default browser is Firefox (no Chromium — the text names the other ticket and says it is not it
- `C556` `P` **7188** + 7189 — Screen recording fails silently on the external monitor of a hyb — the text names the other ticket and says it is not it
- `C557` `P` **7259** + 7771 — Plugin hot-reload never picks up changed plugin code (stale QML  — the text names the other ticket and says it is not it · 7771 reached only through another ticket, not directly
- `C558` `P` **7359** + 8879 — `omarchy install service sunshine` fails: "Unit sunshine.service — same author, same area — probably one job split across patches, not a copy
- `C559` `P` **7472** + 7492 ⏱ — Switch DNS providers without a password prompt — the text names the other ticket and says it is not it
- `C560` `P` **7982** + 9148 — omarchy-drive-info loses the drive model when a nested crypt/LVM — the text names the other ticket and says it is not it
- `C561` `P` **8672** + 8673 — Add generic Snapdragon X support on aarch64 — same author, same area — probably one job split across patches, not a copy
- `C562` `P` **8786** + 9063 — Dual-GPU AMD: PCI by-path in AQ_DRM_DEVICES silently login-loops — the text names the other ticket and says it is not it
- `C563` `P` **8854** + 8857 — Add `omarchy reboot-windows` for dual-boot machines — same author, same area — probably one job split across patches, not a copy
- `C564` `P` **8862** + 9208 — Agents panel: activity punchcard for records that carry usageByH — the text names the other ticket and says it is not it
- `C565` `P` **8997** + 10190 — Regression: Quickshell workspace indicator shows globally focuse — the text names the other ticket and says it is not it
- `C566` `P` **9162** + 9169 — omarchy-network-speedtest: samples divided by a nominal 1s that  — same author, same area — probably one job split across patches, not a copy
- `C567` `P` **9181** + 9183 — [Quattro] Lock password field can lose focus after suspend resum — same author, same area — probably one job split across patches, not a copy
- `C568` `P` **9195** + 9210 — Keep T2 Mac USB-C ports awake after suspend — same author, same area — probably one job split across patches, not a copy
- `C569` `P` **9255** + 9267 ⏱ — Harden existing key-based SSH setups — the text names the other ticket and says it is not it
- `C570` `P` **9312** + 9313 — Add responsive theme background support — same author, same area — probably one job split across patches, not a copy
- `C571` `P` **9573** + 9571 — omarchy-remove-gaming-heroic leaves ~/.config/heroic behind ($HO — same author, same area — probably one job split across patches, not a copy
- `C572` `P` **9830** + 10211 — Fix T2 Mac suspend: s2idle, d3cold, and brcmfmac — the text names the other ticket and says it is not it
- `C573` `P` **9908** + 9909 — Install AppImages as real apps, like web apps and TUIs — same author, same area — probably one job split across patches, not a copy
- `C574` `P` **10510** + 10511 — Tailscale panel: exit node rows show OS hostname instead of Magi — same author, same area — probably one job split across patches, not a copy
- `C575` `P` **10660** + 10677 — Background wipe animates on only one output — same author, same area — probably one job split across patches, not a copy
- `C576` `P` **10759** + 10760 ⏱ — Install broadcom-wl-dkms now that Arch dropped the prebuilt modu — same author, same area — probably one job split across patches, not a copy
- `C577` `R` **10030** + 10122 10221 10604 — Top-bar widgets intermittently stop responding to mouse clicks — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C578` `R` **7380** + 9549 10108 — omarchy-shell crashes and relaunches on every wake from idle loc — the text names the other ticket and says it is not it
- `C579` `R` **8239** + 8369 8769 — Omarchy 'omarchy update' — the text names the other ticket and says it is not it
- `C580` `R` **9683** + 9684 9685 — Add OpenCode collector to the Agents panel — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C581` `R` **2798** + 7944 — nautilus takes 25s to start — the text names the other ticket and says it is not it
- `C582` `R` **4901** + 8979 — Hybrid Intel+NVIDIA: Chromium hardware acceleration requires man — the text names the other ticket and says it is not it
- `C583` `R` **5827** + 7056 — linux-ptl: iwlwifi skbuff runaway OOM under wlan0 TX load on Del — the text names the other ticket and says it is not it
- `C584` `R` **5868** + 7573 — Bluetooth is turned off at boot time — the text names the other ticket and says it is not it · 7573 reached only through another ticket, not directly
- `C585` `R` **6633** + 6634 — installer: ship subvolid + x-systemd.remount=false in /etc/fstab — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C586` `R` **6878** + 7049 — Quattro upgrade drops non-US keyboard layout when vconsole.conf  — the text names the other ticket and says it is not it
- `C587` `R` **6992** + 8962 — omarchy-upgrade-to-quattro enables bt-agent.service but orphans  — the text names the other ticket and says it is not it
- `C588` `R` **7034** + 8298 — launch webapp fails when default browser is Firefox (no Chromium — the text names the other ticket and says it is not it
- `C589` `R` **7233** + 9388 — Emoji not sent to clipboard — the text names the other ticket and says it is not it · 9388 reached only through another ticket, not directly
- `C590` `R` **8111** + 10339 — Tray icons are unclickable: clicks fall through to the bar's ges — the text names the other ticket and says it is not it
- `C591` `R` **8183** + 10187 — Regression: Quickshell workspace indicator shows globally focuse — the text names the other ticket and says it is not it
- `C592` `R` **8367** + 8372 — [Security] omarchy debug and omarchy upload log stage root-colle — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C593` `R` **9029** + 9756 — Menu blocks on-screen keyboard input: Exclusive keyboard focus r — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C594` `R` **9180** + 9182 — [Quattro] Lock password field can lose focus after suspend resum — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C595` `R` **9184** + 9231 — [Quattro] Idle screensaver-to-lock transition flashes the passwo — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C596` `R` **9190** + 9389 — omarchy-hw-touchpad fails to detect Apple bcm5974 trackpad (name — the text names the other ticket and says it is not it
- `C597` `R` **9194** + 9295 — Consider setting kernel.kptr_restrict=1 by default — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C598` `R` **9268** + 9269 —   Quickshell SIGSEGV in QQuickTextPrivate::updateLayout after in — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C599` `R` **9552** + 9559 — Default fcitx5 service breaks Hyprland multi-layout keyboard swi — one author filing a series of related tickets — distinct work that shares a theme, not a copy
- `C600` `R` **10508** + 10509 — Tailscale panel: exit node rows show OS hostname instead of Magi — one author filing a series of related tickets — distinct work that shares a theme, not a copy

# PART TWO — a ticket and its own fix (219 clusters, 219 tickets)

**These are not duplicates.** Each is one ticket and one open patch that would close it.
They leave the queue when the patch merges, which is a fix landing, not waste. They are
here because the original count included them, and because the second band below is worth
checking: those patches never declared what they close, so the link is an inference.

## Declared — the patch body carries a parsed `Fixes #N` — 129 clusters

Held 42 times out of 42 when checked. Read these for form; do not spend long on them.

- `C001` `F` patch **4928** → ticket 3669 — Bug regarding "omarchy-launch-or-focus" and ghostty — the patch declares it closes this ticket
- `C002` `F` patch **5312** → ticket 4901 — Hybrid Intel+NVIDIA: Chromium hardware acceleration requires man — the patch declares it closes this ticket
- `C003` `F` patch **5514** → ticket 5506 — omarchy-capture-screenshot toggle leaves stale hyprpicker overla — the patch declares it closes this ticket
- `C004` `F` patch **5545** → ticket 4869 — Ctrl+C during sudo password prompt in pkg-install/pkg-aur-instal — the patch declares it closes this ticket
- `C005` `F` patch **5548** → ticket 5547 — Browser managed policy directories are world-writable — the patch declares it closes this ticket
- `C006` `F` patch **5567** → ticket 4821 — # No Sound Fix: ASUS ROG Strix G16 (2025) on Omarchy 3.4.1 — the patch declares it closes this ticket
- `C007` `F` patch **6344** → ticket 6085 ⏱ — Choosing non-English layout in installation makes the system unu — the patch declares it closes this ticket
- `C008` `F` patch **6424** → ticket 6416 ⏱ — omarchy-launch-browser launches an empty executable after unsett — the patch declares it closes this ticket
- `C009` `F` patch **6487** → ticket 6462 ⏱ — Quickshell panels do not dismiss on outside clicks on another mo — the patch declares it closes this ticket
- `C010` `F` patch **6533** → ticket 5414 — Keyboard backlight settings inconsistently jump in steps of 9 or — the patch declares it closes this ticket
- `C011` `F` patch **6561** → ticket 6530 ⏱ — "terminal" tag does not get applied properly — the patch declares it closes this ticket
- `C012` `F` patch **6563** → ticket 6554 ⏱ — Menu: SUPER+ESCAPE opens an empty "Htop" menu instead of the Sys — the patch declares it closes this ticket
- `C013` `F` patch **6584** → ticket 6582 ⏱ — Wifi password input box fails to re-appear when wifi-menu is clo — the patch declares it closes this ticket
- `C014` `F` patch **6601** → ticket 6595 ⏱ — Menu briefly shows options that don't match the current state — the patch declares it closes this ticket
- `C015` `F` patch **6613** → ticket 6609 ⏱ — Quickshell keyboard shortcuts open panels on the laptop display  — the patch declares it closes this ticket
- `C016` `F` patch **6615** → ticket 6576 ⏱ — upgrade-to-quattro: install_keyrings uses `pacman -Sy`, so a reb — the patch declares it closes this ticket
- `C017` `F` patch **6617** → ticket 6575 ⏱ — upgrade-to-quattro: missing bin/omarchy-done aborts at step 18/3 — the patch declares it closes this ticket
- `C018` `F` patch **6619** → ticket 6618 ⏱ — omarchy-mise-install overwrites symlink targets (breaks existing — the patch declares it closes this ticket
- `C019` `F` patch **6627** → ticket 6465 ⏱ — (4.0a) Improper Wraping of Long Lines in About — the patch declares it closes this ticket
- `C020` `F` patch **6646** → ticket 6574 ⏱ — Issue with the omarchy.keyboard-layout plugin not visually switc — the patch declares it closes this ticket
- `C021` `F` patch **6653** → ticket 6651 ⏱ — Quattro, beta 1: Setup → Direct boot reports Error: No Omarchy U — the patch declares it closes this ticket
- `C022` `F` patch **6654** → ticket 6649 ⏱ — omarchy-agent-usage-claude: race condition in scan_opencode_usag — the patch declares it closes this ticket
- `C023` `F` patch **6687** → ticket 6678 ⏱ — Migration 1786279107 fails with a custom clock widget — the patch declares it closes this ticket
- `C024` `F` patch **6692** → ticket 6684 ⏱ — omarchy-shell exits when locking with a screen that has no valid — the patch declares it closes this ticket
- `C025` `F` patch **6701** → ticket 6668 ⏱ — Monitors stay black (0x0) when PC boots with monitors off — neve — the patch declares it closes this ticket
- `C026` `F` patch **6712** → ticket 6660 ⏱ — Quattro: hyprctl reload fails with a Lua timeout error — the patch declares it closes this ticket
- `C027` `F` patch **6727** → ticket 6726 ⏱ — perf(bar): stop spawning hyprctl every 10s, gate tray layer, cac — the patch declares it closes this ticket
- `C028` `F` patch **6749** → ticket 6743 ⏱ — Shell tests dump core instead of skipping when WAYLAND_DISPLAY i — the patch declares it closes this ticket
- `C029` `F` patch **6752** → ticket 5906 ⏱ — Treat LVDS laptop panels as internal displays — the patch declares it closes this ticket
- `C030` `F` patch **6775** → ticket 6774 ⏱ — [Bug] [Quattro]: Interrupted thumbnail generation can permanentl — the patch declares it closes this ticket
- `C031` `F` patch **6791** → ticket 6790 ⏱ — NVIDIA installs: `kms` hook bundles ~100 MB of unused nouveau GS — the patch declares it closes this ticket
- `C032` `F` patch **6815** → ticket 6806 ⏱ — Quickshell AppLibrary causes ~20% CPU usage at idle — the patch declares it closes this ticket
- `C033` `F` patch **6830** → ticket 6818 ⏱ — Upstream qemu update blocks omarchy update — the patch declares it closes this ticket
- `C034` `F` patch **6832** → ticket 6823 — Dictation bar icon errors when voxtype isn't installed (missing  — the patch declares it closes this ticket
- `C035` `F` patch **6834** → ticket 6833 — Keyboard layout bar widget can switch the wrong device on T2 Mac — the patch declares it closes this ticket
- `C036` `F` patch **6842** → ticket 6841 ⏱ — [Quattro] Recent update got stuck running migration 1786643346 — the patch declares it closes this ticket
- `C037` `F` patch **6852** → ticket 6838 ⏱ — [Quattro] LocalSend tray item duplicates the built-in Share flow — the patch declares it closes this ticket
- `C038` `F` patch **6896** → ticket 6880 — SDDM greeter always uses US keyboard layout, ignoring the system — the patch declares it closes this ticket
- `C039` `F` patch **6938** → ticket 6903 ⏱ — Foot terminal shows syntax error in foot.ini on startup — the patch declares it closes this ticket
- `C040` `F` patch **6939** → ticket 6914 ⏱ — `o.shell_succeeds()` always returns false inside Hyprland, so NV — the patch declares it closes this ticket
- `C041` `F` patch **6942** → ticket 6913 ⏱ — Clone Plugin from Setup > Plugins fails: "unknown clone option:  — the patch declares it closes this ticket
- `C042` `F` patch **6943** → ticket 6881 ⏱ — Bar stuck in "move bar" mode: press-and-hold on a center widget  — the patch declares it closes this ticket
- `C043` `F` patch **6958** → ticket 6957 — omarchy font set resets Foot font size to 9, ignoring omarchy di — the patch declares it closes this ticket
- `C044` `F` patch **7039** → ticket 7034 — launch webapp fails when default browser is Firefox (no Chromium — the patch declares it closes this ticket
- `C045` `F` patch **7151** → ticket 7093 — Clicking workspaces in BarWidget is sluggish vs keybinds — the patch declares it closes this ticket
- `C046` `F` patch **7236** → ticket 6985 ⏱ — Quattro (4.0) install fails: fix-synaptic-touchpad.sh psmouse mo — the patch declares it closes this ticket
- `C047` `F` patch **7239** → ticket 6977 — `omarchy debug` and four other commands are unreachable inside t — the patch declares it closes this ticket
- `C048` `F` patch **7254** → ticket 7253 — Cloned or third-party bar plugin fails to load, leaving no bar a — the patch declares it closes this ticket
- `C049` `F` patch **7256** → ticket 7255 — Quattro migration doesn't update kb_options, trapping Caps Lock  — the patch declares it closes this ticket
- `C050` `F` patch **7319** → ticket 7112 — omarchy remove service dropbox and tailscale are committed witho — the patch declares it closes this ticket
- `C051` `F` patch **7343** → ticket 7110 — fnmode=2 is forced on every install: a no-op for the keyboards i — the patch declares it closes this ticket
- `C052` `F` patch **7359** → ticket 7050 — `omarchy install service sunshine` fails: "Unit sunshine.service — the patch declares it closes this ticket
- `C053` `F` patch **7444** → ticket 7411 — Zen installer writes policies to unused /opt/zen-browser path — the patch declares it closes this ticket
- `C054` `F` patch **7465** → ticket 7464 — Obsidian shortcut never focuses a running window: ^obsidian$ no  — the patch declares it closes this ticket
- `C055` `F` patch **7500** → ticket 5101 — Cant Increase Width on Last window when on Scrolling workspace L — the patch declares it closes this ticket
- `C056` `F` patch **7519** → ticket 6673 — [Quattro] Display panel scale is per-monitor at runtime but pers — the patch declares it closes this ticket
- `C057` `F` patch **7600** → ticket 7597 — Dropbox widget shows wrong quota for Basic accounts with bonus s — the patch declares it closes this ticket
- `C058` `F` patch **7673** → ticket 7652 — Display never blanks after lock: blank/wake silently stops worki — the patch declares it closes this ticket
- `C059` `F` patch **7708** → ticket 7706 — Weather unit mismatch in Omarchy 4 — the patch declares it closes this ticket
- `C060` `F` patch **7780** → ticket 7762 — [Quattro] Screensaver only exits on a keypress inside its own te — the patch declares it closes this ticket
- `C061` `F` patch **7905** → ticket 7900 — Dictation indicator opens the config instead of toggling dictati — the patch declares it closes this ticket
- `C062` `F` patch **7982** → ticket 7974 — omarchy-drive-info loses the drive model when a nested crypt/LVM — the patch declares it closes this ticket
- `C063` `F` patch **8005** → ticket 7952 — grammar typo in Manual - Navigation — the patch declares it closes this ticket
- `C064` `F` patch **8086** → ticket 8038 — Changing `idle.screensaver` / `idle.lock` in `shell.json` silent — the patch declares it closes this ticket
- `C065` `F` patch **8089** → ticket 8008 ⏱ — Fix readme 404 links — the patch declares it closes this ticket
- `C066` `F` patch **8132** → ticket 7918 — Invisible mouse cursor in VMware guest: vmwgfx hardware cursor p — the patch declares it closes this ticket
- `C067` `F` patch **8136** → ticket 7967 — omarchy install service sunshine fails to enable unit on fresh i — the patch declares it closes this ticket
- `C068` `F` patch **8146** → ticket 8007 — Cloning a "kind: bar" plugin (omarchy plugin clone omarchy.bar)  — the patch declares it closes this ticket
- `C069` `F` patch **8147** → ticket 8122 — omarchy-install-and-launch: "Press any key to close" races the a — the patch declares it closes this ticket
- `C070` `F` patch **8160** → ticket 8111 — Tray icons are unclickable: clicks fall through to the bar's ges — the patch declares it closes this ticket
- `C071` `F` patch **8175** → ticket 8173 — Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev  — the patch declares it closes this ticket
- `C072` `F` patch **8258** → ticket 8158 — omarchy-theme-set-browser hangs when brave-origin is running but — the patch declares it closes this ticket
- `C073` `F` patch **8341** → ticket 6075 — Bitwarden Chrome Extension popup locked to 875x600 since 2026.5. — the patch declares it closes this ticket
- `C074` `F` patch **8370** → ticket 8367 — [Security] omarchy debug and omarchy upload log stage root-colle — the patch declares it closes this ticket
- `C075` `F` patch **8424** → ticket 8423 — [Security] omarchy-refresh-config will write outside ~/.config g — the patch declares it closes this ticket
- `C076` `F` patch **8452** → ticket 6475 — [Quattro] D-Bus idle inhibits are silently dropped since hypridl — the patch declares it closes this ticket
- `C077` `F` patch **8493** → ticket 8492 — omarchy-hook runs every hook via bash, ignoring the shebang — si — the patch declares it closes this ticket
- `C078` `F` patch **8496** → ticket 8495 ⏱ — [Security] omarchy-webapp-install writes javascript:/file: URLs  — the patch declares it closes this ticket
- `C079` `F` patch **8498** → ticket 7539 — User password update in menu leaves old root password active — the patch declares it closes this ticket
- `C080` `F` patch **8507** → ticket 8503 — omarchy-menu-images runs awk against index.tsv once per thumbnai — the patch declares it closes this ticket
- `C081` `F` patch **8511** → ticket 8508 — Theme backgrounds can cycle forward but not backward — the patch declares it closes this ticket
- `C082` `F` patch **8512** → ticket 8509 — No way to share the clipboard as a QR code from Trigger > Share — the patch declares it closes this ticket
- `C083` `F` patch **8529** → ticket 8528 — Feature: manage NetworkManager VPN profiles from the built-in ne — the patch declares it closes this ticket
- `C084` `F` patch **8590** → ticket 8239 — Omarchy 'omarchy update' — the patch declares it closes this ticket
- `C085` `F` patch **8786** → ticket 8776 — Dual-GPU AMD: PCI by-path in AQ_DRM_DEVICES silently login-loops — the patch declares it closes this ticket
- `C086` `F` patch **8792** → ticket 7300 — screenrecord --with-webcam: overlay locks to YUYV @5fps instead  — the patch declares it closes this ticket
- `C087` `F` patch **8835** → ticket 8832 ⏱ — Migration 1787515927 failed — the patch declares it closes this ticket
- `C088` `F` patch **8881** → ticket 8870 — omarchy-notification-wait treats its timeout argument as an atte — the patch declares it closes this ticket
- `C089` `F` patch **8882** → ticket 8523 — omarchy-brightness-display: Brightness trapped at 0% on displays — the patch declares it closes this ticket
- `C090` `F` patch **8894** → ticket 8780 — omarchy update -y hangs on the orphaned-packages prompt — the patch declares it closes this ticket
- `C091` `F` patch **8997** → ticket 8183 — Regression: Quickshell workspace indicator shows globally focuse — the patch declares it closes this ticket
- `C092` `F` patch **9039** → ticket 8920 — tsl and hsl silently do nothing on a non-numeric pane count inst — the patch declares it closes this ticket
- `C093` `F` patch **9041** → ticket 9030 — Default Enter keybindings never match on keyboards that emit KP_ — the patch declares it closes this ticket
- `C094` `F` patch **9056** → ticket 9057 — Spamming a menu-summoning keybinding (Super+K) leaks orphaned om — the patch declares it closes this ticket
- `C095` `F` patch **9133** → ticket 8999 — omarchy-menu-keybindings: code: binds always displayed with US s — the patch declares it closes this ticket
- `C096` `F` patch **9162** → ticket 9144 — omarchy-network-speedtest: samples divided by a nominal 1s that  — the patch declares it closes this ticket
- `C097` `F` patch **9170** → ticket 7178 — No way to disable the idle lock while keeping the screensaver —  — the patch declares it closes this ticket
- `C098` `F` patch **9181** → ticket 9180 — [Quattro] Lock password field can lose focus after suspend resum — the patch declares it closes this ticket
- `C099` `F` patch **9218** → ticket 9190 — omarchy-hw-touchpad fails to detect Apple bcm5974 trackpad (name — the patch declares it closes this ticket
- `C100` `F` patch **9244** → ticket 9243 — Voxtype pause_media silently fails: playerctl not installed by o — the patch declares it closes this ticket
- `C101` `F` patch **9275** → ticket 9266 — Cloned theme without [colors.selection] gets selection == foregr — the patch declares it closes this ticket
- `C102` `F` patch **9288** → ticket 9194 — Consider setting kernel.kptr_restrict=1 by default — the patch declares it closes this ticket
- `C103` `F` patch **9328** → ticket 8538 — Obsidian user-flags.conf default has single-dash typo (-disable- — the patch declares it closes this ticket
- `C104` `F` patch **9398** → ticket 9384 — omarchy-drive-password: "No encrypted drives available" due to u — the patch declares it closes this ticket
- `C105` `F` patch **9520** → ticket 7085 — Multi-window session not fully restored after reboot — close-all — the patch declares it closes this ticket
- `C106` `F` patch **9563** → ticket 9556 — XDG_DESKTOP_DIR="$HOME" makes apps scatter .desktop shortcuts in — the patch declares it closes this ticket
- `C107` `F` patch **9565** → ticket 9552 — Default fcitx5 service breaks Hyprland multi-layout keyboard swi — the patch declares it closes this ticket
- `C108` `F` patch **9605** → ticket 9374 — windows-vm: chmod 0700 preserves directory setgid bit, causing l — the patch declares it closes this ticket
- `C109` `F` patch **9632** → ticket 9184 — [Quattro] Idle screensaver-to-lock transition flashes the passwo — the patch declares it closes this ticket
- `C110` `F` patch **9637** → ticket 9628 — Lid-open binding does not restore display brightness after suspe — the patch declares it closes this ticket
- `C111` `F` patch **9653** → ticket 9603 — Bluetooth panel shows the device's raw hardware Name instead of  — the patch declares it closes this ticket
- `C112` `F` patch **9656** → ticket 9643 — Sublime Text install does not expose sublime_text on PATH, so De — the patch declares it closes this ticket
- `C113` `F` patch **9657** → ticket 9648 — Lock screen retries fingerprint auth every 250ms forever with no — the patch declares it closes this ticket
- `C114` `F` patch **9663** → ticket 9705 ⏱ — omarchy-install-hermes-cli readiness probe never passes — --ones — the patch declares it closes this ticket
- `C115` `F` patch **9754** → ticket 9753 — Stale ACPI lid state turns external-monitor hotplug into clamshe — the patch declares it closes this ticket
- `C116` `F` patch **9978** → ticket 9902 — 4.0.x: user ~/.config/hypr/envs.lua is never loaded — user env o — the patch declares it closes this ticket
- `C117` `F` patch **10160** → ticket 7183 — omarchy-font-set: terminal restart notifications never fire — -g — the patch declares it closes this ticket
- `C118` `F` patch **10185** → ticket 10178 — Brave has no speechSynthesis voices on a default Omarchy install — the patch declares it closes this ticket
- `C119` `F` patch **10390** → ticket 10319 — Bar: custom command module with empty "text" renders the raw JSO — the patch declares it closes this ticket
- `C120` `F` patch **10396** → ticket 10243 — sddm.sh strips pam_gnome_keyring.so auth from /etc/pam.d/sddm bu — the patch declares it closes this ticket
- `C121` `F` patch **10408** → ticket 10407 — Screensaver interrupts video playback: the Inhibit portal routes — the patch declares it closes this ticket
- `C122` `F` patch **10416** → ticket 10404 — Cloned service plugins are invisible to firstPartyServiceFor() ( — the patch declares it closes this ticket
- `C123` `F` patch **10476** → ticket 9635 — Calendar grid duplicates September 5 and shifts dates in month v — the patch declares it closes this ticket
- `C124` `F` patch **10510** → ticket 10508 — Tailscale panel: exit node rows show OS hostname instead of Magi — the patch declares it closes this ticket
- `C125` `F` patch **10513** → ticket 10469 — omarchy-chromium-ytdlp-host does not unset LD_PRELOAD from Chrom — the patch declares it closes this ticket
- `C126` `F` patch **10535** → ticket 10526 — Clipboard manager cannot paste images into terminal apps: Shift+ — the patch declares it closes this ticket
- `C127` `F` patch **10570** → ticket 10555 — Monitor scaling changes leave GDK_SCALE stale in the app-launch  — the patch declares it closes this ticket
- `C128` `F` patch **10577** → ticket 10449 — Stock XF86TouchpadToggle binding never fires (Hyprland resolve_b — the patch declares it closes this ticket
- `C129` `F` patch **10588** → ticket 10410 — LIBVA_DRIVER_NAME=nvidia is set even when the NVIDIA GPU drives  — the patch declares it closes this ticket

## Uncertain — no declared link, inferred from content — 90 clusters

Held 6 times out of 18 when checked. **This is the band to actually work.** A patch
that addresses one of a ticket's three findings does not close it.

- `C365` `F` patch **4793** → ticket 7618 — hibernation setup installs keyboard-backlight system-sleep hook  — no direct link to 4793 — every ticket here reaches it through a third one
- `C366` `F` patch **5099** → ticket 4881 — Bug: Layout toggle fails on special workspaces — near-identical titles · 4881 reached only through another ticket, not directly
- `C367` `F` patch **5343** → ticket 5338 — Open in Ghostty gone in Nautilus — no direct link to 5343 — every ticket here reaches it through a third one
- `C368` `F` patch **6333** → ticket 5372 — Brave/Chromium lock up and performance glitches — no direct link to 6333 — every ticket here reaches it through a third one
- `C369` `F` patch **6464** → ticket 7747 — Agents panel: Separate OpenCode usage into its own collector ins — no direct link to 6464 — every ticket here reaches it through a third one
- `C370` `F` patch **6515** → ticket 6519 — Fido 2 authenticator breaks polkit ui experience — no direct link to 6515 — every ticket here reaches it through a third one
- `C371` `F` patch **6663** → ticket 6581 ⏱ — Bar hover feedback loop: tray and indicators oscillate when indi — both quote `/collapse`
- `C372` `F` patch **6767** → ticket 6456 — omarchy update fails at snapshot step when a swapfile is active  — both quote `swapoff`, `swapon`, `omarchy-snapshot`
- `C373` `F` patch **6788** → ticket 6787 ⏱ — `--help` is being skipped for bin routes that partially resolve  — near-identical titles
- `C374` `F` patch **6845** → ticket 6885 — Battery percent in the top bar shows only BAT0 — no direct link to 6845 — every ticket here reaches it through a third one
- `C375` `F` patch **6921** → ticket 10265 — MacBook10,1 internal speakers require CS4208 driver support — both quote `macbook10,1`, `macbook9,1`, `snd_hda_codec_cs420x`
- `C376` `F` patch **6961** → ticket 6355 — Bar widget group / collapsible drawer — near-identical titles · 6355 reached only through another ticket, not directly
- `C377` `F` patch **7020** → ticket 6911 — Quattro upgrade replaces customized monitors.conf with default m — both quote `gdk_scale=2`, `gdk_scale`
- `C378` `F` patch **7063** → ticket 7045 — NVIDIA 50xx Users - Can't Install - Boots to black screen — no direct link to 7063 — every ticket here reaches it through a third one
- `C379` `F` patch **7065** → ticket 6956 — Bluetooth widget disappears from shell when turned off — both quote `rfkill`, `adapter`, `soft-blocked`
- `C380` `F` patch **7167** → ticket 7166 — omarchy-update-available false positive when a pre-release tag e — both quote `v4.0.0-beta3`, `sort -v`, `v4.0.0`
- `C381` `F` patch **7188** → ticket 7184 — Screen recording fails silently on the external monitor of a hyb — both quote `alt + print`, `list-capture-options`, `omarchy_screenrecord_use_portal=true`
- `C382` `F` patch **7225** → ticket 7128 — The agents widget can be added to the bar twice, permanently — no direct link to 7225 — every ticket here reaches it through a third one
- `C383` `F` patch **7259** → ticket 6981 — Plugin hot-reload never picks up changed plugin code (stale QML  — no direct link to 7259 — every ticket here reaches it through a third one
- `C384` `F` patch **7282** → ticket 7281 — Add numpad bindings for workspace navigation on Quattro — near-identical titles
- `C385` `F` patch **7449** → ticket 7233 — Emoji not sent to clipboard — both quote `copy_pid`, `$copy_pid`, `--foreground`
- `C386` `F` patch **7553** → ticket 7522 — omarchy-settings ships a zram-generator config but nothing insta — both quote `zram-generator`
- `C387` `F` patch **7560** → ticket 6991 — Weather plugin: Current location icon() overlaps on the current — no direct link to 7560 — every ticket here reaches it through a third one
- `C388` `F` patch **7598** → ticket 6989 — Quitting the speedtest midway leaves orphan processes — no direct link to 7598 — every ticket here reaches it through a third one
- `C389` `F` patch **7671** → ticket 7672 — BCM43602 Macs only see 2.4 GHz Wi-Fi out of the box — both quote `per-channel`, `dual-band`, `//github.com/csk-grit42`
- `C390` `F` patch **7773** → ticket 5676 — Intel IPU6 MIPI camera Raptor Lake not working — both quote `intel-ipu6-camera-hal-git`
- `C391` `F` patch **7831** → ticket 7003 — RTL8852BE Wi-Fi dead after s2idle; rtw89 resume wedges the chip — both quote `nmcli radio wifi on`, `omarchy-restart-wifi`
- `C392` `F` patch **7839** → ticket 7838 — Proposal: macOS-friendly Tab keybindings (SUPER+TAB for windows, — both quote `super + tab`, `super + shift + tab`, `alt + shift + tab`
- `C393` `F` patch **7857** → ticket 9484 — Surface Book 2 touchscreen dead on stock kernel (needs linux-sur — both quote `linux-surface-headers`, `//github.com/linux-surface/linux-surface`, `linux-surface`
- `C394` `F` patch **7890** → ticket 7881 — Skip incompatible Bun-based agents on CPUs below their instructi — no direct link to 7890 — every ticket here reaches it through a third one
- `C395` `F` patch **7895** → ticket 7374 — Power panel shows UPower's hwdb charge limit (75-80%) instead of — both quote `battery-status-test`
- `C396` `F` patch **7907** → ticket 7481 — Qt.formatDate/Qt.formatDateTime ignore system locale for day/mon — both quote `formatted`
- `C397` `F` patch **7924** → ticket 8868 — Agents bar widget: Codex limits always show "unavailable" (stale — both quote `usagestatustext: "codex limits unavailable`, `account/read`, `/weekly`
- `C398` `F` patch **7945** → ticket 2798 — nautilus takes 25s to start — both quote `org.gnome.nautilus`
- `C399` `F` patch **8017** → ticket 10038 — Hibernate on pre-T2 Intel Macs reboots instead of powering off — both quote `basic-pm-debugging`, `/etc/systemd/sleep.conf.d/hibernatemode.conf`, `//docs.kernel.org/power/basic-pm-debugging.html`
- `C400` `F` patch **8069** → ticket 7949 — SDDM authenticates empty username ("") after interrupted/resumed — both quote `/resumed`, `single-user`
- `C401` `F` patch **8127** → ticket 8126 — Suspend breaks NVIDIA 580xx installs: gpu-screen-recorder sets P — both quote `is handled automatically`, `nvreg_usekernelsuspendnotifiers=1`, `for the proprietary driver or if kernel suspend notifiers are disabled`
- `C402` `F` patch **8145** → ticket 7084 — Clamshell watcher ignores desc: rules for the internal panel and — both quote `output = `
- `C403` `F` patch **8199** → ticket 7619 — hibernation setup cannot repair a half-configured state, and --f — both quote `/etc/limine-entry-tool.d/resume.conf`, `omarchy_resume`, `/etc/mkinitcpio.conf.d/omarchy_resume.conf`
- `C404` `F` patch **8365** → ticket 8248 — OpenSSH daemon bound to all interfaces — both quote `key-only`, `sshd_config`
- `C405` `F` patch **8383** → ticket 7423 — Dropbox widget hides the tray icon without replacing its menu: n — both quote `os.walk`, `dropbox-cli stop`
- `C406` `F` patch **8486** → ticket 7662 — Fingerprint setup misses Broadcom BCM58200 ControlVault 3 (vendo — both quote `product-name`, `fingerprint_vendors`
- `C407` `F` patch **8497** → ticket 6987 — Agents bar widget: Claude collector shows 'Waiting for auth' wit — both quote `authhelptext`
- `C408` `F` patch **8506** → ticket 7721 — omarchy-hyprland-window-pop resizes unconditionally after a floa — both quote `already-floating`
- `C409` `F` patch **8546** → ticket 4891 — Suspend/resume causes compositor freeze on NVIDIA hybrid GPU lap — both quote `systemd-logind`, `systemd-sleep`
- `C410` `F` patch **8588** → ticket 9512 — system-sleep hooks installed by omarchy-hibernation-setup and om — both quote `powered-off`, `bin/omarchy-toggle-hybrid-gpu:63`, `bin/omarchy-hibernation-setup:92`
- `C411` `F` patch **8685** → ticket 6878 — Quattro upgrade drops non-US keyboard layout when vconsole.conf  — both quote `/etc/vconsole.conf`
- `C412` `F` patch **8739** → ticket 7418 — Cloning the bar plugin blanks the bar (broken Loader.Error fallb — no direct link to 8739 — every ticket here reaches it through a third one
- `C413` `F` patch **8773** → ticket 7399 — Lock screen re-blanks ~1s after DPMS wake on slow-sync monitor,  — no direct link to 8773 — every ticket here reaches it through a third one
- `C414` `F` patch **8793** → ticket 8725 — Error mounting an external hard drive — no direct link to 8793 — every ticket here reaches it through a third one
- `C415` `F` patch **8801** → ticket 3864 — Helium browser them switching via policies no longer works. — no direct link to 8801 — every ticket here reaches it through a third one
- `C416` `F` patch **8820** → ticket 8290 — [Quattro] Screen lock moves the default audio sink to the intern — no direct link to 8820 — every ticket here reaches it through a third one
- `C417` `F` patch **8888** → ticket 6876 — omarchy_hooks.conf replaces HOOKS instead of extending it, dropp — both quote `resume`
- `C418` `F` patch **8895** → ticket 7679 — Low battery notification can fire on boot after resuming from a  — both quote `time to recharge!`, `low-battery`
- `C419` `F` patch **8947** → ticket 8475 — Missing gst-libav, gst-plugins-bad and gst-plugins-ugly — no direct link to 8947 — every ticket here reaches it through a third one
- `C420` `F` patch **9011** → ticket 8998 — 1Password window is not visible when accessing desktop over suns — both quote `/sunshine`
- `C421` `F` patch **9040** → ticket 7174 — First-agent OAuth browser opens tiled under the 875×600 setup te — both quote `omarchy-launch-browser`
- `C422` `F` patch **9130** → ticket 7371 — SUPER+C/V/X universal clipboard shortcuts fail with "send_key_st — both quote `send_key_state: key not found`
- `C423` `F` patch **9131** → ticket 6992 — omarchy-upgrade-to-quattro enables bt-agent.service but orphans  — both quote `bluetooth.service`, `execcondition`
- `C424` `F` patch **9161** → ticket 7588 — Web app installer saves non-PNG icons with a .png extension — no direct link to 9161 — every ticket here reaches it through a third one
- `C425` `F` patch **9343** → ticket 7019 — Cannot run Migration (1786643346) because an "browser window is  — no direct link to 9343 — every ticket here reaches it through a third one
- `C426` `F` patch **9456** → ticket 7172 — Lock screen fingerprint retry livelocks after resume: overlappin — both quote `handlefingerprintfinished`
- `C427` `F` patch **9573** → ticket 9569 — omarchy-remove-gaming-heroic leaves ~/.config/heroic behind ($HO — both quote `omarchy-apply-lock`
- `C428` `F` patch **9641** → ticket 10050 — Default Voxtype type mode can corrupt longer Japanese/CJK dictat — both quote `//github.com/peteonrails/voxtype/issues/695`, `paste`, `//github.com/atx/wtype/issues/71`
- `C429` `F` patch **9651** → ticket 6947 — Steam idle-inhibit rule matches the client but not steam_app gam — both quote `steam`
- `C430` `F` patch **9757** → ticket 9029 — Menu blocks on-screen keyboard input: Exclusive keyboard focus r — both quote `exclusionmode.ignore`, `/keyboardpanel.qml`, `ui/keyboardpanel.qml`
- `C431` `F` patch **9959** → ticket 9914 — quickshell SIGSEGV in VDMListDelegateDataType::createMissingProp — both quote `cachedaudiosinks`, `displayaudiosinks`, `rawaudiosinks`
- `C432` `F` patch **9972** → ticket 7635 — Bar: every inline command module logs TypeError: Cannot assign t — both quote `modulename" in target`, `customcommandmodule`, `injectprops`
- `C433` `F` patch **9988** → ticket 7556 — SUPER+J runs dwindle-only togglesplit on scrolling workspaces — both quote `get_active_workspace`, `tiled_layout`, `no such layoutmsg for scrolling`
- `C434` `F` patch **10065** → ticket 8352 — Hibernation resume fails on hybrid Intel+NVIDIA laptops — nvidia — both quote `modules+=`, `resume-from-hibernate`
- `C435` `F` patch **10113** → ticket 10114 — windows vm launch fails when ~/Windows is empty (dockur sets sha — near-identical titles
- `C436` `F` patch **10115** → ticket 9361 — Critical notifications have no visible close button and never au — both quote `auto-expiring`, `remaininglifetime`
- `C437` `F` patch **10130** → ticket 7749 — [Quattro] Lock screen re-blanks slow DPMS monitors after fixed 5 — both quote `armblanktimer`
- `C438` `F` patch **10146** → ticket 7834 — Notification replacement hints honoured by mako are ignored by t — both quote `replaces_id`
- `C439` `F` patch **10184** → ticket 4070 — Cannot record audio via built in stereo microphone — no direct link to 10184 — every ticket here reaches it through a third one
- `C440` `F` patch **10200** → ticket 7810 — omarchy default editor <gui-editor> does not update XDG MIME def — both quote `omarchy default editor code`, `code-workspace`, `application/x-code-workspace`
- `C441` `F` patch **10257** → ticket 10255 — omarchy-debug output includes unredacted LAN IPs and MAC address — both quote `/config/firewall.sh`, `install/config/firewall.sh`, `ufw block`
- `C442` `F` patch **10388** → ticket 7025 — omarchy-menu-keybindings hangs forever when a user Lua config it — both quote `__index`, `ipairs`
- `C443` `F` patch **10391** → ticket 8189 — Cloned bar plugin (kind: bar) never renders — required propertie — no direct link to 10391 — every ticket here reaches it through a third one
- `C444` `F` patch **10430** → ticket 1434 — Hyprsunset is reset when/after screen locks — no direct link to 10430 — every ticket here reaches it through a third one
- `C445` `F` patch **10490** → ticket 9904 — 1Password: unlock popup unusable on fractional scaling, and its  — both quote `no_screen_share`
- `C446` `F` patch **10530** → ticket 3224 — Numlock problem after boot and suspend — no direct link to 10530 — every ticket here reaches it through a third one
- `C447` `F` patch **10547** → ticket 10546 — Shell wedges alive while idle-locked: IPC keeps serving stale lo — both quote `crashed-lockscreen`
- `C448` `F` patch **10623** → ticket 7022 — omarchy toggle bar on/off has inverted semantics (hides bar on ' — no direct link to 10623 — every ticket here reaches it through a third one
- `C449` `F` patch **10639** → ticket 8547 — Quickshell SIGSEGV tearing down the workspaces Repeater when Hyp — both quote `hyprlandworkspace`, `mid-mutation`, `valueschanged`
- `C450` `F` patch **10697** → ticket 7624 — Light themes render the Chromium tab strip bright yellow — both quote `near-white`, `#fffcf0`, `max-min`
- `C451` `F` patch **10707** → ticket 7835 — I am trying to install and run Omarchy inside VMware, but I cons — no direct link to 10707 — every ticket here reaches it through a third one
- `C452` `F` patch **10708** → ticket 10700 — Silent lock-screen login loop when ~/.config/uwsm/env.d has a sh — both quote `~/.config/uwsm/env.d/`
- `C453` `F` patch **10757** → ticket 10735 — omarchy-network-speedtest leaves orphaned curl workers running a — both quote `*.oca.nflxvideo.net`, `trap cleanup exit`, `cleanup`
- `C454` `F` patch **10758** → ticket 10593 — Suspend/resume support for vintage MacBook Pro 13" 2017 (MacBook — both quote `config-space`

---

Generated 2026-09-08 from the open queue of omacom/omarchy as of 2026-09-07 21:14,
re-checked against live GitHub on 2026-09-08. Nothing was posted.

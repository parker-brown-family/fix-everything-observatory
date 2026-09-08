# Collapse plan — omacom/omarchy open queue

Generated 2026-09-07T20:30:54 from 2000 sampled open items (1000 newest open issues + 1000 newest open PRs (GitHub search ceiling)).

Nothing in this file has been posted anywhere. Each entry is a candidate collapse:
one surface, several tickets, and the evidence that binds them.

- clusters: **371**
- items inside a cluster: **939** of 2000 (47%)
- redundant items the collapse would remove: **568**
- clusters with two or more distinct low-smell reporters: **252** (surplus 432)

## The twenty biggest candidates

### Cloned bar plugin (kind: bar) never renders — required properties not passed by pluginBarLoader

**16 items** (13 issues, 3 PRs) · 13 authors, 13 low-smell · edges: text×17, mentions×5, closes×3 · median similarity 0.591

Anchor: #8189 (oldest). Members:

- iss #8189 — Cloned bar plugin (kind: bar) never renders — required properties not passed by pluginBarLoader — @Orneyfish
- iss #8202 — Third-party bar plugins: a cloned bar can never load, and user plugin QML does not hot-reload — @epicbagel
- iss #8775 — omarchy plugin clone omarchy.bar leaves the shell with no bar, and the fallback path throws — @quigles1977
- iss #9115 — Cloned omarchy.bar cannot load as a bar option: required properties never initialized by pluginBarLoader — @hshshshs12
- iss #9116 — Failed bar option leaves no bar at all: pluginBarLoader error handler throws ReferenceError before the fallbac — @hshshshs12
- iss #9136 — Cloning the top-level bar plugin (omarchy.bar) breaks the bar on all monitors — @Santym8
- PR  #9219 — Never let bar and panel error diagnostics block their fallbacks — @DeanWahle
- iss #9588 — Cloning the bar plugin leaves the system with no bar (required properties + broken error fallback) — @aspinalljohn
- iss #9593 — Cloned bar plugin never loads: required properties are never set — @Yves848
- iss #9599 — Cloning omarchy.bar (or any third-party kind: bar plugin) never renders — required properties + broken Loader. — @cubicruler
- iss #10324 — Custom bar load failure can't fall back: pluginBarLoader.onStatusChanged throws ReferenceError on errorString — @tinterian
- iss #10325 — omarchy plugin clone omarchy.bar produces a plugin that can never load (required properties) — @tinterian
- PR  #10389 — Record a failed custom bar so the default bar can load — @calledtoconstruct
- PR  #10391 — Allow cloned bar plugins to receive host properties after load — @calledtoconstruct
- iss #10556 — Custom "bar" plugin fails to load — cloning the built-in bar (omarchy plugin clone omarchy.bar) breaks the she — @toppzi
- iss #10745 — Custom bar/panel plugins fail silently — ReferenceError in Loader error handler swallows the diagnostic and sk — @ltehacker

> Draft comment (not posted):
>
> These look like one surface. #8189 is the oldest report; 15 other open items describe the same failure (#8202, #8775, #9115, #9116, #9136, #9219, #9588, #9593, #9599, #10324, #10325, #10389, #10391, #10556, #10745). Evidence: text×17, mentions×5, closes×3. Proposing they collapse onto #8189, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### omarchy-agent-usage-codex: Codex limits always empty ('Codex limits unavailable') on Codex >=0.13

**9 items** (8 issues, 1 PRs) · 9 authors, 9 low-smell · edges: text×17, mentions×3, closes×1 · median similarity 0.591

Anchor: #8656 (oldest). Members:

- iss #8656 — omarchy-agent-usage-codex: Codex limits always empty ('Codex limits unavailable') on Codex >=0.13 — @lasurius
- iss #8868 — Agents bar widget: Codex limits always show "unavailable" (stale --ask-for-approval value) — @abduvaliy-hbai
- iss #8971 — agents: Codex limits break with codex-cli >= 0.151.0 (invalid '-a untrusted') — @Daz92
- PR  #8977 — Fix Codex limits collector for CLI approval-policy churn — @fresh3nough
- iss #9247 — Agents widget: Codex limits never load — collector passes removed `-a untrusted` to app-server — @emergencerising-maker
- iss #9283 — omarchy-agent-usage-codex: hardcoded --ask-for-approval value 'untrusted' rejected by current codex-cli — @sal-he
- iss #9357 — omarchy-agent-usage-codex: RPC probe fails on current Codex CLI (-a untrusted no longer valid) — @ddiall
- iss #10242 — Codex usage widget shows initialize after Codex CLI 0.150.0 update — @tycameron
- iss #10727 — omarchy-agent-usage-codex passes a removed --ask-for-approval value, so Codex limits never load — @CougarM

> Draft comment (not posted):
>
> These look like one surface. #8656 is the oldest report; 8 other open items describe the same failure (#8868, #8971, #8977, #9247, #9283, #9357, #10242, #10727). Evidence: text×17, mentions×3, closes×1. Proposing they collapse onto #8656, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### omarchy update -y hangs on the orphaned-packages prompt

**9 items** (4 issues, 5 PRs) · 7 authors, 5 low-smell · edges: mentions×8, closes×4, files×4 · median similarity 0.278

Anchor: #8780 (oldest). Members:

- iss #8780 — omarchy update -y hangs on the orphaned-packages prompt — @PixelatedContinuum
- PR  #8824 — Skip orphan prompt during unattended updates — @maxcroy1
- PR  #8894 — Skip the orphan prompt when omarchy update runs with -y — @Chessing234 ·smell2
- iss #8986 — `omarchy update -y` can block at the post-update reboot prompt — @maxcroy1
- PR  #8992 — Skip reboot prompts in unattended updates — @maxcroy1
- iss #9501 — Support non-interactive updates: omarchy update --yes flag — @hummbl-dev
- PR  #9511 — Support non-interactive updates with --yes — @zerone0x ·smell2
- iss #10021 — Fold third-party plugin updates into omarchy update and add an Update Plugins menu entry — @dmltallen
- PR  #10714 — Review third-party plugin updates during interactive system updates — @yashranaway

> Draft comment (not posted):
>
> These look like one surface. #8780 is the oldest report; 8 other open items describe the same failure (#8824, #8894, #8986, #8992, #9501, #9511, #10021, #10714). Evidence: mentions×8, closes×4, files×4. Proposing they collapse onto #8780, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Omarchy 'omarchy update'

**8 items** (4 issues, 4 PRs) · 7 authors, 7 low-smell · edges: mentions×8, closes×5, text×4, files×2 · median similarity 0.444

Anchor: #8239 (oldest). Members:

- iss #8239 — Omarchy 'omarchy update' — @helioryn
- iss #8369 — omarchy-update-dev crashes with "unbound variable" on $OMARCHY_PATH under sudo — @edhcah
- iss #8769 — omarchy-update-available has the same unbound $OMARCHY_PATH crash as #8369, and it silently clears the update  — @tpatzelt
- PR  #8771 — Default OMARCHY_PATH in omarchy-update-available — @tpatzelt
- PR  #9164 — Default OMARCHY_PATH in channel-current and audio-tuning; add env-robustness test (#8769) — @kfchai
- iss #9953 — sudo omarchy update aborts with "OMARCHY_PATH: unbound variable" in omarchy-update-dev — @MaurizioFaeddaDev
- PR  #9966 — Default OMARCHY_PATH in update-dev for sudo env_reset — @fresh3nough
- PR  #9980 — Survive an unset OMARCHY_PATH in the update pipeline — @omarchybot

> Draft comment (not posted):
>
> These look like one surface. #8239 is the oldest report; 7 other open items describe the same failure (#8369, #8769, #8771, #9164, #9953, #9966, #9980). Evidence: mentions×8, closes×5, text×4, files×2. Proposing they collapse onto #8239, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### omarchy-menu-keybindings: Lua config scan hangs forever (100% CPU) if hyprland.lua calls any un-stubbed hl.* f

**8 items** (4 issues, 4 PRs) · 7 authors, 7 low-smell · edges: mentions×6, text×3, closes×1 · median similarity 0.511

Anchor: #8819 (oldest). Members:

- iss #8819 — omarchy-menu-keybindings: Lua config scan hangs forever (100% CPU) if hyprland.lua calls any un-stubbed hl.* f — @LukaszWituch
- PR  #8876 — Stop keybinding scans from looping on mocked APIs — @yashranaway
- iss #9052 — omarchy-menu-keybindings (Super+K) hangs at 100% CPU when a Lua config calls ipairs(hl.get_*()) — @FernandoJVideira
- iss #9395 — omarchy-menu-keybindings: Infinite loop during cache generation due to ipairs on noop object — @rendarth
- PR  #10212 — Fix keybindings menu hang when user configs iterate hl accessors — @evariste1963
- iss #10214 — omarchy-menu-keybindings hangs (100% CPU) when a user config iterates hl.get_loaded_plugins() — @evariste1963
- PR  #10388 — Stop the keybindings scanner spinning on hl list accessors — @calledtoconstruct
- PR  #10562 — Prevent infinite loop when parsing Lua binds with ipairs — @monkonthehill

> Draft comment (not posted):
>
> These look like one surface. #8819 is the oldest report; 7 other open items describe the same failure (#8876, #9052, #9395, #10212, #10214, #10388, #10562). Evidence: mentions×6, text×3, closes×1. Proposing they collapse onto #8819, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### fix(toggle): invert on/off semantics in omarchy-toggle-bar

**8 items** (3 issues, 5 PRs) · 8 authors, 5 low-smell · edges: mentions×4, closes×4, text×3 · median similarity 0.502

Anchor: #9102 (oldest). Members:

- PR  #9102 — fix(toggle): invert on/off semantics in omarchy-toggle-bar — @harshithnadig ·smell1
- iss #9323 — omarchy toggle bar on/off arguments are inverted — 'on' hides the bar — @brendanhalfpenny
- PR  #9369 — Stop inverting the on/off argument to omarchy toggle bar — @Chessing234
- PR  #9455 — Fix inverted on/off arguments in omarchy toggle bar — @perryqh ·smell2
- iss #9925 — omarchy toggle bar on/off has inverted semantics — @curtisc ·smell2
- PR  #9970 — Map toggle bar on/off to visible bar state — @fresh3nough ·smell2
- iss #10621 — omarchy toggle bar on/off arguments are inverted — @macbe
- PR  #10623 — Fix explicit bar toggle direction — @Drecullith

> Draft comment (not posted):
>
> These look like one surface. #9102 is the oldest report; 7 other open items describe the same failure (#9323, #9369, #9455, #9925, #9970, #10621, #10623). Evidence: mentions×4, closes×4, text×3. Proposing they collapse onto #9102, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Low battery notification can fire on boot after resuming from a suspend that drained the battery (Quickshell r

**7 items** (3 issues, 4 PRs) · 7 authors, 6 low-smell · edges: mentions×4, closes×3, files×3 · median similarity 0.407

Anchor: #7679 (oldest). Members:

- iss #7679 — Low battery notification can fire on boot after resuming from a suspend that drained the battery (Quickshell r — @LorenGrz
- iss #8813 — Low-battery notification remains after charger is connected — @pixelpush-io
- PR  #8838 — Dismiss the low battery warning when charging resumes — @Eyasuk
- PR  #8895 — Clear the low-battery toast when the charger is connected — @Chessing234 ·smell2
- iss #9670 — Low-battery warning storm: notification every ~3s when AC online status flaps (latch resets on onBatteryChange — @calumol
- PR  #9883 — Keep low-battery latch across AC online flaps — @fresh3nough
- PR  #10081 — Latch the low-battery warning until the battery recovers — @djbarrios

> Draft comment (not posted):
>
> These look like one surface. #7679 is the oldest report; 6 other open items describe the same failure (#8813, #8838, #8895, #9670, #9883, #10081). Evidence: mentions×4, closes×3, files×3. Proposing they collapse onto #7679, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Super+J (togglesplit) errors on scrolling layout: 'no such layoutmsg for scrolling'

**7 items** (4 issues, 3 PRs) · 7 authors, 6 low-smell · edges: text×4, mentions×3, closes×2 · median similarity 0.586

Anchor: #8220 (oldest). Members:

- iss #8220 — Super+J (togglesplit) errors on scrolling layout: 'no such layoutmsg for scrolling' — @khru
- iss #8993 — SUPER + J errors on scrolling-layout workspaces — @seth-wood
- iss #9146 — [Bug] Super+J dispatches unsupported togglesplit in Scrolling workspaces — @robinwibom
- PR  #9165 — fix(hypr): route Super+J through split-toggle helper to prevent crash on scrolling workspaces — @harshithnadig ·smell1
- PR  #9704 — Make Super + J flip the axis on scrolling workspaces — @xymbol
- iss #9726 — SUPER + J (togglesplit) raises "no such layoutmsg for scrolling" on scrolling-layout workspaces — @johnwu
- PR  #9988 — No-op dwindle-only tiling binds on scrolling workspaces — @fresh3nough ·smell2

> Draft comment (not posted):
>
> These look like one surface. #8220 is the oldest report; 6 other open items describe the same failure (#8993, #9146, #9165, #9704, #9726, #9988). Evidence: text×4, mentions×3, closes×2. Proposing they collapse onto #8220, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### omarchy-theme-set-browser hangs when brave-origin is running but Brave is not (pgrep -x brave false-positive)

**6 items** (4 issues, 2 PRs) · 6 authors, 6 low-smell · edges: mentions×4, closes×2, text×2 · median similarity 0.444

Anchor: #8158 (oldest). Members:

- iss #8158 — omarchy-theme-set-browser hangs when brave-origin is running but Brave is not (pgrep -x brave false-positive) — @patterninterrupt
- iss #8212 — omarchy-update hangs at migration 1787481315 when brave-origin is the daily browser (theme-set-browser blocks  — @sivaxreddy
- PR  #9423 — Bound the browser policy refresh so a wedged browser can't stall an update — @VykosMolt
- iss #10636 — omarchy-theme-set-browser hangs even when the pgrep guard is a true positive: Chromium running, `--refresh-pla — @hiendinhngoc
- PR  #10645 — Fix/browser policy refresh timeout — @chivopic
- iss #10666 — omarchy-theme-set-browser hangs (and stalls omarchy update) when brave-bin is installed but only Brave Origin  — @bierlingm

> Draft comment (not posted):
>
> These look like one surface. #8158 is the oldest report; 5 other open items describe the same failure (#8212, #9423, #10636, #10645, #10666). Evidence: mentions×4, closes×2, text×2. Proposing they collapse onto #8158, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Battery panel only reads one battery on dual-battery laptops (e.g. ThinkPad T580)

**6 items** (3 issues, 3 PRs) · 6 authors, 5 low-smell · edges: text×4, mentions×3, closes×3 · median similarity 0.565

Anchor: #8521 (oldest). Members:

- iss #8521 — Battery panel only reads one battery on dual-battery laptops (e.g. ThinkPad T580) — @Dhruv-145
- iss #9026 — Power panel percentage ignores second battery on dual-battery laptops — @SilviuManeaDev
- PR  #9106 — fix(battery): aggregate percentage and telemetry across dual-battery setups — @harshithnadig ·smell1
- iss #10244 — omarchy-battery-status reports wrong percentage on dual-battery laptops (reads only BAT0) — @nick-terrant
- PR  #10384 — Read battery aggregate from UPower DisplayDevice — @fresh3nough ·smell2
- PR  #10392 — Report combined battery percentage from UPower DisplayDevice — @calledtoconstruct

> Draft comment (not posted):
>
> These look like one surface. #8521 is the oldest report; 5 other open items describe the same failure (#9026, #9106, #10244, #10384, #10392). Evidence: text×4, mentions×3, closes×3. Proposing they collapse onto #8521, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### windows-vm: chmod 0700 preserves directory setgid bit, causing launch to fail safety check

**6 items** (3 issues, 3 PRs) · 6 authors, 6 low-smell · edges: mentions×5, closes×5 · median similarity 0.244

Anchor: #9374 (oldest). Members:

- iss #9374 — windows-vm: chmod 0700 preserves directory setgid bit, causing launch to fail safety check — @VillainRU
- iss #9540 — omarchy-windows-vm install: fails to write config when mount source dir has setgid bit (chmod 0700 doesn't cle — @evanhfw
- PR  #9564 — Clear set-ID bits from Windows VM mount sources — @aiqubits
- iss #9567 — omarchy-windows-vm launch fails silently when ~/Windows has the setgid bit (numeric chmod can't clear it) — @andyxqq
- PR  #9605 — Clear set-ID bits when securing the Windows VM mount sources — @omarchybot
- PR  #10046 — Clear set-ID bits on Windows VM directories — @0bsolescence

> Draft comment (not posted):
>
> These look like one surface. #9374 is the oldest report; 5 other open items describe the same failure (#9540, #9564, #9567, #9605, #10046). Evidence: mentions×5, closes×5. Proposing they collapse onto #9374, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Fingerprint setup misses Broadcom BCM58200 ControlVault 3 (vendor 0a5c not in detection list)

**5 items** (4 issues, 1 PRs) · 5 authors, 5 low-smell · edges: text×5, mentions×1, closes×1 · median similarity 0.607

Anchor: #7662 (oldest). Members:

- iss #7662 — Fingerprint setup misses Broadcom BCM58200 ControlVault 3 (vendor 0a5c not in detection list) — @bartcho
- iss #8483 — omarchy-hw-fingerprint doesn't detect Broadcom (0a5c) fingerprint sensors — @gbillium143
- iss #8562 — omarchy-hw-fingerprint doesn't detect Dell ControlVault 3 (Broadcom 0a5c:5843) — @VardanMelkonyan
- iss #9507 — omarchy-hw-fingerprint doesn't detect Dell ControlVault 3 (Broadcom BCM58200, vendor 0a5c) — @JeronimoColon
- PR  #9524 — Detect Broadcom ControlVault 3 fingerprint readers — @qybaihe

> Draft comment (not posted):
>
> These look like one surface. #7662 is the oldest report; 4 other open items describe the same failure (#8483, #8562, #9507, #9524). Evidence: text×5, mentions×1, closes×1. Proposing they collapse onto #7662, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### `pending-charge` treated as a charge-limit hold without checking the level: a failed battery reports "Holding 

**5 items** (3 issues, 2 PRs) · 3 authors, 3 low-smell · edges: mentions×4, closes×2, text×1 · median similarity 0.344

Anchor: #7803 (oldest). Members:

- iss #7803 — `pending-charge` treated as a charge-limit hold without checking the level: a failed battery reports "Holding  — @xeeg
- iss #10193 — Power panel invents a "Charge limit / Holding" state on hardware with no charge-control support — @gabamnml
- PR  #10196 — Require a real charge threshold before reporting a held charge — @gabamnml
- iss #10344 — Battery panel ignores charge_control_end_threshold and misreports the charge limit — @brightwalker25
- PR  #10502 — Decide the charge limit from the threshold, not the charge level — @brightwalker25

> Draft comment (not posted):
>
> These look like one surface. #7803 is the oldest report; 4 other open items describe the same failure (#10193, #10196, #10344, #10502). Evidence: mentions×4, closes×2, text×1. Proposing they collapse onto #7803, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### I am trying to install and run Omarchy inside VMware, but I consistently get a black screen after entering my 

**5 items** (4 issues, 1 PRs) · 5 authors, 5 low-smell · edges: mentions×4 · median similarity 0.333

Anchor: #7835 (oldest). Members:

- iss #7835 — I am trying to install and run Omarchy inside VMware, but I consistently get a black screen after entering my  — @cn0xroot
- iss #8113 — Omarchy unusable under VMware Workstation with 3D acceleration enabled — @cavanaug
- iss #8604 — omarchy黑屏问题 — @12-test-12
- iss #10620 — VMware guest: installer leaves the system without open-vm-tools (live ISO has them); plus working fix for the  — @kevincasier
- PR  #10707 — Install guest tools on VMware systems — @yashranaway

> Draft comment (not posted):
>
> These look like one surface. #7835 is the oldest report; 4 other open items describe the same failure (#8113, #8604, #10620, #10707). Evidence: mentions×4. Proposing they collapse onto #7835, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev rules pointing at ~/.local/share/omarchy; remo

**5 items** (3 issues, 2 PRs) · 5 authors, 4 low-smell · edges: mentions×5, closes×2, text×1 · median similarity 0.363

Anchor: #8173 (oldest). Members:

- iss #8173 — Quattro upgrade leaves ~/.XCompose and the Omarchy 3 power udev rules pointing at ~/.local/share/omarchy; remo — @fuchsblau
- iss #9241 — install/user/xcompose.sh writes an absolute /usr/share/omarchy include, breaking every compose sequence inside — @Marjinoz
- PR  #9282 — Point XCompose at a home-local table for sandboxed apps — @fresh3nough
- iss #9541 — XCompose migrations restart fcitx5 and can crash running Steam — @cking-bot
- PR  #9568 — Defer XCompose reloads from migrations — @rookepoole ·smell2

> Draft comment (not posted):
>
> These look like one surface. #8173 is the oldest report; 4 other open items describe the same failure (#9241, #9282, #9541, #9568). Evidence: mentions×5, closes×2, text×1. Proposing they collapse onto #8173, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Regression: Quickshell workspace indicator shows globally focused workspace on every monitor

**5 items** (3 issues, 2 PRs) · 5 authors, 5 low-smell · edges: mentions×7, closes×3 · median similarity 0.256

Anchor: #8183 (oldest). Members:

- iss #8183 — Regression: Quickshell workspace indicator shows globally focused workspace on every monitor — @NeroSong
- iss #8364 — Workspace indicator shows wrong active workspace when switching between monitors — @Dhxnushh
- PR  #8997 — Highlight each monitor's own active workspace in the bar — @mikebenner
- iss #10187 — Workspace highlight stays on the destination monitor's old workspace after moving a workspace between monitors — @sedulam
- PR  #10190 — Fix workspace indicator after monitor move — @dzanaga

> Draft comment (not posted):
>
> These look like one surface. #8183 is the oldest report; 4 other open items describe the same failure (#8364, #8997, #10187, #10190). Evidence: mentions×7, closes×3. Proposing they collapse onto #8183, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Hibernation resume fails on hybrid Intel+NVIDIA laptops — nvidia.sh's early-KMS module bundling races the resu

**5 items** (4 issues, 1 PRs) · 4 authors, 4 low-smell · edges: mentions×5, closes×1 · median similarity 0.238

Anchor: #8352 (oldest). Members:

- iss #8352 — Hibernation resume fails on hybrid Intel+NVIDIA laptops — nvidia.sh's early-KMS module bundling races the resu — @bcelary
- iss #10037 — omarchy hibernation remove leaves /etc/limine-entry-tool.d/resume.conf behind, so the rebuilt UKI still boots  — @brenodyego
- iss #10039 — Hibernate resume fails (nv_pmops_freeze → -EIO) on single-NVIDIA-GPU desktops — initramfs nvidia load blocks t — @unconnect
- iss #10061 — Hibernate restore hangs on iMac17,1 (amdgpu Bonaire/CIK), and every Limine entry carries resume= — no bootable — @madakas
- PR  #10065 — Hibernation: keep native GPU drivers out of the initramfs so resume runs before any GPU driver touches the har — @madakas

> Draft comment (not posted):
>
> These look like one surface. #8352 is the oldest report; 4 other open items describe the same failure (#10037, #10039, #10061, #10065). Evidence: mentions×5, closes×1. Proposing they collapse onto #8352, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Tag brave-origin windows as chromium-based browsers

**5 items** (2 issues, 3 PRs) · 5 authors, 5 low-smell · edges: mentions×5, closes×2, text×1 · median similarity 0.369

Anchor: #8968 (oldest). Members:

- PR  #8968 — Tag brave-origin windows as chromium-based browsers — @Rastafaustian
- iss #9274 — Vivaldi misses the chromium-based-browser tag: browser.lua regex spells the class "Vivaldi-stable", real class — @maTzko13
- PR  #9279 — Tag Vivaldi's window class case-insensitively in browser.lua — @reverb256
- iss #9784 — Web apps never get the chromium-based-browser tag: browser.lua patterns assume substring matching, Hyprland us — @RiccardoBelli
- PR  #9882 — Tag Chromium --app web apps as chromium-based browsers — @fresh3nough

> Draft comment (not posted):
>
> These look like one surface. #8968 is the oldest report; 4 other open items describe the same failure (#9274, #9279, #9784, #9882). Evidence: mentions×5, closes×2, text×1. Proposing they collapse onto #8968, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### omarchy-launch-or-focus / omarchy-launch-spotify match window titles, so any window with the app name in its t

**5 items** (2 issues, 3 PRs) · 5 authors, 4 low-smell · edges: files×3, mentions×2, closes×2 · median similarity 0.302

Anchor: #9544 (oldest). Members:

- iss #9544 — omarchy-launch-or-focus / omarchy-launch-spotify match window titles, so any window with the app name in its t — @chriguschneider
- PR  #9614 — omarchy #9544 launch-or-focus agent titles (fork PR) — @kvnloo
- iss #9901 — omarchy-launch-spotify does nothing when quickshell.spotify is running — @drithird
- PR  #9927 — Avoid focusing Quickshell plugin windows — @imzihuailin
- PR  #9987 — Ignore quickshell surfaces when matching launch windows — @fresh3nough ·smell2

> Draft comment (not posted):
>
> These look like one surface. #9544 is the oldest report; 4 other open items describe the same failure (#9614, #9901, #9927, #9987). Evidence: files×3, mentions×2, closes×2. Proposing they collapse onto #9544, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

### Lid-open binding does not restore display brightness after suspend

**5 items** (3 issues, 2 PRs) · 5 authors, 4 low-smell · edges: mentions×4, closes×1 · median similarity 0.421

Anchor: #9628 (oldest). Members:

- iss #9628 — Lid-open binding does not restore display brightness after suspend — @BjornB2
- PR  #9637 — Restore brightness when the laptop lid opens — @fresh3nough
- iss #10170 — Laptop with no external monitor has no path from lid-open to dpms enable: panel stays dark after resume — @EitanSchuler
- iss #10250 — ThinkPad X1 Carbon Gen 14: lid s2idle never wakes; hibernate reboots; lid-open leaves panel dark — @heredia21
- PR  #10462 — Wake the panel when a laptop-only lid opens — @codemonkey76 ·smell2

> Draft comment (not posted):
>
> These look like one surface. #9628 is the oldest report; 4 other open items describe the same failure (#9637, #10170, #10250, #10462). Evidence: mentions×4, closes×1. Proposing they collapse onto #9628, with the strongest patch kept and the rest closed as duplicates once a maintainer confirms the surface is one thing.

## Invalidation test

The brief promised this check: compute the ranking with and without agent-smelling
reporters, and if the top twenty is the same list either way, agent inflation is not
material and the identity-dedupe can be dropped.

- overlap of the top twenty, with and without agent authors: **20/20**
- clustered items authored by something that smells agentic: **102** of 939
- clusters surviving a two-distinct-human-reporters requirement: **252** of 371

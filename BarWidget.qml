import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// The linter cannot see Quickshell's C++ type registration nor the dynamic
// members of the theme singletons (Color.*, Style.*) — first-party widgets
// score dozens of warnings in exactly these categories under the identical
// invocation, so this is the tool's blind spot, not this file's. Disabled
// file-wide below; every other check still runs.
// qmllint disable uncreatable-type missing-property unqualified

// Fix-Everything Observatory — the swarm chip.
//
// One glyph in the bar; a click opens the observatory. The heavy surface —
// the scrubbable swarm, the flow diagram, the ticket inspector — is a browser
// page served by this plugin's own local server (observatory.py, bound to
// 127.0.0.1), so the widget's whole job is to make sure that server is up and
// put the page on screen. That is one detached run of the launcher script;
// everything else in this file is bar furniture.
//
// The launcher is resolved from this plugin's own directory, wherever that
// is — a git-managed install under ~/.config/omarchy/plugins or a dev symlink
// into a working tree. Qt.resolvedUrl(".") is the one authority on where this
// QML file loaded from, so the path is derived, never configured.
//
// Everything lives in this ONE file on purpose: the QML engine currently
// refuses to load a second .qml entry point from a third-party plugin dir,
// while the bar-widget entry loads fine (same constraint the other
// brownfamilysports widgets ship under).
BarWidget {
  id: root
  moduleName: "brownfamilysports.observatory"

  // The vertical bar needs no second face (taste-ok: vertical): the whole
  // surface is one emoji glyph, equally legible in either orientation, and
  // WidgetButton already sizes its slot per bar.vertical.

  // file:///…/plugins/brownfamilysports.observatory/ → /…/plugins/…/
  readonly property string pluginDir: {
    var url = Qt.resolvedUrl(".").toString()
    return url.indexOf("file://") === 0 ? decodeURIComponent(url.substring(7)) : url
  }

  // Off by default, and only ever turned on by a person in the widget's
  // settings: the server the chip launches refuses /api/allocate without the
  // matching environment flag, and the page never renders the ALLOCATE AGENT
  // button against a server that refuses it. The flag rides the launch, so a
  // change here applies from the next server start — an already-running
  // server keeps the posture it was born with rather than being reconfigured
  // over an unauthenticated local socket.
  readonly property bool allowAgents: setting("allowAgentAllocation", false)

  function openObservatory() {
    var launcher = root.pluginDir + "bin/fix-everything-observatory"
    var cmd = root.allowAgents
      ? ["env", "FIX_OBSERVATORY_ALLOW_AGENTS=1", launcher, "open"]
      : [launcher, "open"]
    Quickshell.execDetached(cmd)
  }

  // The popup contract (Bar.findPanelWidget): open/close/opened on the root
  // is what makes `omarchy-shell shell summon brownfamilysports.observatory`
  // — and with it any Hyprland keybind — reach this widget. There is no QML
  // panel to hold open, so "summon" means the same thing as a click and
  // opened never sticks.
  property bool opened: false
  function open() { root.openObservatory() }
  function close() {}

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  IpcHandler {
    target: "brownfamilysports.observatory"

    function open(): void { root.openObservatory() }
    function show(): void { root.openObservatory() }
    function toggle(): void { root.openObservatory() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "🌀"
    tooltipText: "Fix-Everything Observatory — the omarchy repair swarm, live · click: open the swarm"

    onPressed: function (b) { root.openObservatory() }
  }
}

import QtQuick
import QtQuick.Controls
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

// Fix-Everything Observatory — the swarm chip, and the picker behind it.
//
// One glyph in the bar. LEFT-CLICK opens the observatory on omarchy — the
// repository this program was built to watch — whatever was on screen last
// time; a search result from this tray carries its own slug and opens on that.
// RIGHT-CLICK opens the tray, which is the answer to "watching WHAT?" — a
// search field over every repository this machine has, watched or not, plus
// the button that widens where it looks.
//
// The division of labour with the browser page is deliberate. This tray is a
// launcher: type three letters, hit enter, the observatory opens on that
// repository. It is the thing you want when you already know which repository
// you mean. What it does NOT do is render the induction report — the fifteen
// checks that decide whether a repository can be watched honestly are a
// document, with paths and remedies in it, and a document belongs on the page
// where it can be read and scrolled rather than in a bar popup. Picking an
// unwatched repository here therefore opens the page's directory with that
// repository's checks already running.
//
// The heavy surface — the scrubbable swarm, the flow diagram, the ticket
// inspector — is a browser page served by this plugin's own local server
// (observatory.py, bound to 127.0.0.1). This file talks to that same server
// over the same loopback port the page does.
//
// The launcher is resolved from this plugin's own directory, wherever that
// is — a git-managed install under ~/.config/omarchy/plugins or a dev symlink
// into a working tree. Qt.resolvedUrl(".") is the one authority on where this
// QML file loaded from, so the path is derived, never configured.
//
// Everything lives in this ONE file: the bar-widget entry point is the only
// QML the shell loads from a third-party plugin directory, so the tray is
// declared inline rather than in a sibling Panel.qml. That is the same shape
// the other brownfamilysports widgets ship under.
Panel {
  id: root
  moduleName: "brownfamilysports.observatory"
  ipcTarget: "brownfamilysports.observatory"
  manageIpc: false

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // file:///…/plugins/brownfamilysports.observatory/ → /…/plugins/…/
  readonly property string pluginDir: {
    var url = Qt.resolvedUrl(".").toString()
    return url.indexOf("file://") === 0 ? decodeURIComponent(url.substring(7)) : url
  }
  readonly property string launcher: root.pluginDir + "bin/fix-everything-observatory"
  readonly property string port: Quickshell.env("FIX_OBSERVATORY_PORT") || "4517"
  readonly property string api: "http://127.0.0.1:" + root.port

  // ------------------------------------------------------------------ model
  //
  // Three things, kept apart on purpose. `projects` is what the observatory
  // watches and is authoritative. `found` is what a filesystem walk turned up
  // and is a candidate list, not a claim. `completions` is the directory
  // picker, and only appears when the query stops being a filter and starts
  // being a path.
  property var projects: []
  property var found: []
  property var completions: []
  property string active: ""
  property string query: ""
  property int cursor: 0
  property string status: ""          // a sentence, or empty
  property bool reachable: false
  property bool scanned: false

  function run(args) {
    Quickshell.execDetached([root.launcher].concat(args))
  }

  function openObservatory(slug) {
    root.run(slug ? ["open", slug] : ["open"])
    root.close()
  }

  // ---- talking to the local server ----------------------------------------
  //
  // XMLHttpRequest rather than a Process: these are three-millisecond loopback
  // calls to a server this plugin owns, and shelling out for each one would
  // put a process launch between a keystroke and a filtered list.
  function apiGet(path, cb) {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      if (xhr.status !== 200) { cb(null, xhr.status); return }
      try { cb(JSON.parse(xhr.responseText), 200) } catch (e) { cb(null, -1) }
    }
    xhr.open("GET", root.api + path)
    xhr.send()
  }

  function apiPost(path, body, cb) {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== XMLHttpRequest.DONE) return
      var out = null
      try { out = JSON.parse(xhr.responseText) } catch (e) { out = null }
      cb(out, xhr.status)
    }
    xhr.open("POST", root.api + path)
    xhr.setRequestHeader("Content-Type", "application/json")
    // The same custom header the page sends. It forces a CORS preflight, so
    // nothing but a same-origin caller — or a local program like this one —
    // can reach the write endpoints.
    xhr.setRequestHeader("X-Fix-Observatory", "1")
    xhr.send(JSON.stringify(body))
  }

  // ---- loading -------------------------------------------------------------
  function reload() {
    root.apiGet("/api/projects", function (d, code) {
      if (!d) {
        root.reachable = false
        // "Nothing is watched" and "nothing is running" look identical in an
        // empty list, and only one of them is fixed by waiting. Say which,
        // and start the server rather than asking the user to.
        root.status = "the observatory server is not up — starting it…"
        root.run(["daemon"])
        retry.restart()
        return
      }
      root.reachable = true
      root.status = ""
      root.projects = d.projects || []
      root.active = d.active || ""
      root.rebuild()
      if (!root.scanned) root.rescan(false)
    })
  }

  function rescan(force) {
    root.status = root.found.length ? root.status : "looking for repositories…"
    root.apiGet("/api/scan" + (force ? "?refresh=1" : ""), function (d) {
      if (!d) { root.status = ""; return }
      root.scanned = true
      root.found = d.repos || []
      root.status = d.truncated
        ? "the walk hit its ceiling — this is not every repository on the machine"
        : ""
      root.rebuild()
    })
  }

  Timer {
    id: retry
    interval: 900
    repeat: false
    onTriggered: root.reload()
  }

  // ---- the list ------------------------------------------------------------
  readonly property bool queryIsPath: /^[~\/.]/.test(root.query.trim())

  function matches(hay) {
    return !root.query || hay.toLowerCase().indexOf(root.query.toLowerCase()) >= 0
  }

  function rebuild() {
    results.clear()
    if (root.queryIsPath) {
      for (var c = 0; c < root.completions.length; c++)
        results.append({ kind: "dir", title: root.completions[c],
                         subtitle: "", slug: "", path: root.completions[c] })
      results.append({ kind: "addroot", title: root.query.trim(),
                       subtitle: "add this directory to the search", slug: "",
                       path: root.query.trim() })
    } else {
      for (var i = 0; i < root.projects.length; i++) {
        var p = root.projects[i]
        if (!root.matches(p.repo + " " + (p.path || ""))) continue
        results.append({
          kind: "watch", title: p.repo, slug: p.slug, path: p.path || "",
          // null artifacts is NOT zero — it is a project nobody has mined yet,
          // and the row says so rather than printing a count of nothing.
          subtitle: (p.artifacts === null || p.artifacts === undefined
                     ? "not mined yet"
                     : p.artifacts + " artifacts")
                    + (p.mining ? " · mining" : "")
                    + (p.seeded ? " · seed" : "")
        })
      }
      for (var j = 0; j < root.found.length; j++) {
        var r = root.found[j]
        if (r.watched || !r.supported) continue
        if (!root.matches((r.nwo || "") + " " + r.path)) continue
        results.append({ kind: "found", title: r.nwo, slug: "",
                         path: r.path, subtitle: root.tilde(r.path) })
      }
    }
    root.cursor = results.count > 0 ? 0 : -1
  }

  function tilde(p) {
    var home = Quickshell.env("HOME") || ""
    return home && p.indexOf(home) === 0 ? "~" + p.substring(home.length) : p
  }

  function refreshCompletions() {
    if (!root.queryIsPath) { root.completions = []; root.rebuild(); return }
    root.apiGet("/api/complete?path=" + encodeURIComponent(root.query.trim()),
                function (d) {
                  root.completions = d ? (d.entries || []) : []
                  root.rebuild()
                })
  }

  function activate(index) {
    if (index < 0 || index >= results.count) return
    var row = results.get(index)
    if (row.kind === "watch") { root.openObservatory(row.slug); return }
    if (row.kind === "dir") { search.text = row.path; return }
    if (row.kind === "addroot") {
      root.apiPost("/api/roots", { add: row.path }, function (d, code) {
        if (!d || !d.ok) {
          root.status = d && d.error ? d.error : "could not add that directory"
          return
        }
        search.text = ""
        root.status = "added — rescanning"
        root.rescan(true)
      })
      return
    }
    // An unwatched repository. The fifteen induction checks are a document,
    // not a chip: hand it to the page, which renders them and owns the
    // decision. Nothing is written here.
    root.run(["open"])
    root.close()
    root.status = "opening the directory for " + row.title
  }

  ListModel { id: results }

  onOpenedChanged: {
    if (root.opened) {
      root.reload()
      search.text = ""
      Qt.callLater(function () { search.forceActiveFocus() })
    }
  }

  // ------------------------------------------------------------------ ipc
  IpcHandler {
    target: "brownfamilysports.observatory"

    function open(): void { root.openObservatory("") }
    function show(): void { root.openObservatory("") }
    function toggle(): void { root.toggle() }
    function pick(): void { root.open() }
    function close(): void { root.close() }
  }

  // ------------------------------------------------------------- bar button
  //
  // The root's implicit size IS the bar slot. Panel is a bare Item with none of
  // its own, so without these two lines the slot is zero wide, the button
  // anchored to fill it fills nothing, and the chip vanishes from the bar —
  // while the plugin loads cleanly, registers its IPC handler and logs no QML
  // error anywhere. That is what happened when this file's root changed from
  // BarWidget to Panel and these came off with it; every sibling that works
  // (crt, crook, wool) carries the same pair, and so did this file before the
  // rewrite. A widget that loads and draws nothing looks exactly like a widget
  // that is not installed, which is why it went unnoticed through a clean
  // `omarchy plugin validate` and a clean journal.
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "🌀"
    active: root.opened
    tooltipText: "Fix-Everything Observatory — " + (root.active
      ? "watching " + root.active.replace("__", "/")
      : "the repair swarm, live")
      + "\nclick: open the swarm · right-click: switch or add a project"

    onPressed: function (b) {
      if (b === Qt.RightButton) root.toggle()
      else root.openObservatory("")
    }
  }

  // ------------------------------------------------------------------- tray
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(430))
    contentHeight: panel.fittedContentHeight(
      Math.max(column.implicitHeight, Style.space(260)), Style.space(560))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      // The search field owns every key while it has focus. Without this the
      // catcher's vim bindings eat h, j, k and l out of the middle of a
      // repository name, which is a genuinely maddening bug to be on the
      // wrong end of.
      blocked: search.activeFocus

      onCloseRequested: root.close()
      onTabRequested: function (direction) { root.switchPanel(direction) }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(9)

        PanelHero {
          width: parent.width
          title: "Observatory"
          meta: root.active ? root.active.replace("__", "/") : "no project selected"
          // Short on purpose: PanelHero's detail does not wrap, so a long line
          // runs off the panel edge rather than eliding. The instruction that
          // used to live here is the search field's own placeholder two rows
          // down, where the hand already is.
          detail: root.reachable
            ? results.count + " of " + (root.projects.length + root.found.length)
              + " repositories"
            : "server not reachable on :" + root.port
          foreground: root.foreground
          fontFamily: root.fontFamily
        }

        TextField {
          id: search
          width: parent.width
          foreground: root.foreground
          placeholderText: "filter repositories, or type / for a directory"
          onTextChanged: {
            root.query = text
            if (root.queryIsPath) root.refreshCompletions()
            else root.rebuild()
          }
          Keys.onPressed: function (event) {
            if (event.key === Qt.Key_Down) {
              root.cursor = Math.min(results.count - 1, root.cursor + 1)
              list.positionViewAtIndex(root.cursor, ListView.Contain)
              event.accepted = true
            } else if (event.key === Qt.Key_Up) {
              root.cursor = Math.max(0, root.cursor - 1)
              list.positionViewAtIndex(root.cursor, ListView.Contain)
              event.accepted = true
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
              root.activate(root.cursor)
              event.accepted = true
            } else if (event.key === Qt.Key_Escape) {
              if (search.text) search.text = ""
              else root.close()
              event.accepted = true
            }
          }
        }

        ListView {
          id: list
          width: parent.width
          height: Math.min(Style.space(300),
                           Math.max(Style.space(40), results.count * Style.space(38)))
          model: results
          clip: true
          boundsBehavior: Flickable.StopAtBounds

          delegate: Rectangle {
            required property int index
            required property string kind
            required property string title
            required property string subtitle
            required property string slug

            width: list.width
            height: Style.space(38)
            color: index === root.cursor
              ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.10)
              : "transparent"
            // Watched projects are marked down the left edge; candidates are
            // not. One glance separates "this is in the instrument" from
            // "this is a repository that exists".
            Rectangle {
              width: Style.space(2)
              height: parent.height
              color: kind === "watch" ? root.foreground : "transparent"
              opacity: slug === root.active ? 1 : 0.35
            }

            Column {
              anchors.verticalCenter: parent.verticalCenter
              anchors.left: parent.left
              anchors.leftMargin: Style.space(10)
              anchors.right: parent.right
              anchors.rightMargin: Style.space(8)
              spacing: 1

              Text {
                width: parent.width
                text: kind === "addroot" ? "＋  " + title : title
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideMiddle
              }
              Text {
                width: parent.width
                visible: subtitle !== ""
                text: subtitle
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideMiddle
              }
            }

            MouseArea {
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onContainsMouseChanged: if (containsMouse) root.cursor = index
              onClicked: root.activate(index)
            }
          }
        }

        Text {
          width: parent.width
          visible: results.count === 0
          text: root.reachable
            ? (root.scanned ? "nothing matches." : "looking…")
            : "waiting for the observatory server."
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        PanelSeparator { width: parent.width; foreground: root.foreground }

        Row {
          width: parent.width
          spacing: Style.space(8)

          Button {
            text: root.queryIsPath ? "ADD DIRECTORY" : "＋ ADD A DIRECTORY"
            foreground: root.foreground
            fontFamily: root.fontFamily
            bordered: true
            onClicked: {
              if (root.queryIsPath) {
                // The last row of a path query IS the add action, so reuse it
                // rather than writing the POST twice.
                root.activate(results.count - 1)
              } else {
                // Nothing typed yet: say what to type rather than opening a
                // file dialog this popup has no room for.
                search.text = "~/"
                search.forceActiveFocus()
                root.status = "type where to look — the field completes real directories"
              }
            }
          }

          Button {
            text: "RESCAN"
            foreground: root.foreground
            fontFamily: root.fontFamily
            bordered: true
            onClicked: root.rescan(true)
          }

          Button {
            text: "OPEN"
            foreground: root.foreground
            fontFamily: root.fontFamily
            bordered: true
            onClicked: root.openObservatory("")
          }
        }

        Text {
          width: parent.width
          visible: root.status !== ""
          text: root.status
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}

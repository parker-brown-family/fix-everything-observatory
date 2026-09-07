#!/usr/bin/env python3
"""StatusNotifierItem tray applet for the Fix-Everything Tracker.

Puts the Omarchy spiral in the Omarchy quickshell bar's SNI tray; any click
opens the swarm visualizer via `bin/fix-everything-tracker open`.

Pure Gio/GLib DBus — no libappindicator dependency. Single-instance via a
well-known bus name.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gio, GLib, GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "app" / "omarchy-logo.png"
OPEN_CMD = [str(ROOT / "bin" / "fix-everything-tracker"), "open"]
APP_NAME = "org.omarchy.FixEverythingTracker"
SNI_PATH = "/StatusNotifierItem"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
    <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
    <signal name="NewIcon"/>
    <signal name="NewStatus"><arg type="s"/></signal>
  </interface>
</node>
"""


def icon_pixmap():
    """PNG -> SNI ARGB32 pixmap list (network byte order, per the SNI spec).

    The pixmap is only the fallback: IconName + a hicolor theme icon is the
    primary path (quickshell resolves theme icons itself, no byte-order risk).
    """
    pb = GdkPixbuf.Pixbuf.new_from_file(str(ICON))
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    w, h, stride = pb.get_width(), pb.get_height(), pb.get_rowstride()
    rgba = pb.get_pixels()
    out = bytearray(w * h * 4)
    for row in range(h):
        src = row * stride
        dst = row * w * 4
        for col in range(w):
            r, g, b, a = rgba[src + col * 4: src + col * 4 + 4]
            out[dst + col * 4: dst + col * 4 + 4] = bytes((a, r, g, b))
    return [(w, h, bytes(out))]


PIXMAP = icon_pixmap()
PROPS = {
    "Category": GLib.Variant("s", "ApplicationStatus"),
    "Id": GLib.Variant("s", "fix-everything-tracker"),
    "Title": GLib.Variant("s", "Fix-Everything Tracker"),
    "Status": GLib.Variant("s", "Active"),
    "IconName": GLib.Variant("s", "fix-everything-tracker"),
    "IconThemePath": GLib.Variant("s", ""),
    "IconPixmap": GLib.Variant("a(iiay)", PIXMAP),
    "ToolTip": GLib.Variant("(sa(iiay)ss)",
                            ("", PIXMAP, "Fix-Everything Tracker",
                             "open the omarchy repair swarm")),
    "ItemIsMenu": GLib.Variant("b", False),
    "Menu": GLib.Variant("o", "/NO_DBUSMENU"),
}


def launch(*_args):
    subprocess.Popen(OPEN_CMD, start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def on_method_call(_conn, _sender, _path, _iface, method, _params, invocation):
    if method in ("Activate", "SecondaryActivate", "ContextMenu"):
        launch()
    invocation.return_value(None)


def on_get_property(_conn, _sender, _path, _iface, name):
    return PROPS.get(name)


def register_with_watcher(conn: Gio.DBusConnection, item_name: str) -> None:
    try:
        conn.call_sync(
            "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (item_name,)), None,
            Gio.DBusCallFlags.NONE, 5000, None)
        print(f"registered {item_name} with StatusNotifierWatcher", flush=True)
    except GLib.Error as exc:
        print(f"watcher registration failed: {exc}", file=sys.stderr, flush=True)


def main() -> int:
    conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
    conn.register_object(SNI_PATH, node.interfaces[0],
                         on_method_call, on_get_property, None)

    # Single instance: owning APP_NAME fails -> another applet already runs.
    got_app = Gio.bus_own_name_on_connection(
        conn, APP_NAME, Gio.BusNameOwnerFlags.NONE, None,
        lambda *_: (print("another instance owns the tray — exiting", flush=True),
                    sys.exit(0)))
    if not got_app:
        return 1

    item_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
    Gio.bus_own_name_on_connection(conn, item_name,
                                   Gio.BusNameOwnerFlags.NONE, None, None)
    register_with_watcher(conn, item_name)

    # Re-register whenever the watcher (the bar) restarts.
    Gio.bus_watch_name_on_connection(
        conn, "org.kde.StatusNotifierWatcher",
        Gio.BusNameWatcherFlags.NONE,
        lambda c, n, owner: register_with_watcher(c, item_name),
        None)

    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

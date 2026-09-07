#!/usr/bin/env python3
"""Report whether the SNI tray applet's dependencies are present on this host."""
try:
    import gi  # noqa: F401
    from gi.repository import Gio, GLib  # noqa: F401
    print("gio: ok")
except Exception as exc:  # pragma: no cover — diagnostic script
    print(f"gio: MISSING ({exc})")
try:
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf  # noqa: F401
    print("pixbuf: ok")
except Exception as exc:
    print(f"pixbuf: MISSING ({exc})")

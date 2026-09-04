"""Push the app logo into the X11 _NET_WM_ICON property (ctypes, no deps).

Qt normally mirrors QWidget window icons into _NET_WM_ICON on X11, but in
some XWayland/Qt combinations the property stays empty and the taskbar
falls back to a generic glyph. This helper converts the bundled PNG into
the CARDINAL array the spec requires and sets it explicitly.

Only ever called on the ``xcb`` platform; every failure is swallowed so
Wayland/Windows/macOS behaviour never changes.
"""

import ctypes
import ctypes.util


def push_window_icon(window, png_path: str) -> bool:
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QImage

        for size in (128, 48):
            img = QImage(str(png_path)).scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            argb = img.convertToFormat(QImage.Format.Format_ARGB32)
            if argb.isNull():
                continue
            bits = argb.constBits()
            bits.setsize(argb.sizeInBytes())
            raw = bytes(bits)
            n = size * size
            words = [size, size]
            for i in range(n):
                b, g, r, a = raw[4 * i], raw[4 * i + 1], raw[4 * i + 2], raw[4 * i + 3]
                words.append((a << 24) | (r << 16) | (g << 8) | b)
            if _x11_set_cardinals(int(window.winId()), "_NET_WM_ICON", words):
                return True
        return False
    except Exception:
        return False


def _x11_set_cardinals(win_id: int, prop: str, values: list) -> bool:
    try:
        lib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        lib.XOpenDisplay.restype = ctypes.c_void_p
        lib.XInternAtom.restype = ctypes.c_ulong
        lib.XChangeProperty.restype = ctypes.c_int
        display = lib.XOpenDisplay(None)
        if not display:
            return False
        atom = lib.XInternAtom(display, prop.encode(), False)
        cardinal = lib.XInternAtom(display, b"CARDINAL", False)
        arr = (ctypes.c_ulong * len(values))(*values)
        rc = lib.XChangeProperty(
            display, ctypes.c_ulong(win_id), atom, cardinal, 32, 0,
            ctypes.cast(arr, ctypes.c_char_p), len(values),
        )
        lib.XFlush(display)
        lib.XCloseDisplay(display)
        return rc == 0
    except Exception:
        return False

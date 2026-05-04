#!/usr/bin/env python3
"""
Vehicle Motion Cues for Linux
Reduces transport/motion sickness by showing animated dots at screen edges.

Works WITHOUT a compositor. Uses X11 ShapeBounding (via Qt's setMask) so the
window is physically cut to only the dot shapes — no transparency needed.
Mouse clicks pass through everywhere via X11 ShapeInput (empty region).

Quit: right-click the tray icon → Quit,  or  Ctrl-C in the terminal.

Requirements: pip install PyQt6   (or PyQt5)
"""

import ctypes
import random
import signal
import sys

# ---------------------------------------------------------------------------
# Qt shim — PyQt6 first, PyQt5 fallback
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QRegion
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

    Qt_Frameless   = Qt.WindowType.FramelessWindowHint
    Qt_AlwaysOnTop = Qt.WindowType.WindowStaysOnTopHint
    Qt_Tool        = Qt.WindowType.Tool
    Qt_NoFocus     = Qt.WindowType.WindowDoesNotAcceptFocus
    Hint_AA        = QPainter.RenderHint.Antialiasing
    NoPen          = Qt.PenStyle.NoPen
    Reg_Ellipse    = QRegion.RegionType.Ellipse

    def app_exec(a: QApplication) -> int:
        return a.exec()

except ImportError:
    try:
        from PyQt5.QtCore import Qt, QTimer  # type: ignore[assignment]
        from PyQt5.QtGui import (  # type: ignore[assignment]
            QColor,
            QIcon,
            QPainter,
            QPixmap,
            QRegion,
        )
        from PyQt5.QtWidgets import (  # type: ignore[assignment]
            QAction,
            QApplication,
            QMenu,
            QSystemTrayIcon,
            QWidget,
        )

        Qt_Frameless   = Qt.FramelessWindowHint
        Qt_AlwaysOnTop = Qt.WindowStaysOnTopHint
        Qt_Tool        = Qt.Tool
        Qt_NoFocus     = Qt.WindowDoesNotAcceptFocus
        Hint_AA        = QPainter.Antialiasing
        NoPen          = Qt.NoPen
        Reg_Ellipse    = QRegion.Ellipse

        def app_exec(a: QApplication) -> int:  # type: ignore[misc]
            return a.exec_()

    except ImportError:
        sys.exit("PyQt6 or PyQt5 is required.  Install: pip install PyQt6")

# ---------------------------------------------------------------------------
# X11: make the window receive no mouse/touch events at all (click-through).
# Uses ShapeInput extension — independent from ShapeBounding / setMask.
# ---------------------------------------------------------------------------
def _apply_click_through(win_id: int) -> None:
    try:
        xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
        xext = ctypes.cdll.LoadLibrary("libXext.so.6")
        dpy = xlib.XOpenDisplay(None)
        if not dpy:
            return
        xext.XShapeCombineRectangles(
            dpy, ctypes.c_ulong(win_id),
            ctypes.c_int(2),    # ShapeInput
            ctypes.c_int(0), ctypes.c_int(0),
            None, ctypes.c_int(0),
            ctypes.c_int(0),    # ShapeSet
            ctypes.c_int(0),    # Unsorted
        )
        xlib.XFlush(dpy)
        xlib.XCloseDisplay(dpy)
    except Exception as e:
        print(f"Warning: click-through not applied ({e})")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EDGE_WIDTH = 80     # px strip on each side where dots live
DOT_COUNT  = 60
FPS        = 60
BASE_VY    = 0.35   # gentle downward drift = forward-travel feeling
DECAY      = 0.92   # impulse decay rate

# ---------------------------------------------------------------------------
# Dot
# ---------------------------------------------------------------------------
class Dot:
    PALETTE = [
        (255, 200, 100),
        (100, 200, 255),
        (180, 255, 160),
        (255, 150, 180),
        (200, 170, 255),
        (255, 220, 160),
    ]

    def __init__(self, sw: int, sh: int):
        self.sw, self.sh = sw, sh
        self._place()

    def _place(self) -> None:
        ew   = EDGE_WIDTH
        edge = random.randint(0, 3)
        if edge == 0:
            self.x = random.uniform(0, self.sw)
            self.y = random.uniform(0, ew)
        elif edge == 1:
            self.x = random.uniform(0, self.sw)
            self.y = random.uniform(self.sh - ew, self.sh)
        elif edge == 2:
            self.x = random.uniform(0, ew)
            self.y = random.uniform(0, self.sh)
        else:
            self.x = random.uniform(self.sw - ew, self.sw)
            self.y = random.uniform(0, self.sh)

        self.r, self.g, self.b = random.choice(self.PALETTE)
        self.size  = random.uniform(6, 14)
        self.alpha = random.uniform(0.55, 1.0)
        self.sfac  = random.uniform(0.65, 1.35)

    def _on_edge(self) -> bool:
        ew = EDGE_WIDTH
        return not (ew < self.x < self.sw - ew and ew < self.y < self.sh - ew)

    def update(self, vx: float, vy: float) -> None:
        self.x += vx * self.sfac
        self.y += vy * self.sfac
        m = 20
        if (self.x < -m or self.x > self.sw + m
                or self.y < -m or self.y > self.sh + m
                or not self._on_edge()):
            self._place()

    def draw(self, p: QPainter) -> None:
        p.setBrush(QColor(self.r, self.g, self.b, int(self.alpha * 255)))
        p.setPen(NoPen)
        h = self.size / 2
        p.drawEllipse(int(self.x - h), int(self.y - h), int(self.size), int(self.size))

    def mask_region(self) -> QRegion:
        # Slightly larger than the drawn dot so anti-aliased edges aren't clipped
        pad = 2
        d   = int(self.size) + pad * 2
        h   = d // 2
        return QRegion(int(self.x) - h, int(self.y) - h, d, d, Reg_Ellipse)

# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------
class MotionCuesOverlay(QWidget):

    def __init__(self) -> None:
        super().__init__()
        geom    = QApplication.primaryScreen().geometry()
        self.sw = geom.width()
        self.sh = geom.height()

        # No WA_TranslucentBackground — we shape the window instead,
        # which works with or without a compositor.
        self.setWindowFlags(Qt_Frameless | Qt_AlwaysOnTop | Qt_Tool | Qt_NoFocus)
        self.setGeometry(geom)
        self.show()

        # Click-through: set ShapeInput to empty after native handle exists
        QTimer.singleShot(150, lambda: _apply_click_through(int(self.winId())))

        self.vx   = 0.0
        self.vy   = BASE_VY
        self.dots = [Dot(self.sw, self.sh) for _ in range(DOT_COUNT)]

        timer = QTimer(self)
        timer.timeout.connect(self._tick)
        timer.start(1000 // FPS)

    def _tick(self) -> None:
        self.vx = self.vx * DECAY
        self.vy = self.vy * DECAY + BASE_VY * (1.0 - DECAY)
        for dot in self.dots:
            dot.update(self.vx, self.vy)

        # Shape the window to only the dot pixels — compositor not required.
        mask = QRegion()
        for dot in self.dots:
            mask = mask.united(dot.mask_region())
        self.setMask(mask)

        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(Hint_AA)
        for dot in self.dots:
            dot.draw(p)
        p.end()

    def push(self, dvx: float = 0.0, dvy: float = 0.0) -> None:
        self.vx += dvx
        self.vy += dvy

# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------
def _make_tray(overlay: MotionCuesOverlay) -> QSystemTrayIcon:
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(Hint_AA)
    p.setBrush(QColor(100, 200, 255))
    p.setPen(NoPen)
    p.drawEllipse(2, 2, 18, 18)
    p.end()

    tray = QSystemTrayIcon(QIcon(px))
    tray.setToolTip("Vehicle Motion Cues")

    menu = QMenu()
    menu.addSection("Inject motion")
    for label, dvx, dvy in [
        ("↓  Accelerate",  0.0,  5.0),
        ("↑  Brake",       0.0, -5.0),
        ("←  Turn left",   5.0,  0.0),
        ("→  Turn right", -5.0,  0.0),
    ]:
        a = QAction(label)
        a.triggered.connect(lambda _checked=False, x=dvx, y=dvy: overlay.push(x, y))
        menu.addAction(a)
    menu.addSeparator()
    q = QAction("Quit")
    q.triggered.connect(QApplication.quit)
    menu.addAction(q)

    tray.setContextMenu(menu)
    tray.show()
    return tray

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Vehicle Motion Cues")
    app.setQuitOnLastWindowClosed(False)

    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    # Give Python's signal handler a chance to run every 500 ms
    pulse = QTimer()
    pulse.start(500)
    pulse.timeout.connect(lambda: None)

    overlay = MotionCuesOverlay()
    _tray   = _make_tray(overlay)  # kept alive via reference

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray detected — quit with Ctrl-C.")

    print("Vehicle Motion Cues running. Right-click tray icon to quit.")

    sys.exit(app_exec(app))


if __name__ == "__main__":
    main()

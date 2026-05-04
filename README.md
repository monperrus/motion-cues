# motion-cues

Animated peripheral dots that reduce motion/transport sickness while using a laptop in a vehicle — a Linux port of Apple's [Vehicle Motion Cues](https://support.apple.com/guide/iphone/iphone-comfortably-riding-a-vehicle-iph55564cb22/ios) (iOS 18 / macOS 15).

The overlay is fully **click-through** and **focus-free**: you see the dots at the screen edges and can keep working normally underneath.

## How it works

Motion sickness occurs when the vestibular system (inner ear) detects vehicle motion but the eyes, focused on a static screen, do not. The dots appear in the peripheral visual field (~80 px from each edge) and drift to match vehicle motion, providing the optic-flow signal the peripheral visual system expects and collapsing the sensory conflict.

Dot direction mirrors Apple's convention:

| Vehicle motion | Dot direction |
|----------------|---------------|
| Accelerate     | drift down    |
| Brake          | drift up      |
| Turn left      | drift right   |
| Turn right     | drift left    |

## Installation

```bash
pip install motion-cues
```

Requires Python ≥ 3.9, Linux + X11, and PyQt6 (pulled in automatically). Does **not** require a compositor.

## Usage

```bash
motion-cues
```

Or run directly:

```bash
python -m motion_cues
```

A blue dot appears in the system tray. Right-click it to inject simulated motion impulses (useful when stationary) or to quit. Press **Ctrl-C** in the terminal to quit as well.

## Requirements

- Linux with X11 (Wayland support is not yet implemented)
- `libX11` and `libXext` system libraries (present on any X11 system)
- PyQt6 ≥ 6.0 (or PyQt5 ≥ 5.15 as fallback)

## Technical notes

The overlay window uses **X11 ShapeBounding** (`setMask`) to cut the window to only the dot pixels, so there is no opaque background anywhere — no compositor required. Mouse events are discarded via **X11 ShapeInput** (empty region), so clicks always fall through to the desktop.

## License

MIT

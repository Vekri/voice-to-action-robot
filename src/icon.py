"""Companion Raja face used as the window icon and header mark."""

from __future__ import annotations

from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT / "data" / "raja_icon.png"
CORNER_PATH = ROOT / "data" / "dollar_network.png"


def make_icon(size: int = 256) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    scale = size / 256.0

    def n(v: float) -> int:
        return max(1, int(v * scale))

    def oval(color, x, y, w, h, width: int = 0) -> None:
        box = pygame.Rect(0, 0, n(w), n(h))
        box.center = (n(x), n(y))
        pygame.draw.ellipse(s, color, box, width)

    pygame.draw.rect(s, (10, 16, 28, 255), (0, 0, size, size), border_radius=n(48))

    # Arms
    oval((236, 240, 246), 70, 168, 36, 70)
    oval((236, 240, 246), 186, 168, 36, 70)

    # Body
    oval((198, 206, 216), 128, 186, 118, 132)
    oval((236, 240, 246), 128, 180, 112, 126)
    oval((250, 252, 255), 112, 158, 40, 32)

    # Helmet
    oval((198, 206, 216), 128, 96, 108, 96)
    oval((236, 240, 246), 128, 92, 104, 92)
    oval((250, 252, 255), 110, 76, 32, 20)

    # Visor + face
    oval((18, 28, 40), 128, 98, 80, 52)
    pygame.draw.circle(s, (80, 230, 255), (n(110), n(94)), n(5))
    pygame.draw.circle(s, (80, 230, 255), (n(146), n(94)), n(5))
    pygame.draw.circle(s, (80, 230, 255), (n(128), n(110)), n(5))
    return s


def corner_mark(size: int = 44) -> pygame.Surface:
    """Dollar-network badge for the top-right header."""
    if CORNER_PATH.is_file():
        raw = pygame.image.load(str(CORNER_PATH))
        try:
            raw = raw.convert_alpha()
        except pygame.error:
            pass
        return pygame.transform.smoothscale(raw, (size, size))
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(s, (18, 24, 36), (size // 2, size // 2), size // 2)
    pygame.draw.circle(s, (40, 52, 72), (size // 2, size // 2), size // 2, 2)
    return s


def header_mark(size: int = 32) -> pygame.Surface:
    return pygame.transform.smoothscale(make_icon(256), (size, size))


def apply_window_icon() -> pygame.Surface:
    """Must run after pygame.display.set_mode()."""
    big = make_icon(256)
    try:
        ICON_PATH.parent.mkdir(exist_ok=True)
        pygame.image.save(big, str(ICON_PATH))
    except Exception:
        pass
    small = pygame.transform.smoothscale(big, (32, 32))
    try:
        small = small.convert_alpha()
    except pygame.error:
        pass
    pygame.display.set_icon(small)
    return small

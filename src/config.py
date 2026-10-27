"""Visual theme, layout, and runtime constants."""

from __future__ import annotations

WIDTH = 1600
HEIGHT = 900
FPS = 60
ROBOT_NAME = "Raja"
TITLE = "RAJA  —  Don't Ask AI. Assign the Task."

PANEL_W = 400
STAGE_W = WIDTH - PANEL_W
HEADER_H = 70
FOOTER_H = 46
CMD_H = 52
ROBOT_STRIP = 240
CHART_X = 28
CHART_Y = HEADER_H + 10
CHART_W = 700
CHART_H = 500
ROBOT_X = STAGE_W - 112
ROBOT_Y = HEIGHT - 250
ROBOT_MIN_X = STAGE_W - 210
DIALOGUE_X = STAGE_W - 320


def apply_size(width: int, height: int) -> None:
    """Recompute layout so the HUD, chart, and robot stay on-screen."""
    global WIDTH, HEIGHT, PANEL_W, STAGE_W, HEADER_H, FOOTER_H, CMD_H
    global ROBOT_STRIP, CHART_X, CHART_Y, CHART_W, CHART_H
    global ROBOT_X, ROBOT_Y, ROBOT_MIN_X, DIALOGUE_X
    WIDTH = max(1100, int(width))
    HEIGHT = max(680, int(height))
    PANEL_W = 320 if WIDTH < 1280 else (360 if WIDTH < 1480 else 400)
    STAGE_W = WIDTH - PANEL_W
    compact = HEIGHT < 760
    HEADER_H = 60 if compact else 68
    FOOTER_H = 38 if compact else 44
    CMD_H = 46 if compact else 52
    ROBOT_STRIP = 200 if STAGE_W < 980 else 240
    CHART_X = 24
    CHART_Y = HEADER_H + 10
    CHART_W = max(360, STAGE_W - ROBOT_STRIP - 36)
    CHART_H = max(280, HEIGHT - HEADER_H - FOOTER_H - CMD_H - 28)
    ROBOT_X = STAGE_W - max(96, ROBOT_STRIP // 2 - 8)
    ROBOT_Y = HEIGHT - 250
    ROBOT_MIN_X = STAGE_W - ROBOT_STRIP + 20
    DIALOGUE_X = max(CHART_X + 8, STAGE_W - 320)


def fit_desktop() -> tuple[int, int]:
    """Fill the monitor, leaving a thin strip for the Windows taskbar."""
    import sys

    import pygame

    if sys.platform == "emscripten":
        apply_size(1280, 720)
        return WIDTH, HEIGHT
    pygame.display.init()
    info = pygame.display.Info()
    w = max(1100, int(info.current_w) - 8)
    h = max(680, int(info.current_h) - 48)
    apply_size(w, h)
    return WIDTH, HEIGHT


# Motion
WALK_SPEED = 130
RUN_SPEED = 240

# Voice
LISTEN_TIMEOUT = 6.0
PHRASE_LIMIT = 8.0
ENERGY_THRESHOLD = 280

# Colors
BG = (6, 10, 18)
SLIDE = (10, 16, 26)
CARD = (14, 22, 34)
PANEL = (8, 12, 20)
PANEL_EDGE = (36, 48, 66)
GRID = (22, 32, 48)
WHITE = (240, 244, 250)
INK = (18, 24, 34)
MUTED = (140, 154, 172)
CYAN = (0, 230, 255)
GOLD = (255, 204, 51)
MAGENTA = (255, 43, 214)
LIME = (57, 255, 80)
ORANGE = (255, 140, 40)
ACCENT = (0, 200, 230)

# Copy
TAGLINE = "Don't just talk to AI. Give AI the ability to act."
SUBLINE = "Speak or type. I understand. I act. I answer."
PIPELINE = "Voice  →  AI Agent  →  Python Tools  →  Robot Action"
TASKS = (
    "I load retail sales data, draw the chart, speak the insight, "
    "move on stage, and answer you like a person."
)
TRY = "load csv  ·  visualize  ·  get insights  ·  dance  ·  hello Raja"

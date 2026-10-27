"""Stage, briefing console, chrome, and text helpers."""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence

import pygame

from . import config as C
from .agent import Agent
from .icon import corner_mark, header_mark
from .robot import Robot
from .voice import VoiceIO

_FONTS: dict = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _FONTS:
        name = "segoeui"
        try:
            _FONTS[key] = pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            _FONTS[key] = pygame.font.Font(None, size)
    return _FONTS[key]


def wrap(text_in: str, chars: int) -> str:
    words = (text_in or "").split()
    if not words:
        return ""
    lines, cur = [], words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[0] if len(lines) == 1 else lines[0] + "…"


def wrap_lines(text_in: str, chars: int, limit: int = 4) -> List[str]:
    words = (text_in or "").split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= chars:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:limit]


def text(
    surface: pygame.Surface,
    msg: str,
    pos: tuple[int, int],
    size: int = 14,
    color=C.WHITE,
    bold: bool = False,
    shadow: bool = False,
) -> None:
    img = font(size, bold).render(msg[:180], True, color)
    if shadow:
        sh = font(size, bold).render(msg[:180], True, (0, 0, 0))
        surface.blit(sh, (pos[0] + 1, pos[1] + 1))
    surface.blit(img, pos)


class Stage:
    def __init__(self) -> None:
        self.t = 0.0
        self.dust = [(random.random(), random.random(), random.random()) for _ in range(40)]

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surface: pygame.Surface, robot: Robot, voice: VoiceIO, presenting: bool = False) -> None:
        pygame.draw.rect(surface, C.BG, (0, 0, C.STAGE_W, C.HEIGHT))
        floor_y = C.HEIGHT - C.FOOTER_H - 70
        pygame.draw.rect(surface, (10, 16, 24), (0, floor_y, C.STAGE_W, C.HEIGHT - floor_y))
        pygame.draw.line(surface, C.PANEL_EDGE, (20, floor_y), (C.STAGE_W - 20, floor_y), 1)
        glow = 40 if presenting else 70
        for i, (x, y, s) in enumerate(self.dust):
            px = int((x * C.STAGE_W + math.sin(self.t * 0.3 + i) * 8) % C.STAGE_W)
            py = int(80 + y * (floor_y - 100))
            pygame.draw.circle(surface, (20, 40, glow), (px, py), 1)
        if voice.listening:
            pygame.draw.circle(surface, C.CYAN, (28, C.HEADER_H + 36), 4)


class ControlPanel:
    def __init__(self) -> None:
        self.t = 0.0

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, surface, agent: Agent, robot: Robot, voice: VoiceIO, phase: str, log, todos) -> None:
        x = C.STAGE_W
        pygame.draw.rect(surface, C.PANEL, (x, 0, C.PANEL_W, C.HEIGHT))
        pygame.draw.line(surface, C.PANEL_EDGE, (x, 0), (x, C.HEIGHT), 1)
        tiny = C.HEIGHT < 760
        short = C.HEIGHT < 840
        card_h = 42 if tiny else (54 if short else 68)
        gap = 6 if tiny else 8
        chars = max(22, (C.PANEL_W - 56) // 9)

        text(surface, "BRIEFING CONSOLE", (x + 16, 12), 15 if tiny else 17, C.WHITE, True)
        text(surface, agent.backend, (x + 16, 34 if tiny else 38), 12, C.GOLD)
        if not tiny:
            text(surface, "RAJA  ·  Your AI robot", (x + 16, 56), 12, C.MUTED)

        pipe_y = 56 if tiny else 88
        self._pipeline(surface, x + 16, pipe_y, phase)

        y = pipe_y + 92
        heard = "… listening …" if voice.listening else (agent.last_voice or "… ready …")
        self._card(surface, x + 14, y, "VOICE", f'"{wrap(heard, chars)}"', C.CYAN, card_h)
        y += card_h + gap
        self._card(surface, x + 14, y, "INTENT", agent.last_intent, C.GOLD, card_h)
        y += card_h + gap
        if not tiny:
            self._card(surface, x + 14, y, "PARAMETER", agent.last_params, C.ORANGE, card_h)
            y += card_h + gap
        self._card(surface, x + 14, y, "TOOL", agent.last_tool if agent.last_tool != "—" else robot.tool_line, C.LIME, card_h)
        y += card_h + gap

        status = "EXECUTING" if robot.busy else ("COMPLETED" if robot.status == "COMPLETED" else "READY")
        status_col = C.ORANGE if robot.busy else (C.LIME if status == "COMPLETED" else C.CYAN)
        self._card(surface, x + 14, y, "STATUS", status, status_col, card_h)
        y += card_h + gap

        glyph = {
            "RUNNING": ">>  RUNNING",
            "WALKING": ">>  WALKING",
            "JUMPING": "^^  JUMPING",
            "SITTING": "..  SITTING",
            "STANDING": "||  STANDING",
            "DANCING": "**  DANCING",
            "PLAYING MUSIC": "  PLAYING MUSIC",
            "TURNING LEFT": "<<  TURN LEFT",
            "TURNING RIGHT": ">>  TURN RIGHT",
            "STOPPED": "[]  STOPPED",
            "IDLE": "--  IDLE",
            "COMPLETED": "OK  READY",
            "LOADING DATA": "[]  LOADING DATA",
            "VISUALIZING": "##  VISUALIZING",
            "ANALYZING": "AI  ANALYZING",
            "SPEAKING": "..  SPEAKING",
            "WAVING": "++  WAVING",
        }.get(robot.status, robot.status)
        self._card(surface, x + 14, y, "ROBOT", glyph, C.MAGENTA, card_h)
        y += card_h + 10

        text(surface, "TASKS", (x + 16, y), 11, C.GOLD, True)
        y += 18
        if todos:
            for item in list(todos)[: 5 if tiny else 7]:
                if y > C.HEIGHT - 96:
                    break
                if item.status == "done":
                    mark, col = "OK", C.LIME
                elif item.status == "doing":
                    mark, col = ">>", C.GOLD
                else:
                    mark, col = "· ", C.MUTED
                text(surface, wrap(f"{mark}  {item.title}", chars + 4), (x + 16, y), 13, col)
                y += 18
            y += 6
        elif agent.last_plan:
            text(surface, "  →  ".join(agent.last_plan)[:48], (x + 16, y), 13, C.WHITE)
            y += 24
        else:
            text(surface, "Try: " + C.TRY, (x + 16, y), 12, C.MUTED)
            y += 22

        text(surface, "ACTIVITY", (x + 16, y), 11, C.MUTED, True)
        y += 18
        log_n = 3 if tiny else (4 if short else 6)
        for i, row in enumerate(list(log)[:log_n]):
            if y + i * 16 > C.HEIGHT - 86:
                break
            text(surface, wrap(str(row), chars + 2), (x + 16, y + i * 16), 12, C.MUTED)

    def _pipeline(self, surface, x: int, y: int, phase: str) -> None:
        steps = ("listen", "understand", "action", "status")
        labels = ("VOICE", "UNDERSTAND", "ACTION", "STATUS")
        w = C.PANEL_W - 32
        slot = w // 4
        for i, (key, label) in enumerate(zip(steps, labels)):
            on = key == phase
            bx = x + i * slot
            pygame.draw.rect(surface, C.GOLD if on else C.CARD, (bx, y, slot - 6, 28), border_radius=6)
            text(surface, label[:10], (bx + 6, y + 6), 11, C.INK if on else C.MUTED, True)
        text(surface, C.PIPELINE, (x, y + 36), 11, C.MUTED)

    def _card(self, surface, x, y, title, value, color, h: int) -> None:
        pygame.draw.rect(surface, C.CARD, (x, y, C.PANEL_W - 28, h), border_radius=8)
        pygame.draw.rect(surface, C.PANEL_EDGE, (x, y, C.PANEL_W - 28, h), 1, border_radius=8)
        pygame.draw.rect(surface, color, (x, y, 4, h), border_radius=2)
        text(surface, title, (x + 12, y + 6), 11, C.MUTED, True)
        text(surface, wrap(str(value), max(18, (C.PANEL_W - 50) // 8)), (x + 12, y + 24), 14, C.WHITE)


class Chrome:
    def __init__(self) -> None:
        self._mark = header_mark(32)
        self._corner = corner_mark(44)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (8, 12, 20), (0, 0, C.WIDTH, C.HEADER_H))
        pygame.draw.line(surface, C.PANEL_EDGE, (0, C.HEADER_H), (C.WIDTH, C.HEADER_H), 1)
        surface.blit(self._mark, (16, 8))
        text(surface, "RAJA", (56, 8), 20 if C.HEADER_H < 64 else 24, C.WHITE, True)
        title_size = 13 if C.WIDTH < 1280 else 15
        text(surface, "Don't Ask AI. Assign the Task.", (122, 10), title_size, C.GOLD, True)
        tag_size = 12 if C.WIDTH < 1280 else 13
        text(surface, C.SUBLINE, (56, C.HEADER_H - 22), tag_size, C.MUTED)
        badge_x = C.WIDTH - self._corner.get_width() - 14
        badge_y = max(6, (C.HEADER_H - self._corner.get_height()) // 2)
        surface.blit(self._corner, (badge_x, badge_y))
        if C.WIDTH >= 1320:
            text(surface, "Retail sales", (badge_x - 108, 12), 14, C.GOLD, True)
            text(surface, C.PIPELINE, (badge_x - 220, 34), 13, C.MUTED)

        pygame.draw.rect(surface, (8, 12, 20), (0, C.HEIGHT - C.FOOTER_H, C.WIDTH, C.FOOTER_H))
        pygame.draw.line(surface, C.PANEL_EDGE, (0, C.HEIGHT - C.FOOTER_H), (C.WIDTH, C.HEIGHT - C.FOOTER_H), 1)
        text(
            surface,
            "Tasks: " + C.TRY + "     Ctrl+L load     Ctrl+I insights     F12 demo     ESC",
            (24, C.HEIGHT - 30),
            13,
            C.MUTED,
        )


def dialogue(surface: pygame.Surface, user_text: str, robot_text: str, x: int = 28, w: int = 340) -> None:
    y = C.HEIGHT - C.FOOTER_H - C.CMD_H - 58
    pygame.draw.rect(surface, C.CARD, (x, y, w, 52), border_radius=8)
    pygame.draw.rect(surface, C.PANEL_EDGE, (x, y, w, 52), 1, border_radius=8)
    chars = max(22, (w - 60) // 8)
    text(surface, "YOU", (x + 12, y + 6), 10, C.CYAN, True)
    text(surface, wrap(user_text or "Waiting for a request", chars), (x + 48, y + 6), 13, C.WHITE)
    text(surface, "AI", (x + 12, y + 30), 10, C.GOLD, True)
    text(surface, wrap(robot_text or "Ready to present.", chars), (x + 48, y + 29), 13, C.GOLD)


def speech_bubble(surface: pygame.Surface, robot: Robot, caption: str, min_x: int = 16) -> None:
    lines = wrap_lines(caption, 36, 4)
    if not lines:
        return
    f = font(14, True)
    imgs = [f.render(line, True, C.WHITE) for line in lines]
    w = max(img.get_width() for img in imgs) + 24
    h = 18 + 18 * len(imgs)
    x = max(min_x, int(robot.x - w // 2))
    x = min(x, C.STAGE_W - w - 8)
    y = max(C.HEADER_H + 8, int(robot.y - 250))
    pygame.draw.rect(surface, (8, 16, 28), (x, y, w, h), border_radius=8)
    pygame.draw.rect(surface, C.GOLD, (x, y, w, 4), border_radius=2)
    pygame.draw.rect(surface, C.GOLD, (x, y, w, h), 1, border_radius=8)
    text(surface, "RAJA", (x + 10, y + 6), 11, C.GOLD, True)
    for i, img in enumerate(imgs):
        surface.blit(img, (x + 10, y + 22 + i * 16))

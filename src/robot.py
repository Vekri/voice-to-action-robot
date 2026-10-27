"""Glossy white companion robot: poses, queued actions, and renderer."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import pygame

from . import config as C

Vec = Tuple[float, float]
Pose = Dict[str, float]


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def polar(origin: Vec, length: float, angle: float) -> Vec:
    return (origin[0] + math.sin(angle) * length, origin[1] - math.cos(angle) * length)


REST: Pose = {
    "torso": 0.08,
    "head": 0.0,
    "l_shoulder": 0.55,
    "l_elbow": 0.35,
    "l_hand": 0.0,
    "r_shoulder": -0.55,
    "r_elbow": -0.35,
    "r_hand": 0.0,
    "l_hip": 0.12,
    "l_knee": 0.08,
    "r_hip": -0.12,
    "r_knee": -0.08,
}

SIT: Pose = {
    "torso": 0.18,
    "head": 0.05,
    "l_shoulder": 0.7,
    "l_elbow": 0.9,
    "l_hand": 0.2,
    "r_shoulder": -0.7,
    "r_elbow": -0.9,
    "r_hand": -0.2,
    "l_hip": 1.15,
    "l_knee": 1.35,
    "r_hip": 1.15,
    "r_knee": 1.35,
}

WAVE_BASE: Pose = dict(REST)
WAVE_BASE["r_shoulder"] = -2.35
WAVE_BASE["r_elbow"] = -0.15


def idle_pose(clock: float) -> Pose:
    p = dict(REST)
    breathe = 0.03 * math.sin(clock * 2.1)
    p["torso"] = REST["torso"] + breathe
    p["head"] = 0.04 * math.sin(clock * 1.3)
    return p


def mix(a: Pose, b: Pose, t: float) -> Pose:
    t = ease_in_out(t)
    return {k: lerp(a[k], b.get(k, a[k]), t) for k in a}


def gait(elapsed: float, amp: float = 30.0) -> Pose:
    p = dict(REST)
    swing = math.sin(elapsed * 7.2)
    p["l_hip"] = 0.12 + swing * (amp / 90.0)
    p["r_hip"] = -0.12 - swing * (amp / 90.0)
    p["l_knee"] = 0.08 + max(0.0, -swing) * 0.45
    p["r_knee"] = -0.08 + max(0.0, swing) * 0.45
    p["l_shoulder"] = 0.55 - swing * 0.55
    p["r_shoulder"] = -0.55 + swing * 0.55
    p["torso"] = 0.08 + 0.04 * math.sin(elapsed * 7.2)
    return p


@dataclass
class Action:
    name: str
    label: str
    tool: str
    duration: float
    pose_fn: Callable[[float, float], Pose]
    vx: float = 0.0
    vy_fn: Optional[Callable[[float], float]] = None
    facing_delta: float = 0.0
    speak: str = ""
    message: str = ""
    interruptible: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)


def make_action(kind: str, params: Optional[Dict[str, Any]] = None) -> Action:
    params = dict(params or {})
    kind = (kind or "idle").lower()
    direction = str(params.get("direction") or "forward").lower()
    distance = float(params.get("distance") or 2.0)
    count = int(params.get("count") or 1)

    def _walk_fn(u: float, e: float) -> Pose:
        return gait(e, 30.0)

    def _run_fn(u: float, e: float) -> Pose:
        return gait(e, 42.0)

    def _wave_fn(u: float, e: float) -> Pose:
        p = dict(WAVE_BASE)
        p["r_elbow"] = -0.15 + 0.55 * math.sin(e * 10.0)
        p["r_hand"] = 0.4 * math.sin(e * 10.0)
        p["head"] = 0.08 * math.sin(e * 3.0)
        return mix(REST, p, min(1.0, u * 3.0) if u < 0.85 else max(0.0, (1.0 - u) * 6.0))

    def _present_fn(u: float, e: float) -> Pose:
        p = dict(REST)
        p["l_shoulder"] = -0.2
        p["l_elbow"] = -0.1
        p["r_shoulder"] = -1.6
        p["r_elbow"] = -0.4
        p["head"] = -0.12
        return mix(REST, p, ease_in_out(min(1.0, u * 2.5)))

    def _jump_fn(u: float, e: float) -> Pose:
        p = dict(REST)
        p["l_hip"] = 0.35
        p["r_hip"] = 0.35
        p["l_knee"] = 0.55
        p["r_knee"] = 0.55
        p["l_shoulder"] = 1.1
        p["r_shoulder"] = -1.1
        return mix(REST, p, math.sin(min(1.0, u) * math.pi))

    def _sit_fn(u: float, e: float) -> Pose:
        return mix(REST, SIT, u)

    def _stand_fn(u: float, e: float) -> Pose:
        return mix(SIT, REST, u)

    def _dance_fn(u: float, e: float) -> Pose:
        p = dict(REST)
        beat = math.sin(e * 8.5)
        p["torso"] = 0.12 + 0.18 * beat
        p["head"] = 0.2 * math.sin(e * 6.0)
        p["l_shoulder"] = 0.9 + 0.8 * beat
        p["r_shoulder"] = -0.9 - 0.8 * beat
        p["l_elbow"] = 0.6 + 0.5 * math.cos(e * 8.5)
        p["r_elbow"] = -0.6 - 0.5 * math.cos(e * 8.5)
        p["l_hip"] = 0.35 * beat
        p["r_hip"] = -0.35 * beat
        return p

    def _turn_fn(u: float, e: float) -> Pose:
        p = dict(REST)
        p["torso"] = 0.08 + 0.4 * math.sin(u * math.pi)
        p["head"] = 0.35 * math.sin(u * math.pi)
        return p

    def _stop_fn(u: float, e: float) -> Pose:
        return mix(gait(e, 12.0), REST, u)

    if kind in {"walk", "walk_forward"}:
        dur = max(1.2, distance * 55.0 / C.WALK_SPEED)
        vx = -C.WALK_SPEED if "back" in direction else C.WALK_SPEED
        return Action(
            "walk",
            "WALKING",
            f"robot.walk(distance={distance:g})",
            dur,
            _walk_fn,
            vx=vx,
            speak="Walking now.",
            message="Walking as asked.",
            payload={"distance": distance, "direction": direction},
        )
    if kind in {"run", "sprint"}:
        dur = max(1.0, distance * 55.0 / C.RUN_SPEED)
        vx = -C.RUN_SPEED if "back" in direction else C.RUN_SPEED
        return Action(
            "run",
            "RUNNING",
            f"robot.run(distance={distance:g})",
            dur,
            _run_fn,
            vx=vx,
            speak="Running now.",
            message="Running as asked.",
            payload={"distance": distance, "direction": direction},
        )
    if kind in {"jump", "leap"}:
        hops = max(1, min(6, count))
        return Action(
            "jump",
            "JUMPING",
            f"robot.jump(count={hops})",
            0.7 * hops,
            _jump_fn,
            vy_fn=lambda u: -48.0 * math.sin(min(1.0, (u * hops) % 1.0) * math.pi),
            speak="Jumping.",
            payload={"count": hops},
        )
    if kind == "wave":
        return Action("wave", "WAVING", "robot.wave()", 1.8, _wave_fn, speak="Hello. I am Raja.")
    if kind == "sit":
        return Action("sit", "SITTING", "robot.sit()", 1.1, _sit_fn, speak="Sitting down.")
    if kind == "stand":
        return Action("stand", "STANDING", "robot.stand()", 1.0, _stand_fn, speak="Standing up.")
    if kind == "dance":
        return Action("dance", "DANCING", "robot.dance()", 4.0, _dance_fn, speak="Dancing now.")
    if kind == "music":
        return Action(
            "music",
            "PLAYING MUSIC",
            "robot.play_jam()",
            5.2,
            _dance_fn,
            speak="Playing a short original jam. I will dance for five seconds.",
            message="Playing a short original jam.",
        )
    if kind in {"turn", "turn_left", "turn_right"}:
        if "left" in kind or direction == "left":
            speak = "Turning left."
            label = "TURNING LEFT"
            tool = "robot.turn(direction='left')"
        else:
            speak = "Turning right."
            label = "TURNING RIGHT"
            tool = "robot.turn(direction='right')"
        return Action("turn", label, tool, 0.85, _turn_fn, facing_delta=180.0, speak=speak)
    if kind == "stop":
        return Action(
            "stop",
            "STOPPED",
            "robot.stop()",
            0.35,
            _stop_fn,
            speak="Halting.",
            message="Stopping now.",
            interruptible=True,
        )
    if kind in {"load", "load_data"}:
        source = str(params.get("source", "retail_sales.csv"))
        return Action(
            "load",
            "LOADING DATA",
            f"robot.load_data(source='{source}')",
            0.9,
            _present_fn,
            speak="Loading the retail sales data now.",
            message="Loading the retail sales data now.",
            payload={"source": source},
        )
    if kind in {"visualize", "chart", "plot"}:
        chart = str(params.get("chart", "bar")).lower()
        metric = str(params.get("metric", "")).lower()
        label = f"{metric} {chart}" if metric else chart
        return Action(
            "visualize",
            "VISUALIZING",
            f"robot.visualize(chart='{chart}'{f', metric={metric!r}' if metric else ''})",
            2.4,
            _present_fn,
            speak=f"Here is the {label} chart." if metric else "Here is the result.",
            message=f"Here is the {label} chart." if metric else "Here is the result.",
            payload={"chart": chart, "metric": metric},
        )
    if kind in {"insights", "analyze", "analyse"}:
        return Action(
            "insights",
            "ANALYZING",
            "robot.analyze()",
            1.6,
            _present_fn,
            speak="Here is a short brief.",
            message="Here is a short brief.",
        )
    if kind == "talk":
        reply = str(params.get("reply") or "I am here and ready.")
        dur = min(10.0, max(2.8, 0.42 * len(reply.split()) + 1.1))
        return Action(
            "talk",
            "SPEAKING",
            "robot.say()",
            dur,
            _wave_fn,
            speak=reply,
            message=reply,
            payload={"reply": reply},
        )
    return Action("idle", "IDLE", "robot.idle()", 0.4, lambda u, e: idle_pose(e), speak="")


class Robot:
    """World-space articulated robot with queued cinematic actions."""

    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.base_y = y
        self.facing = 1.0
        self.pose: Pose = dict(REST)
        self.queue: List[Action] = []
        self.current: Optional[Action] = None
        self.t = 0.0
        self.elapsed = 0.0
        self.clock = 0.0
        self.seated = False
        self.status = "IDLE"
        self.tool_line = "robot.idle()"
        self.last_completed = ""
        self.complete_tick = 0
        self.busy = False
        self.air_y = 0.0
        self._flipped = False
        self.caption = ""
        self.min_x = 80.0
        self.max_x = float(C.STAGE_W - 70)
        self.hold_speech = False
        self.talking = False

    def enqueue(self, actions: List[Action], replace: bool = False) -> None:
        if replace or (actions and actions[0].name == "stop"):
            self.queue.clear()
            self.current = None
            self.t = 0.0
            self.air_y = 0.0
        if self.seated and actions and actions[0].name not in {"sit", "stand", "stop"}:
            actions = [make_action("stand")] + list(actions)
        self.queue.extend(actions)
        self.busy = True

    def clear(self) -> None:
        self.queue.clear()
        self.current = None
        self.busy = False
        self.status = "IDLE"
        self.tool_line = "robot.stop()"
        self.air_y = 0.0

    def update(self, dt: float) -> Optional[str]:
        self.clock += dt
        speak: Optional[str] = None

        if self.current is None:
            if self.queue:
                self.current = self.queue.pop(0)
                self.t = 0.0
                self.elapsed = 0.0
                self._flipped = False
                self.status = self.current.label
                self.tool_line = self.current.tool
                self.caption = self.current.message or self.current.speak
                speak = self.current.speak
                if self.current.name == "sit":
                    self.seated = True
                elif self.current.name == "stand":
                    self.seated = False
            else:
                self.busy = False
                if self.status not in {"IDLE", "COMPLETED"}:
                    self.last_completed = self.status
                    self.complete_tick += 1
                    self.status = "COMPLETED"
                if not self.seated:
                    self.pose = idle_pose(self.clock)
                    self.air_y = lerp(self.air_y, 0.0, min(1.0, dt * 8))
                else:
                    self.pose = SIT
                self.y = self.base_y + self.air_y
                return None

        assert self.current is not None
        self.t += dt
        self.elapsed += dt
        u = min(1.0, self.t / max(0.001, self.current.duration))
        self.pose = self.current.pose_fn(u, self.elapsed)

        if self.current.vx:
            self.x += self.current.vx * self.facing * dt
            if self.x > self.max_x:
                self.x = self.max_x
                self.facing = -1.0
            elif self.x < self.min_x:
                self.x = self.min_x
                self.facing = 1.0

        if self.current.vy_fn:
            self.air_y = self.current.vy_fn(u)
        elif self.current.name == "sit":
            self.air_y = lerp(0, 42, ease_in_out(u))
        elif self.current.name == "stand":
            self.air_y = lerp(42, 0, ease_in_out(u))
        else:
            self.air_y = lerp(self.air_y, 0.0, min(1.0, dt * 6))

        if self.current.facing_delta and u >= 0.5 and not self._flipped:
            self.facing *= -1.0
            self._flipped = True

        self.y = self.base_y + self.air_y

        if u >= 1.0:
            if self.hold_speech:
                loop = (self.elapsed % max(0.4, self.current.duration)) / max(0.4, self.current.duration)
                self.pose = self.current.pose_fn(loop, self.elapsed)
                return speak
            self.current = None
            self.t = 0.0
            if not self.queue:
                self.busy = False
                if self.status != "COMPLETED":
                    self.complete_tick += 1
                self.status = "COMPLETED"
        return speak


@dataclass
class Joints:
    hip: Vec
    chest: Vec
    core: Vec
    head: Vec
    l_shoulder: Vec
    l_elbow: Vec
    l_hand: Vec
    r_shoulder: Vec
    r_elbow: Vec
    r_hand: Vec
    l_hip: Vec
    l_knee: Vec
    l_foot: Vec
    r_hip: Vec
    r_knee: Vec
    r_foot: Vec


def solve_skeleton(origin: Vec, pose: Pose, facing: float) -> Joints:
    hip = origin
    chest = polar(hip, 68, pose["torso"])
    core = (chest[0] * 0.35 + hip[0] * 0.65, chest[1] * 0.42 + hip[1] * 0.58)
    head = polar(chest, 62, pose["head"])
    sh_sep = 26
    l_sh = (chest[0] - sh_sep, chest[1] + 4)
    r_sh = (chest[0] + sh_sep, chest[1] + 4)
    l_el = polar(l_sh, 50, pose["l_shoulder"])
    r_el = polar(r_sh, 50, pose["r_shoulder"])
    l_hand = polar(l_el, 46, pose["l_elbow"] + pose.get("l_hand", 0))
    r_hand = polar(r_el, 46, pose["r_elbow"] + pose.get("r_hand", 0))
    l_h = (hip[0] - 12, hip[1] + 4)
    r_h = (hip[0] + 12, hip[1] + 4)
    l_k = polar(l_h, 46, pose["l_hip"] + math.pi)
    r_k = polar(r_h, 46, pose["r_hip"] + math.pi)
    l_f = polar(l_k, 46, pose["l_knee"] + math.pi)
    r_f = polar(r_k, 46, pose["r_knee"] + math.pi)
    if facing < 0:
        def flip(p: Vec) -> Vec:
            return (2 * origin[0] - p[0], p[1])

        return Joints(
            hip, flip(chest), flip(core), flip(head),
            flip(r_sh), flip(r_el), flip(r_hand),
            flip(l_sh), flip(l_el), flip(l_hand),
            flip(r_h), flip(r_k), flip(r_f),
            flip(l_h), flip(l_k), flip(l_f),
        )
    return Joints(
        hip, chest, core, head,
        l_sh, l_el, l_hand, r_sh, r_el, r_hand,
        l_h, l_k, l_f, r_h, r_k, r_f,
    )


def _ellipse(surface: pygame.Surface, color, cx: float, cy: float, w: float, h: float, width: int = 0) -> pygame.Rect:
    box = pygame.Rect(0, 0, max(2, int(w)), max(2, int(h)))
    box.center = (int(cx), int(cy))
    pygame.draw.ellipse(surface, color, box, width)
    return box


def _stubby_arm(surface: pygame.Surface, sx: float, sy: float, hx: float, hy: float, white, shade) -> None:
    dx, dy = hx - sx, hy - sy
    length = math.hypot(dx, dy) or 1.0
    cap = 36.0
    if length > cap:
        dx, dy = dx * cap / length, dy * cap / length
    mx, my = sx + dx * 0.85, sy + dy * 0.85
    pygame.draw.line(surface, white, (sx, sy), (mx, my), 22)
    pygame.draw.circle(surface, white, (int(sx), int(sy)), 12)
    pygame.draw.circle(surface, white, (int(mx), int(my)), 14)
    pygame.draw.circle(surface, shade, (int(mx + 3), int(my + 4)), 6)


class RobotRenderer:
    def __init__(self) -> None:
        self._blink = 0.0

    def draw(self, surface: pygame.Surface, robot: Robot) -> None:
        j = solve_skeleton((robot.x, robot.y), robot.pose, robot.facing)
        self._blink += 0.016
        wink = math.sin(self._blink * 0.55) > 0.96
        white = (236, 240, 246)
        shade = (198, 206, 216)
        visor = (18, 28, 40)
        glow = (80, 230, 255)

        bx, by = int(j.core[0]), int(j.core[1] + 18)
        hx, hy = int(j.chest[0]), int(j.chest[1] - 38)

        shadow = pygame.Surface((130, 28), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 50), shadow.get_rect())
        surface.blit(shadow, (bx - 65, int(robot.y) + 18))

        _stubby_arm(surface, bx - 38, by - 18, j.l_hand[0], j.l_hand[1], white, shade)
        _stubby_arm(surface, bx + 38, by - 18, j.r_hand[0], j.r_hand[1], white, shade)

        _ellipse(surface, shade, bx, by + 4, 104, 122)
        _ellipse(surface, white, bx, by, 100, 118)
        _ellipse(surface, (250, 252, 255), bx - 16, by - 22, 36, 28)
        _ellipse(surface, (220, 228, 236), bx, by, 100, 118, 2)

        _ellipse(surface, shade, hx, hy + 4, 92, 84)
        _ellipse(surface, white, hx, hy, 90, 82)
        _ellipse(surface, (250, 252, 255), hx - 16, hy - 16, 28, 18)
        _ellipse(surface, (220, 228, 236), hx, hy, 90, 82, 2)

        _ellipse(surface, visor, hx, hy + 6, 70, 46)
        _ellipse(surface, (28, 42, 58), hx, hy + 4, 64, 40)

        eye_y = hy + 2
        if wink:
            pygame.draw.line(surface, glow, (hx - 18, eye_y), (hx - 8, eye_y + 2), 3)
            pygame.draw.line(surface, glow, (hx + 8, eye_y + 2), (hx + 18, eye_y), 3)
        else:
            pygame.draw.circle(surface, glow, (hx - 14, eye_y), 4)
            pygame.draw.circle(surface, glow, (hx + 14, eye_y), 4)
            pygame.draw.circle(surface, (200, 255, 255), (hx - 15, eye_y - 1), 2)
            pygame.draw.circle(surface, (200, 255, 255), (hx + 13, eye_y - 1), 2)

        if robot.talking:
            open_h = 6 + int(4 * abs(math.sin(robot.clock * 14)))
            _ellipse(surface, glow, hx, hy + 16, 12, open_h)
        else:
            pygame.draw.circle(surface, glow, (hx, hy + 16), 4)

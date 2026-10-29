"""Main application: Human → Voice → AI Agent → Python Tools → Robot."""

from __future__ import annotations

import asyncio
import re
import sys
from collections import deque

import pygame

from . import config as C
from .agent import Agent
from .data_viz import DataStore, HoloDeck
from .icon import apply_window_icon
from .music import Jukebox
from .robot import Robot, RobotRenderer, make_action
from .ui import Chrome, ControlPanel, Stage, dialogue, font, speech_bubble, text, wrap
from .voice import VoiceIO


class Todo:
    def __init__(self, title: str, action_name: str) -> None:
        self.title = title
        self.action_name = action_name
        self.status = "pending"


def _todo_title(action) -> str:
    name = action.name
    payload = getattr(action, "payload", {}) or {}
    if name == "load":
        return "Load the retail sales data and show the table"
    if name == "visualize":
        metric = str(payload.get("metric") or "the data")
        chart = str(payload.get("chart") or "bar")
        return f"Present the {metric} {chart} chart"
    if name == "insights":
        return "Explain the key takeaways"
    if name == "talk":
        return "Answer out loud"
    if name == "walk":
        return "Walk as asked"
    if name == "run":
        return "Run as asked"
    if name == "wave":
        return "Wave"
    if name == "jump":
        return "Jump"
    if name == "dance":
        return "Dance"
    if name == "sit":
        return "Sit down"
    if name == "stand":
        return "Stand up"
    if name == "turn":
        return "Turn"
    if name == "music":
        return "Play a 5 second jam and dance"
    if name == "stop":
        return "Stop"
    return action.label.title() if getattr(action, "label", "") else name.title()


# Numeric key codes. The browser build of pygame does not expose K_1 at import time.
HOTKEYS = {
    49: "walk forward two meters",
    50: "run five meters",
    51: "jump twice",
    52: "wave at me",
    53: "sit down",
    54: "stand up",
    55: "dance",
    56: "turn left",
    57: "turn right",
    48: "stop",
    108: "load data",
    118: "show bar chart",
    112: "show pie chart",
    110: "show line chart",
    97: "show area chart",
    100: "show donut chart",
    111: "show orders bar chart",
    114: "show revenue bar chart",
    99: "show customers bar chart",
    105: "analyze the data",
    109: "play music",
}

LINKEDIN_DEMO = (
    (0.6, None),
    (0.5, "hello Raja how are you"),
    (0.7, "walk forward two meters"),
    (0.5, "wave at me"),
    (0.6, "load csv"),
    (0.8, "show orders"),
    (0.6, "analyze the data"),
    (0.5, "dance"),
    (0.7, "__close__"),
)


class App:
    def __init__(self, demo: bool = False) -> None:
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(C.TITLE)
        width, height = C.fit_desktop()
        flags = 0 if sys.platform == "emscripten" else pygame.RESIZABLE
        if sys.platform != "emscripten" and hasattr(pygame, "WINDOWMAXIMIZED"):
            flags |= pygame.WINDOWMAXIMIZED
        self.screen = pygame.display.set_mode((width, height), flags)
        self.icon = apply_window_icon()
        self.clock = pygame.time.Clock()
        self.robot = Robot(C.STAGE_W * 0.52, C.ROBOT_Y)
        self.renderer = RobotRenderer()
        self.agent = Agent()
        self.voice = VoiceIO()
        self.stage = Stage()
        self.panel = ControlPanel()
        self.chrome = Chrome()
        self.log: deque[str] = deque(maxlen=24)
        self.phase = "listen"
        self.phase_until = 0.0
        self.time = 0.0
        self.typing = True
        self.typed = ""
        pygame.key.start_text_input()
        self.flash = ""
        self.flash_until = 0.0
        self.running = True
        self.intro_until = 2.4 if demo else 4.2
        self.demo = demo
        self.demo_i = 0
        self.demo_wait = 0.0
        self.demo_done = False
        self.data = DataStore()
        self.holo = HoloDeck()
        self.jukebox = Jukebox()
        self.user_text = ""
        self.robot_text = C.TASKS
        self.todos: list[Todo] = []
        self._speech_started = 0.0
        self._heard_speech = False
        self._tasks_announced = True
        self._done_tick = 0
        self._complete_pending = False
        self._last_utterance = ""
        self._last_utterance_at = -10.0
        self._web_hello = False
        self.log.appendleft("SYSTEM  Raja online")
        self.log.appendleft("AGENT   Natural-language tools armed")
        if self.voice.available:
            self.log.appendleft("VOICE   Continuous microphone listening")
        else:
            self.log.appendleft(f"VOICE   {self.voice.error or 'fallback mode'}")

    async def run(self) -> None:
        self.voice.start()
        hello = (
            "Hello. I am Raja. Don't ask AI. Assign the task. "
            "I load retail sales data, draw the chart, speak the insight, dance, "
            "and answer your questions like a person."
        )
        if sys.platform != "emscripten":
            self.voice.speak(hello)
        else:
            self.robot_text = "Click once, then type a task in the Ask box."
            self.log.appendleft("VOICE   Click once to unlock speaker")
            self._web_hello_line = hello
        try:
            while self.running:
                dt = self.clock.tick(C.FPS) / 1000.0
                self.time += dt
                self.voice.poll()
                self._events()
                self._ingest_voice()
                await asyncio.sleep(0)
                self._demo_tick(dt)
                speak = self.robot.update(dt)
                if speak:
                    self.phase = "action"
                    self.phase_until = self.time + 0.8
                    self._apply_data_tool()
                    self.robot_text = self.robot.caption or speak
                    self.voice.speak(self.robot_text)
                    if self.voice.last_error:
                        self.log.appendleft(f"VOICE   {self.voice.last_error}")
                    current = self.robot.current
                    self.robot.hold_speech = bool(
                        current and current.name in {"talk", "insights", "visualize", "load"}
                    )
                    self._speech_started = self.time
                    self._heard_speech = False
                    self._mark_todo("doing")
                    self.log.appendleft(f"TOOL    {self.robot.tool_line}")
                    self.log.appendleft(f"TEXT    {self.robot_text}")
                self._release_speech_hold()
                self.data.update(dt)
                self.holo.update(dt)
                self._park_robot(dt)
                if (
                    not self.robot.busy
                    and self.robot.status == "COMPLETED"
                    and self.phase == "action"
                    and self._done_tick != self.robot.complete_tick
                ):
                    self.phase = "status"
                    self.phase_until = self.time + 1.8
                    self._done_tick = self.robot.complete_tick
                    self._complete_pending = True
                if self._complete_pending:
                    self._complete_pending = False
                    self._finish_tasks()
                    self.log.appendleft("STATUS  Task complete")
                if self.time > self.phase_until and self.phase in {"understand", "status"} and not self.robot.busy:
                    self.phase = "listen"
                self.stage.update(dt)
                self.panel.update(dt)
                self.robot.talking = bool(self.voice.speaking) or (
                    self.robot.current is not None and self.robot.current.name == "talk"
                )
                self._draw()
        finally:
            self.voice.shutdown()
            if sys.platform != "emscripten":
                pygame.quit()

    def _unlock_web_voice(self) -> None:
        if sys.platform != "emscripten":
            return
        was_locked = not getattr(self.voice, "_web_unlocked", True)
        self.voice.unlock_web_audio()
        if was_locked and not self._web_hello:
            self._web_hello = True
            line = getattr(self, "_web_hello_line", "")
            if line:
                self.voice.speak(line)
                self.robot_text = line
                self.log.appendleft("VOICE   Speaker unlocked")

    def _events(self) -> None:
        for event in pygame.event.get():
            if event.type in {pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN, pygame.TEXTINPUT}:
                self._unlock_web_voice()
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE and sys.platform != "emscripten":
                if event.w == C.WIDTH and event.h == C.HEIGHT:
                    continue
                C.apply_size(event.w, event.h)
                self.screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT), pygame.RESIZABLE)
                self._sync_layout()
            elif event.type == pygame.TEXTINPUT and self.typing:
                if event.text and event.text.isprintable() and event.text not in "\r\n\t":
                    self.typed += event.text
            elif event.type == pygame.KEYDOWN:
                ctrl = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)
                if event.key == 27:
                    if self.typed:
                        self.typed = ""
                    elif self.typing:
                        self.typing = False
                        pygame.key.stop_text_input()
                    else:
                        self.running = False
                elif event.key == 13:
                    if self.typed.strip():
                        self._dispatch(self.typed)
                        self.typed = ""
                    self.typing = True
                    pygame.key.start_text_input()
                elif event.key == 8 and self.typing:
                    self.typed = self.typed[:-1]
                elif ctrl and event.key in HOTKEYS:
                    self._dispatch(HOTKEYS[event.key])
                elif not self.typing and event.key == 116:
                    self.typing = True
                    pygame.key.start_text_input()
                elif event.key == 1073741893:
                    self._start_demo()
                elif not self.typing and event.key in HOTKEYS:
                    self._dispatch(HOTKEYS[event.key])
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._type_rect().collidepoint(event.pos):
                    self.typing = True
                    pygame.key.start_text_input()
                else:
                    self._click_briefing(event.pos)

    def _ingest_voice(self) -> None:
        while True:
            uttered = self.voice.pop_command()
            if not uttered:
                return
            self._dispatch(uttered)

    def _own_echo(self, utterance: str) -> bool:
        text_in = re.sub(r"\s+", " ", (utterance or "").strip().lower())
        if not text_in:
            return True
        if re.search(r"i have completed the task|task complete|completed the task", text_in):
            return True
        last = re.sub(r"\s+", " ", (getattr(self.voice, "_last_spoken", "") or "").strip().lower())
        return bool(last and text_in == last)

    def _dispatch(self, utterance: str) -> None:
        utterance = (utterance or "").strip()
        if not utterance or self._own_echo(utterance):
            return
        key = re.sub(r"\s+", " ", utterance.lower())
        if key == self._last_utterance and self.time - self._last_utterance_at < 2.2:
            return
        self._last_utterance = key
        self._last_utterance_at = self.time
        self.phase = "understand"
        self.phase_until = self.time + 0.7
        self.user_text = utterance
        self.robot_text = "Understanding command…"
        self.log.appendleft(f'VOICE   "{utterance}"')
        self.log.appendleft(f'TEXT    YOU: "{utterance}"')
        self.typing = not self.demo
        actions = self.agent.understand(utterance)
        if not actions:
            self.log.appendleft("AGENT   Intent not recognized")
            self.robot_text = "I did not understand that command."
            self.voice.speak(self.robot_text)
            self.flash = "UNKNOWN INTENT"
            self.flash_until = self.time + 1.6
            return
        replace = actions[0].name == "stop"
        self.todos = [Todo(_todo_title(action), action.name) for action in actions]
        self._tasks_announced = False
        self._complete_pending = False
        self.robot.enqueue(actions, replace=replace)
        chain = " → ".join(self.agent.last_plan)
        self.log.appendleft(f"AGENT   {chain}")
        n = len(self.todos)
        ack = (
            "On it. I will speak and act on this task."
            if n == 1
            else f"On it. I have {n} tasks. I will speak and act on each one."
        )
        self.robot_text = ack
        if not self.demo:
            self.voice.speak(ack)
        self.flash = f"{n} TASK{'S' if n != 1 else ''}"
        self.flash_until = self.time + 1.6

    def _start_demo(self) -> None:
        self.demo = True
        self.demo_i = 0
        self.demo_wait = 0.4
        self.demo_done = False
        self.flash = "LINKEDIN DEMO"
        self.flash_until = self.time + 2.0

    def _demo_tick(self, dt: float) -> None:
        if not self.demo or self.demo_done:
            return
        if self.time < self.intro_until:
            return
        if self.robot.busy or self.voice.busy:
            return
        if self.demo_wait > 0:
            self.demo_wait -= dt
            return
        if self.demo_i >= len(LINKEDIN_DEMO):
            self.demo_done = True
            return
        wait, command = LINKEDIN_DEMO[self.demo_i]
        self.demo_i += 1
        self.demo_wait = wait
        if not command:
            return
        if command == "__close__":
            line = C.TAGLINE
            self.user_text = "close the demo"
            self.robot_text = line
            self.robot.caption = line
            self.voice.speak(line)
            self.robot.enqueue([make_action("wave")], replace=True)
            self.demo_done = True
            self.log.appendleft("DEMO    Closing tagline")
            return
        self._dispatch(command)

    def _sync_layout(self) -> None:
        self.robot.base_y = C.ROBOT_Y
        self.robot.y = C.ROBOT_Y + self.robot.air_y
        self.robot.max_x = float(C.STAGE_W - 70)
        if self.data.visible:
            self.robot.min_x = float(C.ROBOT_MIN_X)
            self.robot.x = max(self.robot.min_x, min(self.robot.x, C.ROBOT_X))
        else:
            self.robot.min_x = 80.0
            self.robot.x = max(80.0, min(self.robot.x, self.robot.max_x))

    def _park_robot(self, dt: float) -> None:
        from .robot import lerp

        moving = self.robot.current and self.robot.current.name in {
            "walk", "run", "jump", "dance", "turn", "music",
        }
        if moving:
            self.robot.min_x = 80.0
            return
        if self.data.visible:
            self.robot.min_x = float(C.ROBOT_MIN_X)
            self.robot.x = lerp(self.robot.x, float(C.ROBOT_X), min(1.0, dt * 2.2))
        else:
            self.robot.min_x = 80.0

    def _apply_data_tool(self) -> None:
        action = self.robot.current
        if action is None:
            return
        if action.name == "load":
            self.data.load(action.payload.get("source"))
            name = self.data.title.title() if self.data.loaded else "the file"
            label = "retail sales" if "sale" in name.lower() else name
            cards = {name: val for name, val, _hint in self.data.kpis()}
            growth = cards.get("REVENUE GROWTH", "")
            brief = f" Revenue grew {growth} from January to December." if growth else ""
            self.robot.caption = f"I have loaded the {label} data.{brief}"
            self.robot.min_x = C.ROBOT_MIN_X
            self.robot.x = C.ROBOT_X
        elif action.name == "visualize":
            chart = str(action.payload.get("chart", "bar"))
            metric = str(action.payload.get("metric", ""))
            self.data.visualize(chart, metric)
            raw = (self.data.metric or metric or "the data")
            label = raw.lower()
            if "revenue" in label or "income" in label:
                self.robot.caption = f"This {chart} chart presents monthly {label} in dollars."
            else:
                self.robot.caption = f"This {chart} chart presents monthly {label}."
            self.robot.min_x = C.ROBOT_MIN_X
            self.robot.x = C.ROBOT_X
        elif action.name == "insights":
            self.data.analyze()
            spoken = self.data.insights[0] if self.data.insights else "Briefing ready."
            self.robot.caption = spoken
            self.robot.min_x = C.ROBOT_MIN_X
            self.robot.x = C.ROBOT_X
        elif action.name == "talk":
            self.robot.caption = action.message
        elif action.name == "music":
            self.jukebox.play()
            self.robot.caption = "Playing a short original jam. I will dance for five seconds."
            self.robot.hold_speech = False
        elif action.name == "stop":
            self.jukebox.stop()

    def _mark_todo(self, status: str) -> None:
        if status == "doing":
            for item in self.todos:
                if item.status == "pending":
                    item.status = "doing"
                    return
            return
        for item in reversed(self.todos):
            if item.status == "doing":
                item.status = status
                return

    def _release_speech_hold(self) -> None:
        if not self.robot.hold_speech:
            return
        if self.voice.busy:
            self._heard_speech = True
            return
        if self._heard_speech or self.time - self._speech_started > 0.25:
            self.robot.hold_speech = False
            self._mark_todo("done")

    def _finish_tasks(self) -> None:
        for item in self.todos:
            if item.status != "done":
                item.status = "done"
        if self._tasks_announced:
            return
        self._tasks_announced = True
        if self.demo:
            return
        line = "I have completed the task."
        self.robot_text = line
        self.voice.speak(line)

    def _click_briefing(self, pos) -> None:
        if not self.data.visible:
            return
        hit = self.holo.hit(pos)
        if not hit:
            return
        kind, value = hit
        if kind == "metric":
            view = self.data.mode if self.data.mode not in {"", "table"} else "bar"
            utterance = f"show {view} chart of {value}"
        elif value == "table":
            utterance = "show table chart"
        else:
            metric = self.data.metric or "revenue"
            utterance = f"show {value} chart of {metric}"
        self._dispatch(utterance)

    def _draw(self) -> None:
        self.screen.fill(C.BG)
        self.stage.draw(self.screen, self.robot, self.voice, presenting=self.data.visible)
        self.holo.draw(self.screen, self.data)
        self.renderer.draw(self.screen, self.robot)
        if self.data.visible:
            dlg_x = C.DIALOGUE_X
            dlg_w = max(150, C.STAGE_W - C.DIALOGUE_X - 10)
        else:
            dlg_x = 28
            dlg_w = min(340, C.STAGE_W - 80)
        dialogue(self.screen, self.user_text, self.robot_text, x=dlg_x, w=dlg_w)
        if self.robot.caption:
            speech_bubble(
                self.screen,
                self.robot,
                self.robot.caption,
                min_x=C.CHART_X + C.CHART_W + 8 if self.data.visible else 16,
            )
        else:
            self._nameplate()
        self.panel.draw(self.screen, self.agent, self.robot, self.voice, self.phase, self.log, self.todos)
        self.chrome.draw(self.screen)
        if self.demo:
            self._demo_badge()
        if self.time < self.flash_until and self.flash:
            self._banner(self.flash)
        self._type_box()
        if self.time < self.intro_until:
            self._intro()
        pygame.display.flip()

    def _nameplate(self) -> None:
        x, y = int(self.robot.x), max(C.HEADER_H + 6, int(self.robot.y - 248))
        f = font(14, True)
        img = f.render("RAJA", True, C.CYAN)
        pad = 10
        box = pygame.Rect(x - img.get_width() // 2 - pad, y, img.get_width() + pad * 2, 24)
        pygame.draw.rect(self.screen, (6, 14, 22), box, border_radius=3)
        pygame.draw.rect(self.screen, C.CYAN, box, 1, border_radius=3)
        self.screen.blit(img, (box.x + pad, box.y + 4))

    def _banner(self, msg: str) -> None:
        f = font(22, True)
        img = f.render(msg, True, C.WHITE)
        w, h = img.get_width() + 40, 44
        x = max(16, min((C.STAGE_W - w) // 2, C.STAGE_W - w - 12))
        pygame.draw.rect(self.screen, (8, 16, 28), (x, 8, w, h), border_radius=6)
        pygame.draw.rect(self.screen, C.CYAN, (x, 8, w, h), 1, border_radius=6)
        self.screen.blit(img, (x + 20, 18))

    def _intro(self) -> None:
        fade = 1.0 if self.time < 2.6 else max(0.0, (self.intro_until - self.time) / 1.6)
        veil = pygame.Surface((C.STAGE_W, C.HEIGHT), pygame.SRCALPHA)
        veil.fill((2, 6, 12, int(150 * fade)))
        self.screen.blit(veil, (0, 0))
        text(self.screen, C.TAGLINE, (48, C.HEIGHT // 2 - 40), 28, C.WHITE, True, True)
        text(self.screen, C.SUBLINE, (48, C.HEIGHT // 2 + 4), 20, C.MAGENTA, True)
        text(self.screen, C.PIPELINE, (48, C.HEIGHT // 2 + 36), 16, C.GOLD)
        if self.demo:
            text(self.screen, "Press  Win + Alt + R  to start recording", (48, C.HEIGHT // 2 + 70), 18, C.CYAN, True)

    def _type_rect(self) -> pygame.Rect:
        return pygame.Rect(C.CHART_X, C.HEIGHT - C.FOOTER_H - C.CMD_H, C.CHART_W, C.CMD_H - 4)

    def _type_box(self) -> None:
        box = self._type_rect()
        pygame.draw.rect(self.screen, C.CARD, box, border_radius=8)
        border = C.GOLD if self.typing else C.PANEL_EDGE
        pygame.draw.rect(self.screen, border, box, 1, border_radius=8)
        caret = "_" if self.typing and int(self.time * 2) % 2 == 0 else ""
        if self.typed or self.typing:
            shown = "Ask  ·  " + self.typed + caret
            color = C.GOLD
        else:
            shown = "Ask  ·  " + C.TRY
            color = C.MUTED
        text(self.screen, wrap(shown, max(28, (box.w - 28) // 8)), (box.x + 14, box.y + max(10, box.h // 2 - 10)), 16, color, True)

    def _demo_badge(self) -> None:
        pulse = 0.55 + 0.45 * abs((self.time * 2.0) % 2.0 - 1.0)
        r = 7
        x, y = 28, C.HEADER_H + 14
        pygame.draw.circle(self.screen, (int(220 * pulse), 40, 50), (x, y), r)
        label = "LINKEDIN DEMO  ·  Win+Alt+R record" if not self.demo_done else "DEMO COMPLETE  ·  Win+Alt+R stop"
        text(self.screen, label, (x + 16, y - 8), 14, C.GOLD, True)


def main(demo: bool = False) -> None:
    asyncio.run(App(demo=demo).run())

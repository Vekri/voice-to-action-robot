"""AI Agent: natural-language understanding, tool selection, multi-step plans."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .chat import answer, intro
from .robot import Action, make_action


def infer_chart(text: str) -> str:
    t = (text or "").lower()
    rules = (
        ("donut", ("donut", "doughnut")),
        ("pie", ("pie",)),
        ("area", ("area",)),
        ("hbar", ("horizontal", "hbar")),
        ("line", ("line",)),
        ("table", ("table",)),
        ("bar", ("bar", "column")),
    )
    for kind, keys in rules:
        if any(k in t for k in keys):
            return kind
    return "bar"


def infer_metric(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\borders?\b", t):
        return "orders"
    if re.search(r"\bcustomers?\b", t):
        return "customers"
    if re.search(r"\b(revenue|income)\b", t):
        return "revenue"
    return ""


NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "once": 1, "twice": 2, "thrice": 3, "a": 1, "an": 1,
}


def _num(token: str) -> Optional[float]:
    token = token.lower().replace(",", "")
    if token in NUMBER_WORDS:
        return float(NUMBER_WORDS[token])
    try:
        return float(token)
    except ValueError:
        return None


def extract_number(text: str, default: float) -> float:
    for raw in re.findall(
        r"\b(?:\d+(?:\.\d+)?|once|twice|thrice|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)\b",
        text.lower(),
    ):
        value = _num(raw)
        if value is not None:
            return value
    return default


def _dataset_name(token: Optional[str]) -> str:
    t = (token or "").lower()
    if "sale" in t:
        return "retail_sales.csv"
    return "retail_sales.csv"


@dataclass
class ToolCall:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    intent: str = ""
    tool_repr: str = ""

    def __post_init__(self) -> None:
        if not self.intent:
            self.intent = self.name.upper()
        if not self.tool_repr:
            parts = []
            for k, v in self.params.items():
                if k == "direction" and v == "forward":
                    continue
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                parts.append(f"{k}={v!r}" if isinstance(v, str) else f"{k}={v}")
            self.tool_repr = f"robot.{self.name}({', '.join(parts)})"


def chat_reply(text: str) -> str:
    return answer(text)


_PATTERNS = [
    (
        r"\b(hello|hi|hey|greetings)(?:\s+raja)?\b|\b(how are you|how're you|how's it going|how do you (?:feel|do)|who are you|what(?:'s| is) your name|thank(?:s| you)|what can you do|help me|introduce yourself|good (?:morning|afternoon|evening|night)|are you (?:ok|okay|fine|ready)|nice to meet you)\b",
        "talk",
        lambda m, g: {"reply": chat_reply(m.string)},
    ),
    (
        r"\b(load|open|import|fetch)\b(?:\s+(?:the\s+)?)?(?P<source>data|dataset|csv|file|sales(?:\s+data)?)?",
        "load",
        lambda m, g: {"source": _dataset_name(g.get("source"))},
    ),
    (
        r"\b(play(?:\s+(?:some|the|a))?\s+(?:music|song|jam|track)|play music|music please|put on music)\b",
        "music",
        lambda m, g: {},
    ),
    (
        r"\b(insight|insights|analyze|analyse|explain|summarize|what do you (?:see|think)|tell me about (?:the )?data)\b",
        "insights",
        lambda m, g: {},
    ),
    (
        r"\b(?:show|plot|display|visuali[sz]e|graph)\s+(?:me\s+)?(?:the\s+)?(?:(?P<kind>donut|doughnut|pie|area|line|bar|horizontal|hbar|table)\s+)?(?:(?:chart|graph|data)\s+(?:of|for|by)\s+)?(?P<metric>orders?|revenue|income|customers?)\b",
        "visualize",
        lambda m, g: {"chart": infer_chart(m.group(0)), "metric": infer_metric(m.group(0))},
    ),
    (
        r"\b(?P<metric>orders?|revenue|customers?)\s+(?:(?P<kind>donut|doughnut|pie|area|line|bar|horizontal|hbar|table)\s+)?(?:chart|graph)\b",
        "visualize",
        lambda m, g: {"chart": infer_chart(m.group(0)), "metric": infer_metric(m.group(0))},
    ),
    (
        r"\b(?:((?:donut|doughnut|pie|area|line|bar|horizontal|hbar|table)\s+chart)|visuali[sz]e|plot|show(?:\s+the)?\s+(?:(?:donut|doughnut|pie|area|line|bar|horizontal|table)\s+)?(?:data|chart|graph|sales)|display(?:\s+the)?\s+(?:data|chart))\b(?:\s+(?P<kind>donut|doughnut|pie|area|line|bar|table|hbar))?",
        "visualize",
        lambda m, g: {"chart": infer_chart(m.group(0)), "metric": infer_metric(m.group(0))},
    ),
    (r"\b(stop|halt|freeze|hold on|enough)\b", "stop", lambda m, g: {}),
    (r"\b(sit(?:\s+down)?|take a seat)\b", "sit", lambda m, g: {}),
    (r"\b(stand(?:\s+up)?|get up)\b", "stand", lambda m, g: {}),
    (r"\b(dance|boogie|groove)\b", "dance", lambda m, g: {}),
    (r"\b(wave|greet)\b(?:\s+(?:at\s+me|to\s+me|hello))?", "wave", lambda m, g: {}),
    (
        r"\b(jump|leap|hop)s?\b(?:\s+(?P<n>\d+|once|twice|thrice|one|two|three|four|five|six))?(?:\s+times?)?",
        "jump",
        lambda m, g: {"count": int(extract_number(m.group(0), 1))},
    ),
    (
        r"\b(run|sprint|jog)s?\b(?:\s+(?P<dir>forward|ahead|back(?:wards?)?))?(?:\s+(?P<n>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten))?(?:\s*(?:meters?|metres?|m|steps?))?",
        "run",
        lambda m, g: {
            "distance": extract_number(m.group(0), 4.0),
            "direction": (m.groupdict().get("dir") or "forward"),
        },
    ),
    (
        r"\b(walk|step|go|move)s?\b(?:\s+(?P<dir>forward|ahead|back(?:wards?)?))?(?:\s+(?P<n>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten))?(?:\s*(?:meters?|metres?|m|steps?))?",
        "walk",
        lambda m, g: {
            "distance": extract_number(m.group(0), 2.0),
            "direction": (m.groupdict().get("dir") or "forward"),
        },
    ),
    (
        r"\bturn(?:\s+(?P<dir>left|right))?\b",
        "turn",
        lambda m, g: {"direction": m.groupdict().get("dir") or "left"},
    ),
]


def parse_local(text: str) -> List[ToolCall]:
    calls: List[ToolCall] = []
    used = set()
    for pattern, kind, builder in _PATTERNS:
        for match in re.finditer(pattern, text, flags=re.I):
            span = (match.start(), match.end())
            if any(span[0] < b and a < span[1] for a, b in used) and kind != "talk":
                continue
            if kind == "talk" and calls:
                continue
            params = builder(match, match.groupdict())
            calls.append(ToolCall(kind, params, kind.upper(), ""))
            used.add(span)
            if kind == "stop":
                return [ToolCall("stop", {}, "STOP", "robot.stop()")]
    return calls


def _openai_plan(text: str) -> Optional[List[ToolCall]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        import urllib.request

        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Map the user to a JSON list of tool calls. "
                        'Each item: {"name":"talk|walk|run|jump|wave|sit|stand|dance|turn|stop|load|visualize|insights|music","params":{}}. '
                        "Use load then insights when they say load csv. Reply only JSON."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw = body["choices"][0]["message"]["content"]
        raw = raw.strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        items = json.loads(raw)
        calls = []
        for item in items:
            name = str(item.get("name") or "")
            params = item.get("params") or {}
            if name:
                calls.append(ToolCall(name, params))
        return calls or None
    except Exception:
        return None


def _is_intro(text: str) -> bool:
    t = text.lower()
    work = re.search(
        r"\b(load|show|plot|walk|run|jump|dance|sit|stand|turn|stop|analyze|analyse|"
        r"insight|visuali|csv|chart|play|music|song)\b",
        t,
    )
    greet = re.search(
        r"\b(hello|hi|hey|how are you|who are you|what can you do|help|"
        r"introduce|nice to meet|good (morning|afternoon|evening))\b",
        t,
    )
    return bool(greet and not work)


class Agent:
    def __init__(self) -> None:
        self.last_voice = ""
        self.last_intent = "—"
        self.last_params = "—"
        self.last_tool = "—"
        self.last_plan: List[str] = []
        self.backend = "LOCAL AGENT"
        if os.getenv("OPENAI_API_KEY"):
            self.backend = "OPENAI + TOOLS"

    def understand(self, text: str) -> List[Action]:
        text = (text or "").strip()
        text = re.sub(
            r"^(please\s+|can you\s+|could you\s+|would you\s+|todo[:\s]+|to[- ]do[:\s]+|"
            r"task[:\s]+|add (?:a )?task[:\s]+|do this[:\s]+)",
            "",
            text,
            flags=re.I,
        ).strip()
        self.last_voice = text
        if not text:
            return []

        if _is_intro(text):
            reply = intro(text)
            calls = [ToolCall("talk", {"reply": reply}, "TALK", "robot.say()")]
        else:
            work = re.sub(r"^(hey |hi |hello )?(raja[,:]?\s+)", "", text, flags=re.I).strip()
            calls = _openai_plan(work) or parse_local(work or text)
            if not calls:
                reply = answer(text)
                calls = [ToolCall("talk", {"reply": reply}, "TALK", "robot.say()")]
            for call in calls:
                if call.name == "talk":
                    call.params["reply"] = answer(text)
        chart = infer_chart(text)
        metric = infer_metric(text)
        mentioned_chart = any(
            k in text.lower()
            for k in ("bar", "pie", "line", "area", "donut", "table", "horizontal", "hbar", "column")
        )
        for call in calls:
            if call.name == "visualize":
                if mentioned_chart:
                    call.params["chart"] = chart
                else:
                    call.params.setdefault("chart", "bar")
                if metric:
                    call.params["metric"] = metric
                shown = call.params.get("chart", "bar")
                extra = f", metric='{call.params['metric']}'" if call.params.get("metric") else ""
                call.tool_repr = f"robot.visualize(chart='{shown}'{extra})"
        names = [c.name for c in calls]
        if not calls:
            self.last_intent = "UNKNOWN"
            self.last_params = "—"
            self.last_tool = "—"
            self.last_plan = []
            return []

        actions: List[Action] = []
        plan_labels: List[str] = []
        for call in calls:
            actions.append(make_action(call.name, call.params))
            plan_labels.append(call.intent.replace("_", " "))

        first = calls[0]
        self.last_intent = first.intent.replace("_", " ")
        if len(calls) > 1:
            self.last_intent = " → ".join(plan_labels)
        self.last_params = _pretty_params(first.params, len(calls))
        self.last_tool = first.tool_repr or actions[0].tool
        if len(actions) > 1:
            self.last_tool = " → ".join(a.tool for a in actions[:5])
            if len(actions) > 5:
                self.last_tool += " → …"
        self.last_plan = plan_labels
        return actions


def _pretty_params(params: Dict[str, Any], steps: int) -> str:
    if steps > 1:
        return f"{steps} sequenced tools"
    if "distance" in params:
        dist = params["distance"]
        dist = int(dist) if float(dist).is_integer() else dist
        extra = f", {params['direction']}" if params.get("direction") and params["direction"] != "forward" else ""
        return f"{dist} meters{extra}"
    if "count" in params:
        return f"{params['count']} time(s)"
    if "direction" in params:
        return str(params["direction"])
    if "chart" in params:
        return f"{params.get('chart', 'bar')} chart" + (f" · {params['metric']}" if params.get("metric") else "")
    if "reply" in params:
        return "spoken answer"
    return "—"

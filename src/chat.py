"""Spoken answers for conversation — local first, optional free LLM."""

from __future__ import annotations

import datetime
import re

from .insights import ask_free_llm


def is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if t.endswith("?"):
        return True
    return bool(
        re.match(
            r"^(how|what|who|why|when|where|which|can you|could you|do you|are you|is it|tell me|explain)\b",
            t,
        )
    )


def answer(text: str) -> str:
    t = (text or "").strip()
    local = _local(t)
    llm = None
    if is_question(t) and not _is_simple_greeting(t):
        llm = ask_free_llm(
            f"You are Raja, a friendly robot. Answer this out loud in 2 short sentences: {t}"
        )
    return llm or local


def _is_simple_greeting(text: str) -> bool:
    return bool(
        re.search(
            r"how are you|how's it going|thank|good (morning|afternoon|evening)|hello|hi\b|hey\b|\braja\b",
            text.lower(),
        )
    )


def _local(text: str) -> str:
    t = text.lower().strip()
    now = datetime.datetime.now()

    if re.search(r"how are you|how're you|how's it going|how do you (feel|do)", t) or (
        re.search(r"\b(hello|hi|hey|greetings)\b", t) and re.search(r"\braja\b", t)
    ):
        return intro(t)
    if re.search(r"\b(hello|hi|hey|greetings)\b", t):
        return intro(t)
    if re.search(r"who are you|what(?:'s| is) your name|\braja\b", t):
        return intro(t)
    if re.search(r"thank", t):
        return "You are welcome!"
    if re.search(r"what can you do|help|your (job|purpose|role)|introduce", t):
        return intro(t)
    if re.search(r"good morning", t):
        return "Good morning. I am ready to work with you."
    if re.search(r"good afternoon", t):
        return "Good afternoon. What would you like me to do?"
    if re.search(r"good evening|good night", t):
        return "Good evening. I will stay ready for your next command."
    if re.search(r"are you (ok|okay|fine|ready|real|a robot)", t):
        return "Yes. I am Raja, your robot, and I am ready."
    if re.search(r"nice to meet", t):
        return "Nice to meet you too. Let's get to work."
    if re.search(r"how old", t):
        return "I came online as Raja. I am new, fast, and ready to help."
    if re.search(r"where are you", t):
        return "I am right here on your screen, standing on the stage."
    if re.search(r"what time|the time", t):
        return f"The time is {now.strftime('%I:%M %p')}."
    if re.search(r"what(?:'s| is) the date|what day", t):
        return f"Today is {now.strftime('%A, %B %d, %Y')}."
    if re.search(r"tell me a joke|make me laugh", t):
        return "Why did the robot go on vacation? Because it needed to recharge its batteries."
    if re.search(r"what is ai|what is artificial", t):
        return "Artificial intelligence is software that understands goals and takes actions. That is what I do."
    if re.search(r"who (made|created|built) you", t):
        return "I was built as a voice-to-action robot so humans can talk and I can do the work."
    if re.search(r"i love you|do you love", t):
        return "That is kind. I will keep helping you."
    if re.search(r"weather", t):
        return "I cannot see the sky, but I can load your data and show you a chart."
    math = _math(t)
    if math:
        return math
    if is_question(t):
        return (
            "I hear your question. I can answer simply, or I can load the retail sales data, "
            "draw a chart, and explain the result."
        )
    return "I hear you. I am Raja, and I am ready to act."


def intro(_text: str = "") -> str:
    return (
        "Hello. I am Raja. Speak or type like a person. "
        "Give me a task, or ask me a question — I will answer out loud, then I will act. "
        "I can load the retail sales data and show the table. "
        "I can visualize revenue, orders, or customers as a bar, line, pie, or table. "
        "I can get insights and tell you what the numbers mean. "
        "I can walk, run, jump, wave, sit, turn, and dance. "
        "Ask how I am, what I can do, the time, or anything else. I am here to work with you."
    )


def _math(text: str) -> str:
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(\+|plus|-|minus|x|times|\*|divided by|/)\s*(-?\d+(?:\.\d+)?)", text)
    if not m:
        return ""
    a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
    if op in {"+", "plus"}:
        result = a + b
    elif op in {"-", "minus"}:
        result = a - b
    elif op in {"x", "times", "*"}:
        result = a * b
    else:
        result = a / b if b else 0
    shown = int(result) if float(result).is_integer() else round(result, 2)
    return f"The answer is {shown}."

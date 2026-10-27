"""Local analyst + optional free LLM (Groq, Gemini, Ollama) for data insights."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def _is_money(key: str) -> bool:
    k = (key or "").lower()
    return any(word in k for word in ("revenue", "income", "sale", "sales", "price", "amount", "usd"))


def _num(value: float, money: bool = False) -> str:
    if abs(value) >= 100:
        body = f"{value:,.0f}"
    elif abs(value) >= 10:
        body = f"{value:,.1f}"
    else:
        body = f"{value:g}"
    return f"${body}" if money else body


def _one_series(key: str, series: List[float], labels: List[str]) -> Dict[str, Any]:
    n = len(series)
    total = sum(series)
    avg = total / n
    peak_i = max(range(n), key=lambda i: series[i])
    low_i = min(range(n), key=lambda i: series[i])
    first, last = series[0], series[-1]
    growth = ((last - first) / first * 100.0) if first else 0.0
    slope = (n * sum(i * v for i, v in enumerate(series)) - (n - 1) * n / 2 * total) / max(
        1.0, (n * sum(i * i for i in range(n)) - ((n - 1) * n / 2) ** 2)
    )
    if slope > avg * 0.02:
        trend = "rising"
    elif slope < -avg * 0.02:
        trend = "falling"
    else:
        trend = "stable"
    return {
        "metric": key,
        "n": n,
        "total": total,
        "average": round(avg, 2),
        "peak": {"label": labels[peak_i] if peak_i < len(labels) else str(peak_i), "value": series[peak_i]},
        "low": {"label": labels[low_i] if low_i < len(labels) else str(low_i), "value": series[low_i]},
        "growth_pct": round(growth, 1),
        "trend": trend,
        "first": first,
        "last": last,
        "labels": labels[:12],
        "values": series[:12],
    }


def summarize(
    numeric: Dict[str, List[float]],
    labels: List[str],
    title: str,
    focus: str = "",
) -> Dict[str, Any]:
    series_list = [_one_series(key, values, labels) for key, values in numeric.items() if values]
    if not series_list:
        return {"title": title, "metric": focus or "value", "points": [], "series": []}
    primary = series_list[0]
    if focus:
        for item in series_list:
            if item["metric"].lower() == focus.lower():
                primary = item
                break
    return {**primary, "title": title, "series": series_list}


def local_insights(stats: Dict[str, Any]) -> List[str]:
    extras = [s for s in (stats.get("series") or []) if s.get("n")]
    if not extras and not stats.get("n"):
        return ["No numeric series found. Load the retail sales data to begin."]
    if not extras:
        extras = [stats]
    lines = []
    kpi_bits = []
    for item in extras:
        money = _is_money(item.get("metric", ""))
        kpi_bits.append(f"{item['metric']} growth {item['growth_pct']:.1f}%")
        if money:
            kpi_bits.append(f"average {_num(item['average'], True)}, peak {_num(item['peak']['value'], True)}")
    if kpi_bits:
        lines.append("KPIs: " + "; ".join(kpi_bits) + ".")
    for item in extras:
        money = _is_money(item.get("metric", ""))
        lines.append(
            f"{item['metric']} is {item['trend']}: {_num(item['first'], money)} -> {_num(item['last'], money)} "
            f"({item['growth_pct']:+.1f}%)."
        )
    focus = extras[0]
    peak = focus["peak"]
    low = focus["low"]
    money = _is_money(focus.get("metric", ""))
    lines.append(
        f"{focus['metric']} peak in {peak['label']} at {_num(peak['value'], money)}; "
        f"lowest in {low['label']} at {_num(low['value'], money)}."
    )
    trend = focus["trend"]
    if trend == "rising":
        lines.append("Recommendation: protect Q4 momentum and raise capacity before the next peak.")
    elif trend == "falling":
        lines.append("Recommendation: investigate the drop after the peak and run a recovery campaign.")
    else:
        lines.append("Recommendation: series is flat — test one growth lever instead of more of the same.")
    return lines


def ask_free_llm(prompt: str, system: str = "Answer in 2 short spoken sentences.") -> Optional[str]:
    for fn in (_groq, _gemini, _ollama):
        try:
            text = fn(prompt, system)
        except TypeError:
            try:
                text = fn(prompt)
            except Exception:
                text = None
        except Exception:
            text = None
        if text:
            return text.strip()
    return None


def fetch_llm_insights(stats: Dict[str, Any]) -> Optional[Tuple[str, List[str]]]:
    prompt = (
        "You are Raja, a briefing robot. In 3 short spoken sentences, explain this data. "
        f"{json.dumps({k: stats.get(k) for k in ('title', 'metric', 'trend', 'growth_pct', 'peak', 'low', 'first', 'last')})}"
    )
    for name, fn in (("GROQ LLAMA", _groq), ("GEMINI FLASH", _gemini), ("OLLAMA", _ollama)):
        try:
            text = fn(prompt, "Return only short spoken sentences.")
        except TypeError:
            try:
                text = fn(prompt)
            except Exception:
                text = None
        except Exception:
            text = None
        if text:
            lines = [ln.strip(" -•") for ln in text.replace("\n", ". ").split(".") if ln.strip()]
            return name, lines[:4] or [text.strip()]
    return None


def _post(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float = 8.0) -> Optional[str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if "choices" in body:
        return (body["choices"][0].get("message") or {}).get("content")
    if "candidates" in body:
        parts = body["candidates"][0].get("content", {}).get("parts") or []
        return " ".join(p.get("text", "") for p in parts)
    return None


def _groq(prompt: str, system: str = "Return only short spoken sentences.") -> Optional[str]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    return _post(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": 180,
        },
        {"Authorization": f"Bearer {key}"},
    )


def _gemini(prompt: str, system: str = "") -> Optional[str]:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    text = f"{system}\n{prompt}" if system else prompt
    return _post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        {"contents": [{"parts": [{"text": text}]}]},
        {},
    )


def _ollama(prompt: str, system: str = "") -> Optional[str]:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    data = _post(f"{host}/api/generate", payload, {}, timeout=6.0)
    if data:
        return data
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("response")
    except Exception:
        return None

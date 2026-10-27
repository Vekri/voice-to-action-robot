"""Load CSV/JSON datasets and draw executive charts the robot presents."""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from . import config as C
from .insights import fetch_llm_insights, local_insights, summarize
from .ui import font, text, wrap

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

CHART_KINDS = ("bar", "line", "area", "pie", "donut", "hbar", "table")
PALETTE = [
    (0, 230, 255), (255, 43, 214), (255, 204, 51), (57, 255, 80),
    (255, 140, 40), (140, 170, 255), (255, 110, 140), (80, 255, 210),
    (210, 160, 255), (255, 230, 90), (90, 200, 255), (180, 255, 150),
]


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


def is_money(key: str) -> bool:
    k = (key or "").lower()
    return any(word in k for word in ("revenue", "income", "sale", "sales", "price", "amount", "usd"))


def _fmt(value: float, money: bool = False) -> str:
    if abs(value - round(value)) < 1e-9:
        body = f"{round(value):,}"
    elif abs(value) >= 100:
        body = f"{value:,.0f}"
    elif abs(value) >= 10:
        body = f"{value:,.1f}"
    else:
        body = f"{value:g}"
    return f"${body}" if money else body


def _growth_pct(series: List[float]) -> float:
    first, last = series[0], series[-1]
    if not first:
        return 0.0
    return round((last - first) / first * 100.0 + 1e-12, 1)


def compute_kpis(numeric: Dict[str, List[float]], labels: List[str]) -> List[Tuple[str, str, str]]:
    """Single source of truth for briefing cards and spoken insights."""

    def find(*needles: str) -> List[float]:
        for key, values in numeric.items():
            kl = key.lower()
            if values and any(n in kl for n in needles):
                return values
        return []

    start = labels[0] if labels else "start"
    end = labels[-1] if labels else "end"
    revenue = find("revenue", "sale", "income")
    orders = find("order")
    customers = find("customer")
    cards: List[Tuple[str, str, str]] = []
    if revenue:
        cards.append(
            (
                "REVENUE GROWTH",
                f"{_growth_pct(revenue):.1f}%",
                f"{start} {_fmt(revenue[0], True)} to {end} {_fmt(revenue[-1], True)}",
            )
        )
    if orders:
        cards.append(
            (
                "ORDERS GROWTH",
                f"{_growth_pct(orders):.1f}%",
                f"{start} {orders[0]:.0f} to {end} {orders[-1]:.0f}",
            )
        )
    if customers:
        cards.append(
            (
                "CUSTOMERS GROWTH",
                f"{_growth_pct(customers):.1f}%",
                f"{start} {customers[0]:.0f} to {end} {customers[-1]:.0f}",
            )
        )
    if revenue:
        total = sum(revenue)
        n = len(revenue)
        avg = total / n
        peak_i = max(range(n), key=lambda i: revenue[i])
        peak_lbl = labels[peak_i] if peak_i < len(labels) else end
        cards.append(("TOTAL REVENUE", _fmt(total, True), f"{n} months combined"))
        cards.append(("AVG REVENUE", _fmt(round(avg, 1), True), f"{_fmt(total, True)} / {n} = {_fmt(avg, True)}"))
        cards.append(("PEAK REVENUE", _fmt(max(revenue), True), f"Highest month  {peak_lbl}"))
    if cards:
        return cards
    key = next(iter(numeric), "")
    series = numeric.get(key, [])
    if not series:
        return []
    money = is_money(key)
    return [
        ("GROWTH", f"{_growth_pct(series):.1f}%", f"{start} to {end}"),
        ("AVERAGE", _fmt(sum(series) / len(series), money), f"{len(series)} periods"),
        ("PEAK", _fmt(max(series), money), key.title()),
    ]


def speak_kpis(cards: List[Tuple[str, str, str]]) -> List[str]:
    lookup = {label: value for label, value, _hint in cards}

    def take(name: str) -> str:
        return lookup.get(name, "")

    rev = take("REVENUE GROWTH")
    avg = take("AVG REVENUE")
    peak = take("PEAK REVENUE")
    if rev and avg and peak:
        return [f"Revenue grew {rev}. Average {avg} a month. Peak {peak}."]
    if rev:
        return [f"Revenue grew {rev} from January to December."]
    return ["Load the retail sales data to generate a briefing."]


class DataStore:
    def __init__(self) -> None:
        self.path = ""
        self.title = "NO DATASET"
        self.headers: List[str] = []
        self.rows: List[Dict[str, str]] = []
        self.numeric: Dict[str, List[float]] = {}
        self.labels: List[str] = []
        self.loaded = False
        self.mode = ""
        self.visible = False
        self.reveal = 0.0
        self.status = "Awaiting load_data()"
        self.insight = ""
        self.insights: List[str] = []
        self.insight_source = "LOCAL ANALYST"
        self.metric = ""

    def load(self, source: Optional[str] = None) -> str:
        path = self._resolve(source)
        if path is None:
            self.status = "No retail sales file found in /data"
            self.loaded = False
            return self.status
        if path.suffix.lower() == ".json":
            self._from_json(path)
        else:
            self._from_csv(path)
        self.path = str(path.name)
        stem = path.stem.replace("_", " ").lower()
        if "sale" in stem:
            self.title = "RETAIL SALES"
        else:
            self.title = path.stem.replace("_", " ").upper()
        self.loaded = True
        self.mode = "table"
        self.metric = ""
        self.visible = True
        self.reveal = 0.0
        self.refresh_insights()
        pretty = "Retail sales" if "sale" in stem else self.title.title()
        self.status = f"{pretty}  ·  {len(self.rows)} rows  ·  {len(self.headers)} fields"
        return self.status

    def visualize(self, chart: str = "bar", metric: str = "") -> str:
        if not self.loaded:
            self.load()
        if not self.loaded:
            return self.status
        kind = infer_chart(chart) if chart not in CHART_KINDS else chart
        if kind not in CHART_KINDS:
            kind = "bar"
        self.mode = kind
        self.metric = self.resolve_metric(metric)
        self.visible = True
        self.reveal = 0.0
        self.refresh_insights()
        label = self.metric.title() + (" ($)" if is_money(self.metric) else "")
        self.status = f"{label}  ·  {kind.title()} view"
        return f"Showing {kind} chart of {self.metric}."

    def analyze(self) -> str:
        if not self.loaded:
            self.load()
        if not self.loaded:
            return self.status
        self.visible = True
        self.refresh_insights(use_llm=True)
        first = self.insights[0] if self.insights else "Analysis complete."
        return f"{self.insight_source}: {first}"

    def hide(self) -> None:
        self.visible = False

    def update(self, dt: float) -> None:
        if self.visible:
            self.reveal = min(1.0, self.reveal + dt * 1.35)

    def _resolve(self, source: Optional[str]) -> Optional[Path]:
        DATA_DIR.mkdir(exist_ok=True)
        if source:
            raw = source.strip().strip('"')
            candidate = Path(raw)
            if not candidate.is_file():
                candidate = DATA_DIR / raw
            if not candidate.is_file():
                matches = list(DATA_DIR.glob(f"*{raw}*"))
                candidate = matches[0] if matches else candidate
            if candidate.is_file():
                return candidate
        preferred = DATA_DIR / "retail_sales.csv"
        if preferred.is_file():
            return preferred
        preferred = DATA_DIR / "sales.csv"
        if preferred.is_file():
            return preferred
        found = sorted(DATA_DIR.glob("*.csv")) + sorted(DATA_DIR.glob("*.json"))
        return found[0] if found else None

    def _from_csv(self, path: Path) -> None:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            self.headers = list(reader.fieldnames or [])
            self.rows = [dict(row) for row in reader]
        self._index_numeric()

    def _from_json(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("data") or payload.get("rows") or [payload]
        self.rows = [dict(item) for item in payload]
        self.headers = list(self.rows[0].keys()) if self.rows else []
        self._index_numeric()

    def _index_numeric(self) -> None:
        self.numeric = {}
        self.labels = []
        if not self.rows:
            return
        label_key = self.headers[0] if self.headers else ""
        self.labels = [str(row.get(label_key, i + 1)) for i, row in enumerate(self.rows)]
        for key in self.headers[1:]:
            values: List[float] = []
            ok = True
            for row in self.rows:
                raw = str(row.get(key, "")).replace(",", "").replace("$", "").strip()
                try:
                    values.append(float(raw))
                except ValueError:
                    ok = False
                    break
            if ok and values:
                self.numeric[key] = values

    def _primary_metric(self) -> str:
        return next(iter(self.numeric), "value")

    def kpis(self) -> List[Tuple[str, str, str]]:
        return compute_kpis(self.numeric, self.labels)

    def resolve_metric(self, asked: str) -> str:
        if not asked:
            return self.metric or self._primary_metric()
        token = asked.lower().strip().rstrip("s")
        aliases = {"sale": "revenue", "income": "revenue", "order": "order", "customer": "customer"}
        token = aliases.get(token, token)
        for key in self.numeric:
            kl = key.lower()
            if token == kl or token == kl.rstrip("s") or token in kl:
                return key
        return self._primary_metric()

    def refresh_insights(self, use_llm: bool = True) -> None:
        self.insights = speak_kpis(self.kpis())
        self.insight_source = "LOCAL ANALYST"
        self.insight = self.insights[0] if self.insights else ""
        if use_llm and sys.platform != "emscripten":
            import threading

            stats = summarize(self.numeric, self.labels, self.title, self.metric)
            threading.Thread(target=self._llm_upgrade, args=(stats,), daemon=True).start()

    def _llm_upgrade(self, stats: Dict) -> None:
        result = fetch_llm_insights(stats)
        if not result:
            return
        source, lines = result
        self.insight_source = source
        self.insights = lines
        self.insight = lines[0]


class HoloDeck:
    VIEWS = (("table", "Table"), ("bar", "Bar"), ("line", "Line"), ("pie", "Pie"), ("area", "Area"))

    def __init__(self) -> None:
        self.t = 0.0
        self.rect = pygame.Rect(C.CHART_X, C.CHART_Y, C.CHART_W, C.CHART_H)
        self.hits: List[Tuple[pygame.Rect, str, str]] = []

    def update(self, dt: float) -> None:
        self.t += dt

    def hit(self, pos: Tuple[int, int]) -> Optional[Tuple[str, str]]:
        for rect, kind, value in self.hits:
            if rect.collidepoint(pos):
                return kind, value
        return None

    def draw(self, surface: pygame.Surface, store: DataStore) -> None:
        self.hits = []
        if not store.visible:
            return
        self.rect = pygame.Rect(C.CHART_X, C.CHART_Y, C.CHART_W, C.CHART_H)
        x, y, w, h = self.rect
        prev_clip = surface.get_clip()
        surface.set_clip(self.rect)

        shadow = pygame.Surface((w + 10, h + 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 70), (6, 6, w, h), border_radius=12)
        surface.blit(shadow, (x - 4, y - 2))
        pygame.draw.rect(surface, C.SLIDE, (x, y, w, h), border_radius=12)
        pygame.draw.rect(surface, C.PANEL_EDGE, (x, y, w, h), 1, border_radius=12)
        pygame.draw.rect(surface, C.GOLD, (x, y, 5, h), border_radius=3)

        metric = store.metric or store._primary_metric()
        metric_title = metric.title() + (" ($)" if is_money(metric) else "")
        title = f"{store.title.title()}  ·  {metric_title}" if store.mode != "table" else store.title.title()
        text(surface, "EXECUTIVE BRIEFING", (x + 18, y + 10), 11, C.GOLD, True)
        text(surface, wrap(title, max(18, (w - 40) // 11)), (x + 18, y + 28), 20, C.WHITE, True)
        text(surface, wrap(store.status, max(22, (w - 40) // 8)), (x + 18, y + 50), 12, C.MUTED)

        chip_y = y + 70
        cx = x + 18
        for key in store.numeric:
            on = key.lower() == metric.lower() and store.mode != "table"
            chip = key.title() + (" $" if is_money(key) else "")
            box = self._chip(surface, cx, chip_y, chip, on)
            self.hits.append((box, "metric", key))
            cx = box.right + 8
        cx += 10
        for kind, label in self.VIEWS:
            on = (store.mode or "table") == kind
            box = self._chip(surface, cx, chip_y, label, on, gold=kind == "table")
            self.hits.append((box, "view", kind))
            cx = box.right + 8

        kpis = store.kpis()
        rows = 2 if len(kpis) > 3 and h > 420 else 1
        kpi_h = (80 * rows) if kpis and h > 380 else 0
        insight_h = 72 if h < 400 else 88
        header = 118
        plot = pygame.Rect(x + 16, y + header + kpi_h, w - 32, h - header - kpi_h - insight_h - 12)
        if plot.h < 90:
            insight_h = max(52, h - header - kpi_h - 100)
            plot.h = h - header - kpi_h - insight_h - 12
        if kpis:
            text(surface, "KPIs   Jan to Dec", (x + 18, y + 98), 11, C.GOLD, True)
            self._kpis(surface, kpis, x + 16, y + 114, w - 32, kpi_h - 20)

        if store.mode == "table":
            self._table(surface, store, plot)
        elif store.mode in {"pie", "donut"}:
            self._pie(surface, store, plot, donut=store.mode == "donut")
        elif store.mode == "hbar":
            self._hbar(surface, store, plot)
        elif store.mode == "line":
            self._line(surface, store, plot, fill=False)
        elif store.mode == "area":
            self._line(surface, store, plot, fill=True)
        else:
            self._bars(surface, store, plot)

        self._insights(surface, store, x + 16, y + h - insight_h - 10, w - 32, insight_h)
        surface.set_clip(prev_clip)

    def _chip(self, surface, x, y, label, on, gold: bool = False) -> pygame.Rect:
        f = font(12, True)
        ink = (12, 18, 28) if on else C.WHITE
        img = f.render(label, True, ink)
        box = pygame.Rect(x, y, img.get_width() + 18, 24)
        fill = C.GOLD if on and gold else (C.ACCENT if on else C.CARD)
        pygame.draw.rect(surface, fill, box, border_radius=12)
        pygame.draw.rect(surface, C.GOLD if on else C.PANEL_EDGE, box, 1, border_radius=12)
        surface.blit(img, (box.x + 9, box.y + 4))
        return box

    def _kpis(self, surface, kpis, x, y, w, h) -> None:
        gap = 8
        per_row = 3 if len(kpis) > 3 else max(1, len(kpis))
        rows = max(1, (len(kpis) + per_row - 1) // per_row)
        ch = max(52, (h - gap * (rows - 1)) // rows)
        cw = max(90, (w - gap * (per_row - 1)) // per_row)
        for i, (label, value, hint) in enumerate(kpis):
            col, row = i % per_row, i // per_row
            bx = x + col * (cw + gap)
            by = y + row * (ch + gap)
            pygame.draw.rect(surface, C.CARD, (bx, by, cw, ch), border_radius=8)
            pygame.draw.rect(surface, C.PANEL_EDGE, (bx, by, cw, ch), 1, border_radius=8)
            ink = C.GOLD if "%" in value else (C.CYAN if value.startswith("$") else C.WHITE)
            text(surface, label, (bx + 10, by + 6), 11, C.MUTED, True)
            text(surface, value, (bx + 10, by + 22), 18, ink, True)
            text(surface, wrap(hint, max(12, cw // 7)), (bx + 10, by + ch - 18), 11, C.MUTED)

    def _insights(self, surface, store, x, y, w, h) -> None:
        pygame.draw.rect(surface, C.CARD, (x, y, w, h), border_radius=8)
        pygame.draw.rect(surface, C.GOLD, (x, y, 4, h), border_radius=2)
        pygame.draw.rect(surface, C.PANEL_EDGE, (x, y, w, h), 1, border_radius=8)
        text(surface, f"KEY TAKEAWAYS  ·  {store.insight_source.title()}", (x + 14, y + 6), 11, C.GOLD, True)
        rows = store.insights or [store.insight or "Load the retail sales data to generate a briefing."]
        limit = max(26, (w - 28) // 8)
        shown = 2 if h < 84 else 3
        for i, line in enumerate(rows[:shown]):
            yy = y + 26 + i * 20
            if yy + 16 > y + h:
                break
            text(surface, wrap(line, limit), (x + 14, yy), 13, C.WHITE)

    def _series(self, store: DataStore) -> Tuple[str, List[float], List[str]]:
        key = store.resolve_metric(store.metric) if store.metric else store._primary_metric()
        return key, store.numeric.get(key, []), store.labels

    def _frame(self, surface, plot, peak, money: bool = False) -> pygame.Rect:
        inner = pygame.Rect(plot.x + 42, plot.y + 8, max(70, plot.w - 54), max(48, plot.h - 36))
        for t in range(5):
            gy = inner.bottom - int(inner.h * t / 4)
            pygame.draw.line(surface, C.GRID, (inner.x, gy), (inner.right, gy), 1)
            text(surface, _fmt(peak * t / 4, money), (plot.x, gy - 8), 11, C.MUTED)
        pygame.draw.line(surface, C.PANEL_EDGE, (inner.x, inner.y), (inner.x, inner.bottom), 1)
        pygame.draw.line(surface, C.PANEL_EDGE, (inner.x, inner.bottom), (inner.right, inner.bottom), 1)
        return inner

    def _bars(self, surface, store, plot) -> None:
        key, series, labels = self._series(store)
        if not series:
            text(surface, "No numeric columns to plot", (plot.x, plot.y + 40), 14, C.ORANGE)
            return
        peak = max(series) or 1.0
        money = is_money(key)
        inner = self._frame(surface, plot, peak, money)
        grow = store.reveal
        n = len(series)
        gap = 10
        bar_w = max(10, int((inner.w - gap * (n + 1)) / n))
        used = n * bar_w + (n + 1) * gap
        left = inner.x + gap + max(0, inner.w - used) // 2
        peak_i = max(range(n), key=lambda i: series[i])
        for i, value in enumerate(series):
            bh = max(0, int((value / peak) * inner.h * grow))
            bx = left + i * (bar_w + gap)
            by = inner.bottom - bh
            color = C.GOLD if i == peak_i else C.ACCENT
            if bh > 0:
                pygame.draw.rect(surface, color, (bx, by, bar_w, bh), border_radius=3)
            if grow > 0.85 and bh > 22:
                text(surface, _fmt(value, money), (bx - 2, max(plot.y, by - 16)), 11, C.WHITE)
            if bar_w >= 14:
                text(surface, str(labels[i])[:3], (bx, min(inner.bottom + 4, plot.bottom - 14)), 12, C.MUTED)

    def _line(self, surface, store, plot, fill: bool) -> None:
        key, series, labels = self._series(store)
        if not series:
            text(surface, "No numeric columns to plot", (plot.x, plot.y + 40), 14, C.ORANGE)
            return
        peak = max(series) or 1.0
        money = is_money(key)
        inner = self._frame(surface, plot, peak, money)
        grow = store.reveal
        n = len(series)
        span = max(1, n - 1)
        shown = max(2, int(math.ceil(n * max(0.08, grow))))
        pts = []
        for i, value in enumerate(series[:shown]):
            px = inner.x + i * inner.w / span
            py = inner.bottom - (value / peak) * inner.h * min(1.0, grow * 1.05)
            pts.append((px, py))
        if fill and len(pts) >= 2:
            poly = [(inner.x, inner.bottom)] + pts + [(pts[-1][0], inner.bottom)]
            overlay = pygame.Surface((inner.w, inner.h), pygame.SRCALPHA)
            local = [(p[0] - inner.x, p[1] - inner.y) for p in poly]
            pygame.draw.polygon(overlay, (*C.ACCENT, 48), local)
            surface.blit(overlay, inner.topleft)
        if len(pts) >= 2:
            pygame.draw.lines(surface, C.ACCENT, False, pts, 3)
        peak_i = max(range(len(pts)), key=lambda i: series[i])
        for i, (px, py) in enumerate(pts):
            pygame.draw.circle(surface, C.GOLD if i == peak_i else C.WHITE, (int(px), int(py)), 4)
        step = 1 if n <= 12 else 2
        for i, label in enumerate(labels):
            if i % step:
                continue
            lx = inner.x + i * inner.w / span - 8
            text(surface, str(label)[:3], (int(lx), inner.bottom + 6), 12, C.MUTED)

    def _hbar(self, surface, store, plot) -> None:
        key, series, labels = self._series(store)
        if not series:
            return
        peak = max(series) or 1.0
        money = is_money(key)
        inner = pygame.Rect(plot.x + 48, plot.y + 8, plot.w - 64, plot.h - 16)
        n = len(series)
        gap = 6
        bh = max(8, int((inner.h - gap * (n + 1)) / n))
        peak_i = max(range(n), key=lambda i: series[i])
        for i, value in enumerate(series):
            bw = int((value / peak) * inner.w * store.reveal)
            by = inner.y + gap + i * (bh + gap)
            pygame.draw.rect(surface, C.GOLD if i == peak_i else C.ACCENT, (inner.x, by, max(1, bw), bh), border_radius=3)
            text(surface, str(labels[i])[:3], (plot.x, by + max(0, bh // 2 - 6)), 12, C.MUTED)
            if store.reveal > 0.8:
                text(surface, _fmt(value, money), (inner.x + bw + 6, by), 11, C.WHITE)

    def _pie(self, surface, store, plot, donut: bool) -> None:
        key, series, labels = self._series(store)
        if not series:
            return
        total = sum(series) or 1.0
        money = is_money(key)
        radius = max(36, min(plot.h // 2 - 12, plot.w // 5, 118))
        cx = plot.x + radius + 24
        cy = plot.y + plot.h // 2
        start = -math.pi / 2
        shown = store.reveal
        for i, value in enumerate(series):
            sweep = (value / total) * math.tau * shown
            if sweep <= 0:
                continue
            self._slice(surface, cx, cy, radius, start, start + sweep, PALETTE[i % len(PALETTE)])
            start += sweep
        if donut:
            hole = int(radius * 0.5)
            pygame.draw.circle(surface, C.SLIDE, (int(cx), int(cy)), hole)
            text(surface, _fmt(total, money), (int(cx) - 22, int(cy) - 12), 15, C.WHITE, True)
            text(surface, ("Revenue" if money else key.title())[:8], (int(cx) - 24, int(cy) + 8), 12, C.MUTED)
        lx, ly = min(int(cx + radius + 24), plot.right - 190), plot.y + 8
        for i, (label, value) in enumerate(zip(labels, series)):
            yy = ly + i * 20
            if yy + 16 > plot.bottom:
                break
            pygame.draw.rect(surface, PALETTE[i % len(PALETTE)], (lx, yy + 4, 10, 10), border_radius=2)
            pct = 100.0 * value / total
            text(surface, f"{label:<4}  {_fmt(value, money):>6}   {pct:4.0f}%", (lx + 16, yy), 12, C.WHITE)

    def _table(self, surface, store, plot) -> None:
        cols = store.headers[:4] or ["-"]
        col_w = plot.w // max(1, len(cols))
        row_h = 26
        pygame.draw.rect(surface, C.CARD, (plot.x, plot.y, plot.w, 28), border_radius=4)
        for i, col in enumerate(cols):
            head = col.title() + (" ($)" if is_money(col) else "")
            text(surface, head, (plot.x + 10 + i * col_w, plot.y + 6), 13, C.MUTED, True)
        shown = store.rows[:12]
        for r, row in enumerate(shown):
            if r / max(1, len(shown)) > store.reveal:
                break
            yy = plot.y + 30 + r * row_h
            if yy + row_h > plot.bottom:
                break
            if r % 2 == 0:
                pygame.draw.rect(surface, (14, 22, 34), (plot.x, yy, plot.w, row_h))
            for c, col in enumerate(cols):
                raw = str(row.get(col, ""))
                try:
                    display = _fmt(float(str(raw).replace(",", "").replace("$", "")), is_money(col))
                except ValueError:
                    display = raw[:14]
                text(surface, display, (plot.x + 10 + c * col_w, yy + 5), 13, C.WHITE)

    def _slice(self, surface, cx, cy, radius, a0, a1, color: Sequence[int]) -> None:
        steps = max(8, int(abs(a1 - a0) * 28))
        pts = [(cx, cy)]
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
        if len(pts) >= 3:
            pygame.draw.polygon(surface, color, pts)

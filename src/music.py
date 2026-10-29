"""Original 5-second jam. Not a copyrighted recording."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
CLIP = ROOT / "data" / ("raja_jam.ogg" if sys.platform == "emscripten" else "raja_jam.wav")
DURATION = 5.0
RATE = 44100


def ensure_clip() -> Path:
    if sys.platform == "emscripten":
        return CLIP
    CLIP.parent.mkdir(exist_ok=True)
    if CLIP.is_file() and CLIP.stat().st_size > 1000:
        return CLIP
    _write_jam(CLIP)
    return CLIP


def _write_jam(path: Path) -> None:
    import wave

    n = int(RATE * DURATION)
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        fade = min(1.0, t / 0.08, (DURATION - t) / 0.25)
        bass = 0.22 * math.sin(2 * math.pi * 110 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 2 * t))
        pad = (
            0.10 * math.sin(2 * math.pi * 220 * t)
            + 0.08 * math.sin(2 * math.pi * 261.63 * t)
            + 0.07 * math.sin(2 * math.pi * 329.63 * t)
            + 0.05 * math.sin(2 * math.pi * 392.00 * t)
        )
        lead_f = 440.0 if int(t * 2) % 4 < 2 else 523.25
        lead = 0.09 * math.sin(2 * math.pi * lead_f * t) * max(0.0, math.sin(2 * math.pi * 4 * t))
        hat = 0.04 * ((i * 13) % 17 / 17 - 0.5) if int(t * 8) % 2 == 0 else 0.0
        sample = max(-1.0, min(1.0, (bass + pad + lead + hat) * fade))
        frames.extend(struct.pack("<h", int(sample * 28000)))
    with wave.open(str(path), "w") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(bytes(frames))


class Jukebox:
    def __init__(self) -> None:
        self.ready = False
        self.error = ""
        self._opened = False

    def _open(self) -> bool:
        if self._opened:
            return self.ready
        self._opened = True
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=1024)
            ensure_clip()
            self.ready = True
        except Exception as exc:
            self.error = exc.__class__.__name__
            self.ready = False
        return self.ready

    def play(self) -> bool:
        if not self._open():
            return False
        try:
            pygame.mixer.music.load(str(ensure_clip()))
            pygame.mixer.music.set_volume(0.85)
            pygame.mixer.music.play(loops=0)
            return True
        except Exception:
            return False

    def stop(self) -> None:
        if not self.ready:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

"""Continuous speech-to-text and reliable Windows text-to-speech."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from collections import deque
from typing import Deque, Optional

from . import config as C

WEB = sys.platform == "emscripten"


class VoiceIO:
    def __init__(self) -> None:
        # queue.Queue breaks under pygame-web / WASM. Use a deque everywhere.
        self._commands: Deque[str] = deque()
        self._speak_q: Deque[str] = deque()
        self.listening = False
        self.available = False
        self.tts_available = False
        self.speaking = False
        self.error = ""
        self.last_error = ""
        self.level = 0.0
        self._recognizer = None
        self._mic = None
        self._sr = None
        self._last_spoken = ""
        self._last_queued = ""
        self.deaf_until = 0.0
        self._speak_until = 0.0
        self._stop = False
        self._listen_thread = None
        self._speak_thread = None

        if WEB:
            self.error = "Type in the Ask box"
            self.available = False
            return

        try:
            import queue
            import threading

            sr = importlib.import_module("speech_recognition")
            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.energy_threshold = C.ENERGY_THRESHOLD
            self._recognizer.pause_threshold = 0.7
            self._mic = sr.Microphone()
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            self.available = True
            self._stop_event = threading.Event()
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._speak_thread = threading.Thread(target=self._speak_loop, daemon=True)
        except Exception as exc:
            self.error = f"Mic unavailable: {exc.__class__.__name__}"
            self.available = False

    def start(self) -> None:
        if WEB:
            return
        if getattr(self, "_stop_event", None) is not None:
            self._stop_event.clear()
        if self._listen_thread is not None and not self._listen_thread.is_alive():
            import threading

            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()
        if self._speak_thread is not None and not self._speak_thread.is_alive():
            import threading

            self._speak_thread = threading.Thread(target=self._speak_loop, daemon=True)
            self._speak_thread.start()

    def shutdown(self) -> None:
        self._stop = True
        if getattr(self, "_stop_event", None) is not None:
            self._stop_event.set()

    def poll(self) -> None:
        if self._speak_until and time.time() >= self._speak_until:
            self.speaking = False
            self._speak_until = 0.0

    def pop_command(self) -> Optional[str]:
        if self._commands:
            return self._commands.popleft()
        return None

    @property
    def busy(self) -> bool:
        return self.speaking or bool(self._speak_q)

    def speak(self, text: str) -> None:
        line = (text or "").strip()
        if not line:
            return
        if line == self._last_queued:
            return
        self._last_queued = line
        if WEB:
            _speak_browser(line)
            self.speaking = True
            self.tts_available = True
            self._last_spoken = line
            self._speak_until = time.time() + min(12.0, max(1.4, 0.06 * len(line)))
            return
        self._speak_q.append(line)

    def push_text(self, text: str) -> None:
        if text.strip():
            self._commands.append(text.strip())

    def _stopped(self) -> bool:
        if getattr(self, "_stop_event", None) is not None:
            return self._stop_event.is_set()
        return self._stop

    def _listen_loop(self) -> None:
        if not self.available or self._recognizer is None or self._mic is None:
            return
        sr = self._sr
        while not self._stopped():
            if self.speaking or time.time() < self.deaf_until:
                time.sleep(0.08)
                continue
            self.listening = True
            try:
                with self._mic as source:
                    audio = self._recognizer.listen(
                        source,
                        timeout=C.LISTEN_TIMEOUT,
                        phrase_time_limit=C.PHRASE_LIMIT,
                    )
                self.level = 1.0
                try:
                    text = self._recognizer.recognize_google(audio)
                except sr.UnknownValueError:
                    text = ""
                except sr.RequestError:
                    try:
                        text = self._recognizer.recognize_sphinx(audio)
                    except Exception:
                        text = ""
                if text:
                    self._commands.append(text)
            except sr.WaitTimeoutError:
                pass
            except Exception:
                time.sleep(0.25)
            finally:
                self.listening = False
                self.level = max(0.0, self.level - 0.4)
                time.sleep(0.05)

    def _speak_loop(self) -> None:
        self._co_init()
        while not self._stopped():
            if not self._speak_q:
                time.sleep(0.05)
                continue
            text = self._speak_q.popleft()
            self.speaking = True
            said = _speak_text(text)
            self.tts_available = said or self.tts_available
            if not said:
                self.last_error = "Speaker failed"
            else:
                self.last_error = ""
                self._last_spoken = text
            self.speaking = False
            self.deaf_until = time.time() + 0.35

    def _co_init(self) -> None:
        try:
            pythoncom = importlib.import_module("pythoncom")
            pythoncom.CoInitialize()
        except Exception:
            pass


def _speak_browser(text: str) -> None:
    try:
        window = importlib.import_module("platform").window
        utter = window.SpeechSynthesisUtterance.new(text)
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(utter)
    except Exception:
        pass


def _speak_text(text: str) -> bool:
    for fn in (_speak_win32, _speak_pyttsx3, _speak_wav, _speak_powershell):
        try:
            if fn(text):
                return True
        except Exception:
            continue
    return False


def _speak_win32(text: str) -> bool:
    pythoncom = importlib.import_module("pythoncom")
    win32 = importlib.import_module("win32com.client")

    pythoncom.CoInitialize()
    try:
        voice = win32.Dispatch("SAPI.SpVoice")
        voice.Speak(str(text))
        return True
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _speak_pyttsx3(text: str) -> bool:
    pyttsx3 = importlib.import_module("pyttsx3")

    try:
        pythoncom = importlib.import_module("pythoncom")
        pythoncom.CoInitialize()
    except Exception:
        pass
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.setProperty("volume", 1.0)
    engine.say(text)
    engine.runAndWait()
    try:
        engine.stop()
    except Exception:
        pass
    return True


def _speak_wav(text: str) -> bool:
    subprocess = importlib.import_module("subprocess")
    winsound = importlib.import_module("winsound")

    path = os.path.join(tempfile.gettempdir(), "raja_tts.wav")
    safe = text.replace("'", "''")
    wav = path.replace("\\", "/")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav}'); "
        f"$s.Speak('{safe}'); "
        "$s.Dispose();"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        timeout=35,
        check=False,
        capture_output=True,
    )
    if not os.path.isfile(path) or os.path.getsize(path) < 80:
        return False
    winsound.PlaySound(path, winsound.SND_FILENAME)
    return True


def _speak_powershell(text: str) -> bool:
    subprocess = importlib.import_module("subprocess")

    safe = text.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}');"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        timeout=35,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0

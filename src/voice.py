"""Continuous speech-to-text and reliable Windows text-to-speech."""

from __future__ import annotations

import os
import queue
import tempfile
import threading
import time
from typing import Optional

from . import config as C


class VoiceIO:
    def __init__(self) -> None:
        self.commands: "queue.Queue[str]" = queue.Queue()
        self.listening = False
        self.available = False
        self.tts_available = False
        self.speaking = False
        self.error = ""
        self.last_error = ""
        self.level = 0.0
        self._stop = threading.Event()
        self._speak_q: "queue.Queue[str]" = queue.Queue()
        self._recognizer = None
        self._mic = None
        self._sr = None
        self._last_spoken = ""
        self._last_queued = ""
        self.deaf_until = 0.0

        try:
            import speech_recognition as sr

            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.energy_threshold = C.ENERGY_THRESHOLD
            self._recognizer.pause_threshold = 0.7
            self._mic = sr.Microphone()
            with self._mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.4)
            self.available = True
        except Exception as exc:
            self.error = f"Mic unavailable: {exc.__class__.__name__}"
            self.available = False

        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._speak_thread = threading.Thread(target=self._speak_loop, daemon=True)

    def start(self) -> None:
        self._stop.clear()
        if not self._listen_thread.is_alive():
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()
        if not self._speak_thread.is_alive():
            self._speak_thread = threading.Thread(target=self._speak_loop, daemon=True)
            self._speak_thread.start()

    def shutdown(self) -> None:
        self._stop.set()

    @property
    def busy(self) -> bool:
        return self.speaking or not self._speak_q.empty()

    def speak(self, text: str) -> None:
        line = (text or "").strip()
        if not line:
            return
        if line == self._last_queued:
            return
        self._last_queued = line
        self._speak_q.put(line)

    def push_text(self, text: str) -> None:
        if text.strip():
            self.commands.put(text.strip())

    def _listen_loop(self) -> None:
        if not self.available or self._recognizer is None or self._mic is None:
            return
        sr = self._sr
        while not self._stop.is_set():
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
                    self.commands.put(text)
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
        while not self._stop.is_set():
            try:
                text = self._speak_q.get(timeout=0.05)
            except queue.Empty:
                continue
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
            import pythoncom

            pythoncom.CoInitialize()
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
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice.Speak(str(text))
        return True
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _speak_pyttsx3(text: str) -> bool:
    import pyttsx3

    try:
        import pythoncom

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
    import subprocess
    import winsound

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
    import subprocess

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

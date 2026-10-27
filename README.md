# Raja — Don't Ask AI. Assign the Task.

Raja is a voice-to-action robot. You speak or type in plain English. An agent picks a Python tool, Raja does the work on screen, and he tells you what he did.

Voice → AI Agent → Python tools → robot action

This repository is the desktop app. The public page is [voice-to-action-robot.vercel.app](https://voice-to-action-robot.vercel.app). The YouTube recording (`Robo Video5 fin.mp4`, 2:16) stays on the machine that recorded it because GitHub rejects files larger than 100 MB.

## Run

```bat
pip install -r requirements.txt
python main.py
```

`run.bat` does the same thing. Press F12 inside the window for the scripted demo, or type in the Ask box.

A microphone is optional. Typed commands use the same path as speech. An API key is optional. Without one, a local matcher still routes tools.

## What he can do

- Talk — hello, thanks, what he can do
- Load `data/retail_sales.csv` and show the table
- Visualize revenue, orders, or customers as a bar, line, pie, area, donut, or table
- Speak the insight: growth, average, peak month
- Walk, run, jump, wave, sit, stand, turn, dance, stop
- Play a five-second original jam written in code

## Optional models

| Key | Used for |
| --- | --- |
| `OPENAI_API_KEY` | Turn one sentence into a list of tool calls |
| `GROQ_API_KEY` | Phrase the spoken insight |
| `GEMINI_API_KEY` | Phrase the spoken insight |
| `OLLAMA_HOST` | Phrase the spoken insight on this machine |

## Layout

- `src/app.py` — window loop, typed and spoken commands
- `src/agent.py` — intent and tool plan
- `src/robot.py` — body, poses, action queue
- `src/voice.py` — microphone and speech
- `src/data_viz.py` — table, charts, KPIs
- `src/insights.py` — local brief, optional model phrasing
- `src/music.py` — original jam
- `src/ui.py` — stage and status panel
- `data/retail_sales.csv` — the 12-month file used in the demo
- `YOUTUBE.md` — long-video title and description
- `site/` — the page deployed on Vercel

## Stack

Python 3 · pygame · SpeechRecognition · PyAudio · pyttsx3 · numpy

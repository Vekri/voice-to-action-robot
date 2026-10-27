# YouTube — long video

Upload `Robo Video5 fin.mp4` (2:16). It stays on this computer. GitHub rejects files over 100 MB, and this recording is about 159 MB.

## Title

Raja | Don't Ask AI. Assign the Task | Voice-to-Action AI Agent

## Description

Don't just talk to AI. Give AI the ability to act.

Raja is a voice-to-action robot. You speak or type in plain English. An agent understands the request, calls a Python tool, and Raja does the work on screen — then tells you what he did out loud.

This recording is the desktop app running live. The robot, the charts, and the voice are the program. Nothing in the picture was added in an editor.

What you will see
0:00 Meet Raja
0:24 Load retail sales and read the table
0:40 Revenue bar chart
0:56 Orders line chart
1:12 Revenue pie chart
1:36 Revenue area chart
1:52 Play a short original jam and dance
2:08 Thank you

The briefing on screen
Revenue grew 142.9% from January ($42) to December ($102).
Orders grew 116.7%, from 180 to 390.
Customers grew 112.5%, from 96 to 204.
Twelve-month total revenue is $837. Average month is $69.8. Peak month is December.

How Raja was created
Raja is a Python desktop app drawn with pygame. It is a simulator you can watch, not a physical robot and not a chatbot that only writes text.

The window is a dark stage plus a live panel: voice, intent, tool, status, and the task list. The body is a jointed figure posed every frame at 60 fps.

A background thread listens on the microphone. Typed text uses the same path. Replies use Windows text-to-speech. While Raja is speaking, the microphone ignores him so he does not answer his own voice.

The agent strips filler such as "please" and "can you", then maps the sentence to tools. If an OpenAI key is set, a small model can return the tool list. If it is not set, a local matcher still routes the sentence. One sentence can become several steps. If nothing matches a tool, Raja answers in conversation.

Each match becomes an action on a queue:
• Talk — greetings, thanks, what he can do
• Load — reads data/retail_sales.csv (12 months of revenue, orders, and customers)
• Visualize — bar, line, pie, area, donut, or table
• Insights — growth, average, peak, and a short spoken brief
• Move — walk, run, jump, wave, sit, stand, turn, dance, stop
• Music — a five-second jam written as tones in code, while the body dances

Charts and KPIs are computed in Python and drawn in the window. Groq, Gemini, or Ollama can phrase an insight when a key is present. This demo does not need them.

Run it
https://github.com/Vekri/voice-to-action-robot

pip install -r requirements.txt
python main.py

Project page
https://voice-to-action-robot.vercel.app

Stack
Python 3 · pygame · SpeechRecognition · PyAudio · pyttsx3 · numpy
Optional: OpenAI, Groq, Gemini, Ollama

Voice → AI Agent → Python tools → robot action

#AIAgent #AgenticAI #VoiceAI #Python #DataVisualization

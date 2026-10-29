# /// script
# dependencies = [
#   "pygame-ce",
# ]
# ///

"""Launch Raja — voice-to-action robot."""

import sys

# Pygbag's browser runtime already has an event loop. Desktop Python does not.
if sys.platform == "emscripten":
    import pygbag.aio as asyncio
else:
    import asyncio

from src.app import App


async def main() -> None:
    await App(demo="--demo" in sys.argv).run()


asyncio.run(main())

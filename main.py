"""Launch Raja — voice-to-action robot."""

import importlib
import sys


def _asyncio():
    # The browser build is already inside an event loop. pygbag's asyncio
    # schedules the game on that loop. Desktop Python uses the normal one.
    if sys.platform == "emscripten":
        return importlib.import_module("pygbag.aio")
    return importlib.import_module("asyncio")


async def main() -> None:
    from src.app import App

    await App(demo="--demo" in sys.argv).run()


_asyncio().run(main())

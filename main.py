"""Launch Raja — voice-to-action robot."""

import asyncio
import sys

from src.app import App


async def main() -> None:
    await App(demo="--demo" in sys.argv).run()


asyncio.run(main())

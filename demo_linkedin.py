"""Auto-run Raja for a LinkedIn screen recording."""

import asyncio

from src.app import App


if __name__ == "__main__":
    asyncio.run(App(demo=True).run())


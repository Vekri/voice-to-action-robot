"""Launch Raja — voice-to-action robot."""

import sys

from src.app import main

if __name__ == "__main__":
    main(demo="--demo" in sys.argv)

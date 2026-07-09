"""Application entry point for the WOODY Monitor Telegram bot."""

import sys

from config import validate_config
from core import multiversx as _monitor


def main() -> None:
    """Validate configuration and start the monitor runtime."""
    validate_config()
    _monitor.main()


if __name__ == "__main__":
    main()
else:
    # Preserve the historical `import main` API while the implementation lives
    # in package modules; monkeypatching tests still affect runtime globals.
    sys.modules[__name__] = _monitor

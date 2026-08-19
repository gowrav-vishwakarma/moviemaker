"""Movie Maker entry point."""

from __future__ import annotations

import argparse

from nicegui import ui

from moviemaker.core.state import STATE
from moviemaker.ui.app_layout import build_layout


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Movie Maker")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--mock", action="store_true", help="Force the mock generation backend")
    args = parser.parse_args()
    if args.mock:
        STATE.settings.use_mock_backend = True
        STATE.reload_backend()

    @ui.page("/")
    def index() -> None:
        build_layout(STATE)

    ui.run(
        title="Movie Maker",
        port=args.port or STATE.settings.ui_port,
        reload=False,
        show=True,
        dark=False,
        favicon="🎬",
    )


if __name__ == "__main__":
    main()

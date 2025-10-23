"""Command line entry point for the demo FastAPI application."""
from __future__ import annotations

import argparse
import uvicorn

from .api import build_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the demo combat simulator API")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="TCP port to listen on")
    args = parser.parse_args()

    uvicorn.run(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()


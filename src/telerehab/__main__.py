"""Command-line entry point: ``python -m telerehab``."""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

from .config import BackendConfig, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telerehab",
        description="Vision-based hand rehabilitation exercises with clinician reporting.",
    )
    parser.add_argument(
        "--api-url", metavar="URL",
        help="backend base URL (default: $TELEREHAB_API_URL or http://localhost:3000)",
    )
    parser.add_argument(
        "--camera", type=int, metavar="N", help="camera index (default: 0)"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="verify the camera and backend are reachable, then exit",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable debug logging"
    )
    return parser


def _check(settings) -> int:
    """Preflight both external dependencies, reporting each separately."""
    from .api import TeleRehabClient

    ok = True

    with TeleRehabClient(settings.backend) as client:
        if client.ping():
            print(f"[ ok ] backend      {settings.backend.base_url}")
        else:
            ok = False
            print(f"[fail] backend      {settings.backend.base_url} unreachable")
            print("       start it with: python mock_server/server.py --seed")

    try:
        from .vision.hand_tracker import HandTracker

        with HandTracker(settings.vision) as tracker:
            sample = tracker.read()
        print(
            f"[ ok ] camera {settings.vision.camera_index}     "
            f"{sample.frame.shape[1]}x{sample.frame.shape[0]}"
            + ("  (hand detected)" if sample.has_hand else "")
        )
    except Exception as exc:
        ok = False
        print(f"[fail] camera {settings.vision.camera_index}     {exc}")

    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    if args.api_url:
        settings = replace(
            settings,
            backend=replace(settings.backend, base_url=args.api_url.rstrip("/")),
        )
    if args.camera is not None:
        settings = replace(
            settings, vision=replace(settings.vision, camera_index=args.camera)
        )

    if args.check:
        return _check(settings)

    from .app import run

    return run(settings)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""CLI entry point for Antigravity transcription and OpenCode meeting analysis."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dotenv import find_dotenv, load_dotenv

from ai_processor import AIProcessingError, OpenCodeProcessor
from audio_extractor import AudioExtractor
from html_generator import write_index, write_report
from transcriber import Transcriber, transcript_text


SUPPORTED_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a", ".webm"}


@dataclass(frozen=True)
class Config:
    opencode_model: str
    opencode_variant: str
    antigravity_model: str
    antigravity_timeout: str
    transcription_language: str
    output_dir: Path
    cache_dir: Path

    @classmethod
    def from_environment(cls) -> "Config":
        required = [
            "OPENCODE_MODEL",
            "OPENCODE_VARIANT",
            "ANTIGRAVITY_MODEL",
            "TRANSCRIPTION_LANGUAGE",
            "OUTPUT_DIR",
            "CACHE_DIR",
        ]
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError(
                "Missing required .env settings: " + ", ".join(missing) + ". "
                "Copy .env.example to .env and configure it."
            )
        return cls(
            opencode_model=os.environ["OPENCODE_MODEL"].strip(),
            opencode_variant=os.environ["OPENCODE_VARIANT"].strip(),
            antigravity_model=os.environ["ANTIGRAVITY_MODEL"].strip(),
            antigravity_timeout=os.getenv("ANTIGRAVITY_TIMEOUT", "15m").strip(),
            transcription_language=os.environ["TRANSCRIPTION_LANGUAGE"].strip(),
            output_dir=Path(os.environ["OUTPUT_DIR"].strip()).expanduser(),
            cache_dir=Path(os.environ["CACHE_DIR"].strip()).expanduser(),
        )


def _load_environment() -> None:
    dotenv = find_dotenv(usecwd=True)
    if dotenv:
        load_dotenv(dotenv)
    else:
        script_env = Path(__file__).resolve().with_name(".env")
        load_dotenv(script_env if script_env.exists() else None)


def _discover(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise ValueError(f"Unsupported input type. Supported extensions: {supported}")
        return [input_path.resolve()]
    if input_path.is_dir():
        return sorted(
            (
                item.resolve()
                for item in input_path.rglob("*")
                if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
            ),
            key=lambda item: str(item).lower(),
        )
    raise FileNotFoundError(f"Input does not exist: {input_path}")


def _output_paths(files: list[Path], source: Path, output_dir: Path) -> dict[Path, Path]:
    paths: dict[Path, Path] = {}
    used: set[Path] = set()
    for media in files:
        candidate = output_dir / f"{media.stem}.html"
        suffix = 2
        while candidate in used:
            candidate = output_dir / f"{media.stem}_{suffix}.html"
            suffix += 1
        used.add(candidate)
        paths[media] = candidate
    return paths


def _progress(prefix: str) -> Callable[[float, str], None]:
    last: tuple[int, str] = (-1, "")

    def report(fraction: float, message: str) -> None:
        nonlocal last
        percent = max(0, min(100, round(fraction * 100)))
        state = (percent, message)
        if state != last:
            print(f"  [{prefix}] {message}: {percent}%", flush=True)
            last = state

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Turn meeting recordings into standalone HTML minutes."
    )
    parser.add_argument("input", type=Path, help="A media file or directory to process")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run transcription and AI analysis, replacing existing reports",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_environment()
    try:
        config = Config.from_environment()
        source = args.input.expanduser().resolve()
        files = _discover(source)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not files:
        print("No supported recordings found.")
        return 0

    output_dir = config.output_dir
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).resolve()
    cache_dir = config.cache_dir
    if not cache_dir.is_absolute():
        cache_dir = (Path.cwd() / cache_dir).resolve()
    destinations = _output_paths(files, source, output_dir)
    progress = _progress("setup")
    transcriber = Transcriber(
        config.antigravity_model,
        config.transcription_language,
        cache_dir,
        progress,
        timeout=config.antigravity_timeout,
    )
    processor = OpenCodeProcessor(
        config.opencode_model,
        config.opencode_variant,
        cache_dir,
        progress,
    )
    extractor = AudioExtractor(cache_dir, progress)

    succeeded = skipped = failed = 0
    print(f"Found {len(files)} recording(s). Output: {output_dir}")
    for index, media in enumerate(files, start=1):
        destination = destinations[media]
        label = f"{index}/{len(files)}"
        print(f"\n[{label}] {media}")
        if destination.exists() and not args.force:
            print(f"  Skipped (report exists): {destination}")
            skipped += 1
            continue
        try:
            progress = _progress(label)
            transcriber.progress = progress
            processor.progress = progress
            extractor.progress = progress
            audio_path = extractor.extract(media, force=args.force)
            transcript = transcriber.transcribe(audio_path, force=args.force)
            transcript = processor.clean_transcript(transcript, force=args.force)
            text = transcript_text(transcript, include_timestamps=True)
            analysis = processor.process(text, force=args.force)
            write_report(
                destination,
                analysis,
                transcript,
                media,
                config.opencode_model,
                config.opencode_variant,
            )
            print(f"  Created: {destination}")
            succeeded += 1
        except (AIProcessingError, RuntimeError, OSError, ValueError) as exc:
            print(f"  Failed: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nDone. Created: {succeeded}, skipped: {skipped}, failed: {failed}.")
    write_index(output_dir)
    print(f"Static site index: {output_dir / 'index.html'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

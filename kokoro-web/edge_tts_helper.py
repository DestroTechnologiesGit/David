#!/usr/bin/env python3
"""Small isolated adapter for downloadable Microsoft Edge speech audio."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import edge_tts


LANGUAGE_ALIASES = {
    "cmn": "zh-cn",
    "zh": "zh-cn",
    "zh-hans": "zh-cn",
    "zh-hant": "zh-tw",
    "no": "nb-no",
}


def normalized_language(language: str) -> str:
    language = language.strip().replace("_", "-").lower()
    return LANGUAGE_ALIASES.get(language, language)


def choose_voice(voices: list[dict[str, Any]], language: str) -> dict[str, Any]:
    requested = normalized_language(language)
    base = requested.split("-", 1)[0]
    exact = [voice for voice in voices if str(voice.get("Locale", "")).lower() == requested]
    matches = exact or [
        voice for voice in voices
        if str(voice.get("Locale", "")).lower().split("-", 1)[0] == base
    ]
    if not matches:
        raise ValueError(f"No downloadable online voice is available for language '{language}'.")
    return sorted(
        matches,
        key=lambda voice: (
            str(voice.get("Gender", "")).lower() != "female",
            str(voice.get("ShortName", "")),
        ),
    )[0]


def language_codes(voices: list[dict[str, Any]]) -> list[str]:
    return sorted({
        str(voice.get("Locale", "")).lower().split("-", 1)[0]
        for voice in voices if voice.get("Locale")
    })


def rate_for_speed(speed: float) -> str:
    percent = round((speed - 1) * 100)
    return f"{percent:+d}%"


async def run(args: argparse.Namespace) -> None:
    voices = await edge_tts.list_voices()
    if args.list_languages:
        print(json.dumps(language_codes(voices)))
        return

    voice = choose_voice(voices, args.language)
    text = Path(args.text_file).read_text(encoding="utf-8")
    communicate = edge_tts.Communicate(
        text,
        voice["ShortName"],
        rate=rate_for_speed(args.speed),
    )
    await communicate.save(args.output)
    print(json.dumps({"voice": voice["ShortName"], "locale": voice["Locale"]}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-languages", action="store_true")
    parser.add_argument("--text-file")
    parser.add_argument("--output")
    parser.add_argument("--language")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    if not args.list_languages and not all((args.text_file, args.output, args.language)):
        parser.error("--text-file, --output, and --language are required for synthesis")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()

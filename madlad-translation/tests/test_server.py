import asyncio
import json

import pytest

import server
from server import Message, TranslationEngine, extract_job, stream_completion


def test_extracts_source_and_target() -> None:
    source, target = extract_job(
        [
            Message(role="system", content="Translate to Urdu (language code: ur)."),
            Message(role="user", content="<SOURCE_TEXT>\nHello world.\n</SOURCE_TEXT>"),
        ]
    )
    assert source == "Hello world."
    assert target == "ur"


def test_extracts_regional_target_code() -> None:
    _, target = extract_job(
        [
            Message(role="system", content="Target language code: zh-Hant."),
            Message(role="user", content="<SOURCE_TEXT>Hello.</SOURCE_TEXT>"),
        ]
    )
    assert target == "zh-hant"


def test_deduplicates_repeated_sentence() -> None:
    text = "Mkutano uliahirishwa. Mkutano uliahirishwa."
    assert TranslationEngine._deduplicate(text) == "Mkutano uliahirishwa."


def test_limits_unrequested_extra_sentence() -> None:
    source = "The installation completed successfully."
    translated = "L'installation s'est terminée avec succès. Installation réussie"
    assert TranslationEngine._limit_sentence_expansion(source, translated) == "L'installation s'est terminée avec succès."


def test_detects_numeric_data_line() -> None:
    assert TranslationEngine._is_data_line("[528.0 113.0 4.0 230.971 350.553]/114")
    assert not TranslationEngine._is_data_line("Version 4 was released today.")


def test_restores_protected_value_without_joining_words() -> None:
    restored = TranslationEngine._restore("Visite  ⟪P0⟫  hoy.", ["https://example.com"])
    assert restored == "Visite https://example.com hoy."
    assert TranslationEngine._restore("Abra ( ⟪P0⟫ ).", ["https://example.com"]) == (
        "Abra (https://example.com)."
    )


class WordTokenizer:
    def encode(self, text: str, out_type: type = str) -> list[str]:
        return text.split()


def test_streams_bounded_translation_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = object.__new__(TranslationEngine)
    engine.tokenizer = WordTokenizer()
    monkeypatch.setattr(engine, "supports", lambda _target: True)
    monkeypatch.setattr(engine, "_translate_piece", lambda text, _target: f"<{text}>")
    monkeypatch.setattr(server, "STREAM_SOURCE_TOKENS", 3)

    pieces = list(engine.translate_stream("- one two three four five\nNext line.", "es"))

    assert pieces == ["- <one two three>", " <four five>", "\n", "<Next line.>"]
    assert engine.translate("- one two three four five\nNext line.", "es") == "".join(pieces)


def test_completion_stream_sends_each_engine_piece(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEngine:
        def translate_stream(self, source: str, target: str):
            assert (source, target) == ("Hello. Goodbye.", "es")
            yield "Hola."
            yield " Adiós."

    monkeypatch.setattr(server, "engine", FakeEngine())

    async def direct_call(function, *args):
        # Keep this unit test independent of the environment's thread-pool
        # policy. Production uses asyncio.to_thread so model work cannot block
        # unrelated HTTP requests.
        return function(*args)

    monkeypatch.setattr(server.asyncio, "to_thread", direct_call)

    async def collect_events() -> list[str]:
        return [event async for event in stream_completion("chatcmpl-test", "Hello. Goodbye.", "es")]

    events = asyncio.run(collect_events())
    payloads = [json.loads(event.removeprefix("data: ")) for event in events[:-1]]

    assert payloads[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert [payload["choices"][0]["delta"].get("content") for payload in payloads[1:3]] == [
        "Hola.", " Adiós."
    ]
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"
    assert events[-1] == "data: [DONE]\n\n"

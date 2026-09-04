from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import ctranslate2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sentencepiece import SentencePieceProcessor


MODEL_ID = "madlad400-3b-mt"
MODEL_PATH = Path(os.environ.get("MADLAD_MODEL_PATH", Path(__file__).parent / "model"))
NO_TRANSLATABLE_TEXT = "NO_TRANSLATABLE_TEXT"
MAX_SOURCE_TOKENS = 420
STREAM_SOURCE_TOKENS = max(32, int(os.environ.get("MADLAD_STREAM_SOURCE_TOKENS", "48")))
BEAM_SIZE = max(1, int(os.environ.get("MADLAD_BEAM_SIZE", "1")))

SOURCE_BLOCK = re.compile(r"<SOURCE_TEXT>\s*(.*?)\s*</SOURCE_TEXT>", re.IGNORECASE | re.DOTALL)
TARGET_CODE = re.compile(r"language\s+code\s*:\s*([a-z]{2,3}(?:[-_][A-Za-z]{2,4})?)", re.IGNORECASE)
PROTECTED = re.compile(
    r"```[\s\S]*?```|`[^`\n]+`|https?://[^\s<>]+|\{\{[^{}]+\}\}|\{[A-Za-z_][A-Za-z0-9_.-]*\}|"
    r"\$\{[^{}]+\}|%\([A-Za-z_][A-Za-z0-9_]*\)[a-zA-Z]|%[sdif]|#[A-Za-z0-9][A-Za-z0-9_-]*"
)
MARKDOWN_PREFIX = re.compile(r"^(\s*(?:#{1,6}\s+|[-+*]\s+|\d+[.)]\s+|>\s+|\[[ xX]\]\s+))")
DATA_TOKEN = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|[/\[\](){},.:;+*=<>_-]+")
LETTER_RUN = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str
    content: Any = ""


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = MODEL_ID
    messages: list[Message] = Field(default_factory=list)
    stream: bool = False


class TranslationEngine:
    def __init__(self, model_path: Path) -> None:
        if not (model_path / "model.bin").is_file():
            raise RuntimeError(f"MADLAD model not found at {model_path}")
        self.tokenizer = SentencePieceProcessor(model_file=str(model_path / "spiece.model"))
        self.translator = ctranslate2.Translator(
            str(model_path),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=max(1, min(16, os.cpu_count() or 1)),
        )

    def supports(self, language_code: str) -> bool:
        token = f"<2{language_code}>"
        return self.tokenizer.piece_to_id(token) != self.tokenizer.unk_id()

    def _translate_piece(self, text: str, target: str) -> str:
        tokens = self.tokenizer.encode(f"<2{target}> {text}", out_type=str)
        result = self.translator.translate_batch(
            [tokens],
            # Greedy decoding is substantially faster on CPU and allows the
            # service to return short segments with low time-to-first-text.
            beam_size=BEAM_SIZE,
            no_repeat_ngram_size=3,
            repetition_penalty=1.2,
            max_decoding_length=min(1024, max(128, len(tokens) * 3 + 32)),
        )[0]
        return self.tokenizer.decode(result.hypotheses[0]).strip()

    def _protect(self, text: str) -> tuple[str, list[str]]:
        values: list[str] = []

        def replace(match: re.Match[str]) -> str:
            values.append(match.group(0))
            return f" ⟪P{len(values) - 1}⟫ "

        return PROTECTED.sub(replace, text), values

    @staticmethod
    def _restore(text: str, values: list[str]) -> str:
        for index, value in enumerate(values):
            marker = re.compile(rf"\s*⟪\s*P\s*{index}\s*⟫\s*", re.IGNORECASE)
            match = marker.search(text)
            if match:
                left = text[match.start() - 1] if match.start() else ""
                right = text[match.end()] if match.end() < len(text) else ""
                before = " " if left and not left.isspace() and left not in "([{“‘" else ""
                after = " " if right and not right.isspace() and right not in ".,;:!?)]}”’" else ""
                text = text[:match.start()] + before + value + after + text[match.end():]
                count = 1
            else:
                count = 0
            if count == 0:
                text = text.rstrip() + (" " if text.strip() else "") + value
        return text

    def _chunks(self, text: str, token_limit: int = MAX_SOURCE_TOKENS) -> list[str]:
        if len(self.tokenizer.encode(text, out_type=str)) <= token_limit:
            return [text]
        sentences = re.split(r"(?<=[.!?。！？])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()
            if current and len(self.tokenizer.encode(candidate, out_type=str)) > token_limit:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)

        # A single sentence can still exceed the limit. Split it at word
        # boundaries so a long paragraph cannot delay the first streamed text
        # or be silently truncated by the model.
        bounded: list[str] = []
        for chunk in chunks:
            if len(self.tokenizer.encode(chunk, out_type=str)) <= token_limit:
                bounded.append(chunk)
                continue
            current_words: list[str] = []
            for word in chunk.split():
                candidate = " ".join((*current_words, word))
                if current_words and len(self.tokenizer.encode(candidate, out_type=str)) > token_limit:
                    bounded.append(" ".join(current_words))
                    current_words = [word]
                else:
                    current_words.append(word)
            if current_words:
                bounded.append(" ".join(current_words))
        return bounded

    @staticmethod
    def _is_data_line(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True
        without_data = DATA_TOKEN.sub(" ", stripped)
        words = LETTER_RUN.findall(without_data)
        return len(words) < 2 and len(DATA_TOKEN.findall(stripped)) >= 4

    @staticmethod
    def _deduplicate(text: str) -> str:
        stripped = text.strip()
        midpoint = len(stripped) // 2
        if len(stripped) > 20:
            left = stripped[:midpoint].rstrip()
            right = stripped[midpoint:].lstrip()
            if left == right:
                return left
        parts = re.split(r"(?<=[.!?。！？])\s+", stripped)
        if len(parts) == 2 and parts[0].strip() == parts[1].strip():
            return parts[0].strip()
        return stripped

    @staticmethod
    def _limit_sentence_expansion(source: str, translated: str) -> str:
        sentence_boundary = r"(?<=[.!?。！？])\s+"
        source_parts = [part for part in re.split(sentence_boundary, source.strip()) if part.strip()]
        translated_parts = [part for part in re.split(sentence_boundary, translated.strip()) if part.strip()]
        if source_parts and len(translated_parts) > len(source_parts):
            return " ".join(translated_parts[: len(source_parts)]).strip()
        return translated.strip()

    @staticmethod
    def _normalized_target(target: str) -> str:
        normalized = target.replace("-", "_")
        return "zh_Hant" if normalized.lower() == "zh_hant" else normalized.split("_")[0].lower()

    def validate(self, target: str) -> str:
        target = self._normalized_target(target)
        if not self.supports(target):
            raise ValueError(f"Language code '{target}' is not supported by this translation model.")
        return target

    def translate_stream(self, source: str, target: str) -> Iterator[str]:
        target = self.validate(target)
        if not LETTER_RUN.search(PROTECTED.sub(" ", source)):
            yield NO_TRANSLATABLE_TEXT
            return

        for line in source.splitlines(keepends=True):
            newline = "\n" if line.endswith("\n") else ""
            body = line[:-1] if newline else line
            if not body.strip() or self._is_data_line(body) or body.lstrip().startswith("```"):
                yield body + newline
                continue

            prefix_match = MARKDOWN_PREFIX.match(body)
            prefix = prefix_match.group(1) if prefix_match else ""
            natural = body[len(prefix) :]
            chunks = self._chunks(natural, STREAM_SOURCE_TOKENS)
            for index, chunk in enumerate(chunks):
                protected, values = self._protect(chunk)
                translated = self._translate_piece(protected, target)
                translated = self._limit_sentence_expansion(protected, translated)
                translated = self._deduplicate(translated)
                separator = prefix if index == 0 else " "
                yield separator + self._restore(translated, values)
            if newline:
                yield newline

    def translate(self, source: str, target: str) -> str:
        return "".join(self.translate_stream(source, target)).strip()


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def extract_job(messages: list[Message]) -> tuple[str, str]:
    texts = [_content_text(message.content) for message in messages]
    source = ""
    for text in reversed(texts):
        match = SOURCE_BLOCK.search(text)
        if match:
            source = match.group(1)
            break
    if not source:
        raise ValueError("The translation request is missing a SOURCE_TEXT block.")

    target = ""
    for text in texts:
        match = TARGET_CODE.search(text)
        if match:
            target = match.group(1).lower()
            break
    if not target:
        raise ValueError("The translation request is missing a target language code.")
    return source, target


engine: TranslationEngine | None = None
translation_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global engine
    engine = await asyncio.to_thread(TranslationEngine, MODEL_PATH)
    yield
    engine = None


app = FastAPI(title="LiveContent MADLAD Translation", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok" if engine else "loading", "model": MODEL_ID}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}]}


def completion_payload(request_id: str, text: str) -> dict[str, Any]:
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def translate_request(request: ChatRequest) -> str:
    if engine is None:
        raise HTTPException(status_code=503, detail="Translation model is still loading.")
    try:
        source, target = extract_job(request.messages)
        async with translation_lock:
            return await asyncio.to_thread(engine.translate, source, target)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _next_piece(iterator: Iterator[str]) -> tuple[bool, str]:
    try:
        return True, next(iterator)
    except StopIteration:
        return False, ""


def stream_payload(request_id: str, content: str | None = None, *, first: bool = False,
                   finished: bool = False) -> str:
    base = {"id": request_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL_ID}
    delta: dict[str, str] = {"role": "assistant"} if first else {}
    if content is not None:
        delta["content"] = content
    payload = dict(base, choices=[{
        "index": 0,
        "delta": delta,
        "finish_reason": "stop" if finished else None,
    }])
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_completion(request_id: str, source: str, target: str) -> AsyncIterator[str]:
    # Send headers and the first SSE event before waiting for another request
    # or doing any model work. This makes the connection visibly live at once.
    yield stream_payload(request_id, first=True)
    assert engine is not None
    async with translation_lock:
        iterator = iter(engine.translate_stream(source, target))
        while True:
            has_piece, piece = await asyncio.to_thread(_next_piece, iterator)
            if not has_piece:
                break
            if piece:
                yield stream_payload(request_id, piece)
    yield stream_payload(request_id, finished=True)
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> Any:
    request_id = f"chatcmpl-{uuid.uuid4().hex}"
    if request.stream:
        if engine is None:
            raise HTTPException(status_code=503, detail="Translation model is still loading.")
        try:
            source, target = extract_job(request.messages)
            engine.validate(target)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return StreamingResponse(
            stream_completion(request_id, source, target),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    text = await translate_request(request)
    return completion_payload(request_id, text)

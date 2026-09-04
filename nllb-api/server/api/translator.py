from typing import Annotated, get_args

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sse_starlette.sse import EventSourceResponse

from server.guards import requires_secret
from server.schemas.v1 import Tokens, Translated, Translation, TranslationBatch, TranslationBatchItem, TranslatedBatch
from server.typedefs import Language, get_app_state

router = APIRouter()


@router.delete("/translator", dependencies=[Depends(requires_secret)], status_code=status.HTTP_204_NO_CONTENT)
def unload_model(
    request: Request,
    to_cpu: Annotated[bool, Query(description="whether to unload the model to CPU")] = False,
    state=Depends(get_app_state),
) -> Response:
    """
    Summary
    -------
    unload the model from the current device
    """
    if state.translator.unload_model(to_cpu=to_cpu):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(status_code=status.HTTP_304_NOT_MODIFIED)


@router.put("/translator", dependencies=[Depends(requires_secret)], status_code=status.HTTP_204_NO_CONTENT)
def load_model(
    request: Request,
    keep_cache: Annotated[bool, Query(description="whether to keep the model cache in RAM")] = False,
    state=Depends(get_app_state),
) -> Response:
    """
    Summary
    -------
    load the model back to the initial device
    """
    if state.translator.load_model(keep_cache=keep_cache):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(status_code=status.HTTP_304_NOT_MODIFIED)


@router.get("/translator/tokens", tags=["API"], response_model=Tokens)
def token_count(
    text: Annotated[str, Query(min_length=1, description="source text of a single language")],
    state=Depends(get_app_state),
) -> Tokens:
    """
    Summary
    -------
    count the number of tokens in the input text
    """
    return Tokens(length=state.translator.count_tokens(text))


@router.get("/translator", tags=["API"], response_model=Translated)
def translator_get(
    text: Annotated[
        str,
        Query(
            min_length=1,
            max_length=2000,  # Limit GET requests to avoid URL truncation by proxies/load balancers
            description="source text of a single language (use POST /translator for longer texts)",
            examples=["Hello, world!", "¡Hola, mundo!"],
        ),
    ],
    source: Annotated[
        Language,
        Query(
            description="source language in the FLORES-200 code format",
            examples=[code for code in get_args(Language.__value__)],
        ),
    ] = "eng_Latn",
    target: Annotated[
        Language,
        Query(
            description="target language in the FLORES-200 code format",
            examples=[code for code in get_args(Language.__value__)],
        ),
    ] = "spa_Latn",
    min_length_percentage: Annotated[
        float,
        Query(
            ge=0.0,
            le=1.0,
            description="Minimum decoding length as percentage of input tokens (0.0-1.0). Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models. See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6",
            examples=[0.8],
        ),
    ] = 0.8,
    state=Depends(get_app_state),
) -> Translated:
    """
    Summary
    -------
    the GET variant of the `/translator` route
    
    Note: For texts longer than ~2000 characters, use POST /translator instead
    to avoid URL length limits that may cause truncation.
    
    Parameters
    ----------
    min_length_percentage (float)
        Minimum decoding length as percentage of input tokens (0.0-1.0).
        Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
        See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6
    """
    return Translated(result=state.translator.translate(text, source, target, min_length_percentage))


@router.post("/translator/batch", tags=["API"], response_model=TranslatedBatch, status_code=status.HTTP_200_OK)
def translator_batch(
    data: TranslationBatch,
    request: Request,
    state=Depends(get_app_state),
) -> TranslatedBatch:
    """
    Summary
    -------
    translate multiple texts in batch for improved GPU utilization

    Parameters
    ----------
    data (TranslationBatch)
        batch translation request containing list of translation items.
        Each item can optionally specify min_length_percentage to control minimum decoding length.

    Returns
    -------
    TranslatedBatch
        batch translation response containing list of translated texts in the same order as input
    
    Note
    ----
    Each item can specify its own min_length_percentage value. The minimum decoding length
    is computed per item based on that item's input token count and percentage value.
    """
    from opentelemetry import metrics, trace
    
    batch_size = len(data.translations)
    
    # Add batch size as span attribute for monitoring
    span = trace.get_current_span()
    if span:
        span.set_attribute("batch.size", batch_size)
        span.set_attribute("http.request.batch_size", batch_size)
    
    # Record batch size as a histogram metric for monitoring
    meter = metrics.get_meter(__name__)
    batch_size_histogram = meter.create_histogram(
        name="nllb_api_batch_size",
        description="Batch size distribution for translation requests",
        unit="1",
    )
    batch_size_histogram.record(
        batch_size,
        attributes={
            "endpoint": "/translator/batch",
            "batch_size_bucket": f"{batch_size}",
        },
    )
    
    texts = [item.text for item in data.translations]
    source_languages = [item.source for item in data.translations]
    target_languages = [item.target for item in data.translations]
    # Extract min_length_percentage for each item (each defaults to 0.8)
    min_length_percentages = [item.min_length_percentage for item in data.translations]

    translated_texts = state.translator.translate_batch(texts, source_languages, target_languages, min_length_percentages)

    return TranslatedBatch(
        results=[{"result": text} for text in translated_texts],
    )


@router.post("/translator", tags=["API"], response_model=Translated, status_code=status.HTTP_200_OK)
def translator_post(
    data: TranslationBatchItem,
    state=Depends(get_app_state),
) -> Translated:
    """
    Summary
    -------
    translate a single text using POST (recommended for long texts to avoid URL length limits)
    
    This endpoint uses the same schema as batch translation items for consistency.
    Use this instead of GET /translator for texts longer than ~2000 characters.

    Parameters
    ----------
    data (TranslationBatchItem)
        translation request containing text, source, target language, and optional min_length_percentage

    Returns
    -------
    Translated
        translated text result
    """
    return Translated(result=state.translator.translate(data.text, data.source, data.target, data.min_length_percentage))


@router.get("/translator/stream", tags=["API"])
def translator_stream(
    request: Request,
    text: Annotated[
        str,
        Query(
            min_length=1,
            description="source text of a single language",
            examples=["Hello, world!", "¡Hola, mundo!"],
        ),
    ],
    source: Annotated[
        Language,
        Query(
            description="source language in the FLORES-200 code format",
            examples=[code for code in get_args(Language.__value__)],
        ),
    ] = "eng_Latn",
    target: Annotated[
        Language,
        Query(
            description="target language in the FLORES-200 code format",
            examples=[code for code in get_args(Language.__value__)],
        ),
    ] = "spa_Latn",
    min_length_percentage: Annotated[
        float,
        Query(
            ge=0.0,
            le=1.0,
            description="Minimum decoding length as percentage of input tokens (0.0-1.0). Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models. See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6",
            examples=[0.8],
        ),
    ] = 0.8,
    event_type: Annotated[str | None, Query(description="the event that an event listener will listen for")] = None,
    state=Depends(get_app_state),
) -> EventSourceResponse:
    """
    Summary
    -------
    the `/translator/stream` returns a Server-Sent Event stream of the translation
    
    Parameters
    ----------
    min_length_percentage (float)
        Minimum decoding length as percentage of input tokens (0.0-1.0).
        Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
        See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6
    """
    async def generate():
        for chunk in state.translator.translate_stream(text, source, target, min_length_percentage):
            yield {"event": event_type, "data": chunk} if event_type else {"data": chunk}

    return EventSourceResponse(generate())


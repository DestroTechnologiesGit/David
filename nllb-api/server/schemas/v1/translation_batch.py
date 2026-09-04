from typing import Annotated

from pydantic import BaseModel, Field

from server.typedefs import Language


class TranslationBatchItem(BaseModel):
    """
    Summary
    -------
    a single translation item in a batch request

    Attributes
    ----------
    text (str)
        source text of a single language

    source (Language)
        source language in the FLORES-200 code format

    target (Language)
        target language in the FLORES-200 code format

    min_length_percentage (float)
        minimum decoding length as percentage of input tokens (0.0-1.0).
        Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models.
        See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6
    """

    text: Annotated[
        str,
        Field(min_length=1, max_length=4096, description="source text of a single language", examples=["Hello, world!"]),
    ]

    source: Annotated[
        Language,
        Field(description="source language in the FLORES-200 code format", examples=["eng_Latn"]),
    ]

    target: Annotated[
        Language,
        Field(description="target language in the FLORES-200 code format", examples=["spa_Latn"]),
    ]

    min_length_percentage: Annotated[
        float,
        Field(
            default=0.8,
            ge=0.0,
            le=1.0,
            description="Minimum decoding length as percentage of input tokens (0.0-1.0). Defaults to 0.8 (80%). Used to prevent early stopping in NLLB models. See: https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6",
            examples=[0.8],
        ),
    ] = 0.8


class TranslationBatch(BaseModel):
    """
    Summary
    -------
    the NLLB batch translation schema

    Attributes
    ----------
    translations (list[TranslationBatchItem])
        list of translation requests to process in batch
    """

    translations: Annotated[
        list[TranslationBatchItem],
        Field(
            min_length=1,
            max_length=1000,
            description="list of translation requests to process in batch",
            examples=[
                [
                    {"text": "Hello, world!", "source": "eng_Latn", "target": "spa_Latn"},
                    {"text": "Bonjour le monde!", "source": "fra_Latn", "target": "eng_Latn"},
                ]
            ],
        ),
    ]


class TranslatedBatchItem(BaseModel):
    """
    Summary
    -------
    a single translated result in a batch response

    Attributes
    ----------
    result (str)
        the translated text
    """

    result: Annotated[
        str,
        Field(
            description="translated text in the language specified within the `target` request field",
            examples=["¡Hola, mundo!"],
        ),
    ]


class TranslatedBatch(BaseModel):
    """
    Summary
    -------
    the batch translated schema

    Attributes
    ----------
    results (list[TranslatedBatchItem])
        list of translated texts in the same order as the input requests
    """

    results: Annotated[
        list[TranslatedBatchItem],
        Field(
            description="list of translated texts in the same order as the input requests",
            examples=[{"result": "¡Hola, mundo!"}, {"result": "Hello, world!"}],
        ),
    ]


from typing import Annotated

from pydantic import BaseModel, Field

from server.typedefs import Confidence, Language


class LanguageResult(BaseModel):
    """
    Summary
    -------
    the NLLB language schema

    Attributes
    ----------
    language (Languages)
        the detected language

    confidence (Score)
        the confidence score of the detected language
    """

    language: Annotated[
        Language,
        Field(description="language code in the FLORES-200 format", examples=["eng_Latn"]),
    ]
    confidence: Annotated[
        Confidence,
        Field(description="confidence score of the detected language"),
    ]

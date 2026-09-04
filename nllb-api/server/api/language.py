from typing import Annotated

from fastapi import APIRouter, Depends, Query

from server.schemas.v1 import LanguageResult
from server.typedefs import get_app_state

router = APIRouter()


@router.get("/language", tags=["API"], response_model=LanguageResult)
def language(
    text: Annotated[
        str,
        Query(
            description="sample text for language detection",
            max_length=512,
            min_length=1,
            examples=[
                "She sells seashells!",
                "Ella vende conchas!",
            ],
        ),
    ],
    fast_model_confidence_threshold: Annotated[
        float,
        Query(
            description="minimum acceptable confidence before using the accurate model results",
            ge=0.0,
            le=1.1,
            examples=[0.85, 1.1, 0.0],
        ),
    ] = 0.85,
    accurate_model_confidence_threshold: Annotated[
        float,
        Query(
            description="minimum acceptable confidence before falling back to the faster model results",
            ge=0.0,
            le=1.0,
            examples=[0.35, 0.0],
        ),
    ] = 0.35,
    state=Depends(get_app_state),
) -> LanguageResult:
    """
    Summary
    -------
    the `/language` route detects the language of the input text
    """
    prediction = state.language_detector.detect(
        text,
        fasttext_confidence_threshold=fast_model_confidence_threshold,
        lingua_confidence_threshold=accurate_model_confidence_threshold,
    )
    return LanguageResult(language=prediction.language, confidence=prediction.confidence)


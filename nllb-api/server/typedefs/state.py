from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from server.features.detector import LanguageDetectorProtocol
    from server.features.translator import TranslatorProtocol


class AppState:
    """
    Summary
    -------
    the FastAPI application state that will be injected into the routers

    Attributes
    ----------
    language_detector (LanguageDetectorProtocol)
        the language detector

    translator (TranslatorProtocol)
        the translator
    """

    language_detector: "LanguageDetectorProtocol"
    translator: "TranslatorProtocol"

    def __init__(self, request: Request):
        self.language_detector = request.app.state.language_detector
        self.translator = request.app.state.translator


def get_app_state(request: Request) -> AppState:
    """
    Summary
    -------
    get the application state from the request

    Parameters
    ----------
    request (Request)
        the FastAPI request

    Returns
    -------
    state (AppState)
        the application state
    """
    return AppState(request)

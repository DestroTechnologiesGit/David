from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from server.features.translator import get_translator


@asynccontextmanager
async def translator_lifespan(
    app: FastAPI,
    *,
    translator_repository: str,
    translator_threads: int,
    stub: bool,
    testing: bool,
    use_cuda: bool,
) -> AsyncIterator[None]:
    """
    Summary
    -------
    lifespan to load the translator model

    Parameters
    ----------
    app (FastAPI)
        the application instance

    translator_repository (str)
        the repository to download the model from

    translator_threads (int)
        the number of threads to use for translation

    stub (bool)
        whether to use a stub object

    testing (bool)
        whether the application is running in testing mode

    use_cuda (bool)
        whether to use CUDA for translation
    """
    with get_translator(
        translator_repository,
        translator_threads=translator_threads,
        testing=testing,
        stub=stub,
        use_cuda=use_cuda,
    ) as translator:
        app.state.translator = translator
        yield


def load_translator_model(
    translator_repository: str,
    *,
    translator_threads: int,
    stub: bool,
    testing: bool,
    use_cuda: bool,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """
    Summary
    -------
    the translator lifespan factory

    Parameters
    ----------
    translator_repository (str)
        the repository to download the model from

    translator_threads (int)
        the number of threads to use for translation

    stub (bool)
        whether to use a stub object

    testing (bool)
        whether the application is running in testing mode

    use_cuda (bool)
        whether to use CUDA for translation

    Returns
    -------
    lifespan (Callable[[FastAPI], AbstractAsyncContextManager[None]])
        a FastAPI-compatible lifespan context manager
    """
    return lambda app: translator_lifespan(
        app,
        translator_repository=translator_repository,
        translator_threads=translator_threads,
        stub=stub,
        testing=testing,
        use_cuda=use_cuda,
    )

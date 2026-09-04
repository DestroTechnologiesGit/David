from typing import Annotated

from pydantic import BaseModel, Field


class Translated(BaseModel):
    """
    Summary
    -------
    the translated schema

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

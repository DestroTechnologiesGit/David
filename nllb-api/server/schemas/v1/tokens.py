from typing import Annotated

from pydantic import BaseModel, Field


class Tokens(BaseModel):
    """
    Summary
    -------
    the Tokens schema

    Attributes
    ----------
    length (int)
        the number of tokens in the input text
    """

    length: Annotated[
        int,
        Field(description="the number of tokens in the input text", examples=[512]),
    ]

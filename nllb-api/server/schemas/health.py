from pydantic import BaseModel, ConfigDict, Field


class Health(BaseModel):
    """
    Summary
    -------
    the [shields.io](https://shields.io/badges/endpoint-badge) endpoint badge response schema

    Attributes
    ----------
    schema_version (int)
        the schema version, always `1`

    label (str)
        the label to display on the left side of the badge, defaults to the application name

    message (str)
        the message to display on the right side of the badge, defaults to `online`
    """

    model_config = ConfigDict(populate_by_name=True)

    schema_version: int = Field(default=1, alias="schemaVersion")
    label: str = Field(default="nllb-api")
    message: str = Field(default="online")

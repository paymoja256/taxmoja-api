from pydantic import BaseModel


class ClientAuthenticationBase(BaseModel):
    tax_country_code: str
    tax_id: str
    x_api_key_header: str


class CoreModel(BaseModel):
    """
    Any common logic to be shared by all models goes here.
    """
    pass


class IDModelMixin(BaseModel):
    id: int

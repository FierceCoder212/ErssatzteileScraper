from pydantic import BaseModel

from Models.SectionModel import SectionModel


class CatalogModel(BaseModel):
    sgl_code: str
    sections: list[SectionModel]

from pydantic import BaseModel

from Models.PartModel import PartModel


class SectionModel(BaseModel):
    section_name: str
    section_image: str
    parts: list[PartModel]

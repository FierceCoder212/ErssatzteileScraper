from pydantic import BaseModel


class PartModel(BaseModel):
    part_number: str
    item_number: str
    description: str

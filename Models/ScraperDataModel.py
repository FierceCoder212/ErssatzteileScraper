from pydantic import BaseModel


class ScraperDataModel(BaseModel):
    sgl_code: str
    catalog_link: str

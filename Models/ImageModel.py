from pydantic import BaseModel


class ImageModel(BaseModel):
    file_name: str
    image_url: str

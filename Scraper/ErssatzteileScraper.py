import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from Helpers.MSSqlHelper import MSSqlHelper
from Models.ApiRequestModel import ApiRequestModel
from Models.CatalogModel import CatalogModel
from Models.ImageModel import ImageModel
from Models.PartModel import PartModel
from Models.ScraperDataModel import ScraperDataModel
from Models.SectionModel import SectionModel


class ErssatzteileScraper:
    def __init__(self, data_file_path: str):
        self.scraper_data = self.get_scraper_data(file_path=data_file_path)
        self.max_workers = 10
        self.page_size = math.ceil(len(self.scraper_data) / 10)
        self.scraper_name = 'Erssatzteile'
        self.sqlHelper = MSSqlHelper()
        self.images = []
        self.current_count = 0

    def scrape_data(self):
        with ThreadPoolExecutor(max_workers=self.max_workers) as threads:
            futures = [threads.submit(self.scrape_urls, i) for i in range(self.max_workers)]
        [future.result() for future in as_completed(futures)]
        print('Saving images')
        self._save_json(self.images, 'images.json')

    def scrape_urls(self, index):
        start_index = index * self.page_size
        end_index = (index + 1) * self.page_size
        curr_data = self.scraper_data[start_index:end_index]
        for index, data in enumerate(curr_data):
            print(f'Thread-{index + 1} : {index} of {len(curr_data)}')
            self.current_count += 1
            catalog = self.scrape_url(scraper_data=data)
            records = self._create_records(catalog=catalog)
            print(f'Sending records to SQL: {len(records)}')
            self.sqlHelper.insert_many_records(records=records)

    def scrape_url(self, scraper_data: ScraperDataModel) -> CatalogModel:
        # print(f'Scraping Section')
        response = requests.get(scraper_data.catalog_link)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            parts_links_container = soup.select('div.widget-content a')
            parts_links = [urljoin(scraper_data.catalog_link, container.get('href')) for container in
                           parts_links_container]
            all_section_data = []
            # print(f'Found parts {len(parts_links)}')
            for section_link in parts_links:
                if section_data := self.scrape_parts(section_link):
                    all_section_data.append(section_data)
            # print(f'Got sections : {len(all_section_data)}')
            all_section_data = self.translate_sections_name(sections=all_section_data)
            return CatalogModel(sgl_code=scraper_data.sgl_code, sections=all_section_data)
        else:
            print(f'Error at base url : {scraper_data.catalog_link}, Status Code : {response.status_code}')

    def scrape_parts(self, url: str) -> SectionModel:
        # print(f'Scraping parts')
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            parts_rows = soup.select('tr.Artikelvorschau')
            section_image = ''
            if img := soup.select_one('img.thumbnail'):
                section_image = urljoin(url, img.get('src'))
            section_name = soup.select_one('li.active').text
            parts = []
            for row in parts_rows:
                part_number = row.select_one('td[data-label="Pos."]').text
                item_number = row.select_one('td[data-label=Artikelnummer]').text
                description = row.select_one('td[data-label=Bezeichnung]').text
                parts.append(PartModel(part_number=part_number, item_number=item_number, description=description))
            # print(f'Got parts : {len(parts)}')
            if parts:
                parts = self.translate_parts_description(parts=parts)
            return SectionModel(section_name=section_name, section_image=section_image, parts=parts)
        else:
            print(f'Error at link : {url}, Status Code : {response.status_code}')

    def translate_parts_description(self, parts: list[PartModel]) -> list[PartModel]:
        # print(f'Translating parts : {len(parts)}')
        descriptions = [part.description for part in parts]
        translated_descriptions = self.translate_data(data=descriptions)
        for index, translated_description in enumerate(translated_descriptions):
            parts[index].description = translated_description
        return parts

    def translate_sections_name(self, sections: list[SectionModel]) -> list[SectionModel]:
        names = [section.section_name for section in sections]
        translated_names = self.translate_data(data=names)
        for index, translated_name in enumerate(translated_names):
            sections[index].section_name = translated_name
        return sections

    @staticmethod
    def translate_data(data: list[str]):
        url = "https://translate-pa.googleapis.com/v1/translateHtml"
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "content-type": "application/json+protobuf",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not)A;Brand\";v=\"99\", \"Google Chrome\";v=\"127\", \"Chromium\";v=\"127\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "x-client-data": "CIu2yQEIprbJAQipncoBCKeXywEIk6HLAQia/swBCOmYzQEIhaDNAQ==",
            "x-goog-api-key": "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520",
            "Referer": "https://www.ersatzteil24.de/",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
        body = [[data, "de", "en"], "te_lib"]
        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 200:
            try:
                return json.loads(response.text)[0]
            except Exception as ex:
                print(f'Error at google translate : {ex}\n{response.text}')
        else:
            print(f'Error at translation, Status code : {response.status_code}')
        return data

    @staticmethod
    def get_scraper_data(file_path: str) -> list[ScraperDataModel]:
        with open(file_path, 'r') as scraper_data_file:
            scraper_data = json.load(scraper_data_file)
        return [ScraperDataModel(**data) for data in scraper_data]

    def _create_records(self, catalog: CatalogModel) -> list[dict]:
        records = []
        for section in catalog.sections:
            image_filename = self._sanitize_filename(f'{catalog.sgl_code}-{section.section_name}.jpg')
            self.images.append(ImageModel(
                file_name=image_filename,
                image_url=section.section_image,
            ).model_dump())
            for part in section.parts:
                records.append(ApiRequestModel(
                    id=0,
                    sglUniqueModelCode=catalog.sgl_code,
                    section=section.section_name,
                    partNumber=part.part_number,
                    description=part.description,
                    itemNumber=part.item_number,
                    sectonDiagram=image_filename,
                    scraperName=self.scraper_name).model_dump())
        return records

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Convert invalid filenames to valid filenames by replacing or removing invalid characters.
        """
        invalid_chars = r'[<>:"/\\|?*\']'
        sanitized_filename = re.sub(invalid_chars, "_", filename)
        sanitized_filename = sanitized_filename.strip()
        sanitized_filename = sanitized_filename[:255]
        return sanitized_filename

    @staticmethod
    def _save_json(json_data, file_name="json_data.json"):
        with open(file_name, "w") as json_file:
            json_file.write(json.dumps(json_data, indent=4))

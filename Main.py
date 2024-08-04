from Scraper.ErssatzteileScraper import ErssatzteileScraper

scraper = ErssatzteileScraper('ScraperData.json', 'SGL.json')
scraper.scrape_data()
# import json
#
# with open(r"C:\Users\ABDULLAH\Documents\SGL.csv", 'r') as csv_file:
#     csv_data = csv_file.read().split('\n')
# with open(r"SGL.json", 'w') as csv_file:
#     csv_file.write(json.dumps(csv_data, indent=4))

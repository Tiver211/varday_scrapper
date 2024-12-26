import datetime
import os
import re
import requests
import sqlite3
from PyPDF2 import PdfReader
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Scrapper:
    def __init__(self,
                 url: str = "https://liceum1.vsevobr.ru/temp/varday.pdf",
                 headers: dict = None,
                 cookies: dict = None,
                 db: str = "data.db"
                 ) -> None:
        self.url = url
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.session = requests.Session()
        self.conn = sqlite3.connect(db)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS Changes(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, date TEXT NOT NULL, changes TEXT NOT NULL, group_for TEXT NOT NULL)""")
        self.conn.commit()
        if not os.path.exists("pdf_files"):
            os.makedirs("pdf_files")
        logger.info("Scrapper initialized")

    def get_varday(self, group, actual: bool = False) -> tuple[str, datetime.date] | bool | None:
        logger.info(f"Retrieving variable day schedule for group: {group}")
        response = self.session.get(self.url, cookies=self.cookies, headers=self.headers, stream=True)
        if response.status_code != 200:
            logger.error(f"Failed to download PDF. Status code: {response.status_code}")
            return False
    
        temp_pdf_path = os.path.join("pdf_files", "temp.pdf")
        with open(temp_pdf_path, "wb") as pdf_file:
            for chunk in response.iter_content(chunk_size=8192):
                pdf_file.write(chunk)
        logger.info(f"PDF downloaded and saved to {temp_pdf_path}")
    
        reader = PdfReader(temp_pdf_path)
    
        parsed_text = []
        for page in reader.pages:
            parsed_text.append(page.extract_text())
    
        text = "".join(parsed_text)
        date = self.get_date_from_text(text)
    
        if not date:
            logger.warning("No date found in the PDF")
            return False
    
        path = os.path.join("pdf_files", f"{date}.pdf")
        os.rename(temp_pdf_path, path)
        logger.info(f"PDF renamed to {path}")
    
        changes = self.get_changes_for_group(text, group)
        if not changes:
            logger.info(f"No changes found for group {group}")
            return None
    
        self.cursor.execute('''SELECT * FROM Changes WHERE group_for=? AND date=? LIMIT 1''',
                            (group, date.strftime("%d-%m-%Y")))
        alr_changes = self.cursor.fetchone()
        if alr_changes and alr_changes[2] == changes and actual:
            logger.info(f"Changes for group {group} are up-to-date")
            return True
    
        if (alr_changes and alr_changes[2] != changes and not actual) or not alr_changes:
            self.cursor.execute('''INSERT OR REPLACE INTO Changes(date, changes, group_for) VALUES (?, ?, ?)''',
                                (date.strftime("%d-%m-%Y"), str(changes), group))
            self.conn.commit()
            logger.info(f"Changes for group {group} updated in the database")
    
        return changes, date

    @staticmethod
    def get_changes_for_group(text, group):
        logger.info(f"Searching for changes for group {group}")
        pattern = rf"({group})\s*–\s*([^\n]+)"
        matches = re.findall(pattern, text)

        if matches:
            logger.info(f"Changes found for group {group}")
            return matches[0][1]
        else:
            logger.info(f"No changes found for group {group}")
            return None

    @staticmethod
    def get_date_from_text(text, year = None):
        logger.info("Extracting date from text")
        if year is None:
            year = datetime.date.today().year

        first_line = text.splitlines()[0]

        match = re.search(r'\b(\d{1,2})\.(\d{1,2})\b', first_line)
        if match:
            day, month = map(int, match.groups())
            date = datetime.date(year, month, day)
            logger.info(f"Date extracted: {date}")
            return date

        logger.warning("No date found in the text")
        return None

    def __del__(self):
        logger.info("Closing database connection")
        self.conn.close()

scrapper = Scrapper("https://liceum1.vsevobr.ru/temp/varday.pdf")
print(scrapper.get_varday(group='8в'))
import datetime
import os
import re
import requests
import sqlite3
from PyPDF2 import PdfReader
import logging
import shutil

from asyncpg.pgproto.pgproto import timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Scrapper:
    def __init__(self,
                 url: str = "https://liceum1.vsevobr.ru/temp/varday.pdf",
                 headers: dict = None,
                 cookies: dict = None,
                 db: str = "data.db",
                 ) -> None:
        self.url = url
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.session = requests.Session()
        self.conn = sqlite3.connect(db, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS Changes(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, date TEXT NOT NULL, changes TEXT NOT NULL, group_for TEXT NOT NULL)""")
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS Subs(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, subgroup TEXT NOT NULL, last_update TEXT NOT NULL)""")
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS Users(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL)""")
        self.conn.commit()
        if not os.path.exists("pdf_files"):
            os.makedirs("pdf_files")
        logger.debug("Scrapper initialized")

    def update_varday(self, group) -> tuple[str, datetime.date] | bool | None:
        logger.debug(f"Retrieving variable day schedule for group: {group}")
        response = self.session.get(self.url, cookies=self.cookies, headers=self.headers, stream=True)
        if response.status_code != 200:
            logger.error(f"Failed to download PDF. Status code: {response.status_code}")
            return False
    
        temp_pdf_path = os.path.join("pdf_files", "temp.pdf")
        content = response.iter_content(chunk_size=8192)
        with open(temp_pdf_path, "wb") as pdf_file:
            for chunk in content:
                pdf_file.write(chunk)
        logger.debug(f"PDF downloaded and saved to {temp_pdf_path}")
    
        reader = PdfReader(temp_pdf_path)
    
        parsed_text = []
        for page in reader.pages:
            parsed_text.append(page.extract_text())

        text = "".join(parsed_text)
        date = self.__get_date_from_text(text)
    
        if not date:
            logger.warning("No date found in the PDF")
            return False
    
        path = os.path.join("pdf_files", f"{date}.pdf")

        shutil.move(temp_pdf_path, path)
        logger.debug(f"PDF renamed to {path}")
    
        changes = self.__get_changes_for_group(text, group)
        if not changes:
            logger.debug(f"No changes found for group {group}")
            return None
    
        self.cursor.execute('''SELECT * FROM Changes WHERE group_for=? AND date=? LIMIT 1''',
                            (group, date.strftime("%d-%m-%Y")))
        alr_changes = self.cursor.fetchone()
        if alr_changes and alr_changes[2] == changes:
            logger.debug(f"Changes for group {group} are up-to-date")
            return True
    
        if alr_changes and alr_changes[2] != changes or not alr_changes:
            self.cursor.execute('''INSERT OR REPLACE INTO Changes(date, changes, group_for) VALUES (?, ?, ?)''',
                                (date.strftime("%d-%m-%Y"), str(changes), group))
            self.conn.commit()
            logger.debug(f"Changes for group {group} updated in the database")
    
        return changes, date

    def get_varday(self,
                   group,
                   date: datetime.date = datetime.date.today()+timedelta(days=1)
                   ) -> tuple[str, datetime.date] | None:
        self.cursor.execute('''SELECT * FROM Changes WHERE group_for=? AND date=? LIMIT 1''',
                            (group, date.strftime("%d-%m-%Y")))
        data = self.cursor.fetchone()
        if data:
            return data[2], data[1]

        else:
            return None

    def get_last_varday(self, group) -> tuple[str, datetime.date] | bool | None:
        logger.debug(f"Retrieving last variable day schedule for group: {group}")
        query = """
           SELECT date, changes, group_for
           FROM Changes
           WHERE group_for = ?
           ORDER BY date DESC
           LIMIT 1;
           """
        try:
            # Подключение к базе данных

            self.cursor.execute(query, (group,))

            result = self.cursor.fetchone()
            if result:
                return (result[1], datetime.datetime.strptime(result[0], "%d-%m-%Y").date())
            else:
                return False
        except Exception as e:
            return False

    @staticmethod
    def __get_changes_for_group(text, group):
        logger.debug(f"Searching for changes for group {group}")
        pattern = rf"({group})\s*–\s*([^\n]+)"
        matches = re.findall(pattern, text)

        if matches:
            logger.debug(f"Changes found for group {group}")
            return matches[0][1]
        else:
            logger.debug(f"No changes found for group {group}")
            return None

    @staticmethod
    def __get_date_from_text(text, year = None):
        logger.debug("Extracting date from text")
        if year is None:
            year = datetime.date.today().year

        first_line = text.splitlines()[0]

        match = re.search(r'(\d{1,2})\.(\d{1,2})', first_line)
        if match:
            day, month = map(int, match.groups())
            date = datetime.date(year, month, day)
            logger.debug(f"Date extracted: {date}")
            return date

        logger.warning("No date found in the text")
        return None

    def __del__(self):
        logger.debug("Closing database connection")
        self.conn.close()

if __name__ == '__main__':
    scrapper = Scrapper()
    print(scrapper.update_varday("8в"))
    print(scrapper.get_varday("8в", datetime.date(2022, 1, 1)))
    print(scrapper.get_last_varday("8в"))
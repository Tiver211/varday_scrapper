import datetime
import json
import logging
import os


class Settings:
    def __init__(self):
        with open("settings.json", encoding='utf-8') as file:
            settings = json.load(file)

        # Устанавливаем каждую настройку как атрибут экземпляра
        for key, value in settings.items():
            setattr(self, key, value)

        # Сохраняем настройки для доступа через __getitem__
        self._settings = settings

    def __getitem__(self, key):
        # Предоставляем доступ к настройкам через ключ
        return getattr(self, key, None)

settings = Settings()

if not os.path.exists("logs"):
    os.makedirs("logs")


logger = logging.getLogger(__name__)
logger.setLevel(settings["log_level"])
logger.addHandler(logging.FileHandler(os.path.join("logs", f"{datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.log"), encoding='UTF-8'))
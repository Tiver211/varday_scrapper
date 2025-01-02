import json
import logging

from telebot import TeleBot
from time import sleep
from tg_bot import *
from scrapper import Scrapper
from tg_bot import Subscribe, bot
from settings import settings

GROUPS = settings["groups"]

# Функция отправки сообщений, вызываемая скраппером
class TgHandler:
    def __init__(self, bot: TeleBot, db, scrapper: Scrapper):
        self.bot = bot
        self.db = db
        self.scrapper = scrapper

    def start_cycle(self, period: int):
        while True:
            self.run_cycle()
            sleep(period)

    def run_cycle(self):
        for group in GROUPS:
            self.scrapper.update_varday(group)
            changes = self.scrapper.get_last_varday(group)
            subscribers = get_subscribers(group)
            for subscriber in subscribers:
                if changes[1] > subscriber.last_update:
                    self.send_message(subscriber, changes[0], changes[1])

    def send_message(self, subsctiption: Subscribe, message, date):
        answer = f'Появилсь изменения для класса {subsctiption.subgroup} на {date}: {message}'
        try:
            update_subscription(subsctiption, message, date)
            self.bot.send_message(subsctiption.user_id, answer)

        except Exception as e:
            self.bot.send_message(subsctiption.user_id, f'Ошибка при отправке сообщения: {e}')

    def admin_message(self, message, recipients):
        for recipient in recipients:
            self.bot.send_message(recipient, message)

if __name__ == "__main__":
    tg_handler = TgHandler(bot, db, scrapper)
    tg_handler.start_cycle(settings.cycle_period)
import threading
from typing import List
import telebot
from scrapper import Scrapper
import logging
import sqlite3
import datetime
import json
from telebot_dialogue import Dialogue, DialogueManager
from settings import settings, logger

db = settings["db"]
dialogue_manager = DialogueManager()

logger.setLevel(logging.INFO)

GROUPS = settings["groups"]

scrapper = Scrapper()

conn = sqlite3.connect(db, check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """CREATE TABLE IF NOT EXISTS Changes(
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 
    date TEXT NOT NULL, 
    changes TEXT NOT NULL, 
    group_for TEXT NOT NULL)""")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS Subs(
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 
    user_id INTEGER NOT NULL, 
    subgroup TEXT NOT NULL, 
    last_update TEXT NOT NULL, 
    last_change TEXT NOT NULL)""")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS Users(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL)""")

conn.commit()


TOKEN = settings["token"]


# Создаём экземпляр бота
bot = telebot.TeleBot(TOKEN)


class Subscribe:
    def __init__(self, user_id: int, subgroup: str, last_update: datetime.date, last_change: str):
        self.user_id = user_id
        self.subgroup = subgroup
        self.last_update = last_update
        self.last_change = last_change

    def __str__(self) -> str:
        return self.subgroup

    def __int__(self) -> int:
        return self.user_id

    def get_gruop_num(self) -> int:
        return int(self.subgroup[0])

    def get_gruop_char(self) -> str:
        return self.subgroup[1]

def extract_arg(arg: str) -> List[str]:
    logger.info(f"Extracting arguments from '{arg}'")
    return arg.split()[1:]

def get_subscriptions(user_id: int) -> [Subscribe]:
    logger.debug(f"Getting subscriptions for user {user_id}")
    cursor.execute("""SELECT subgroup, last_update, last_change FROM Subs WHERE user_id=?""",
                   (user_id,))
    res = []
    for sub in cursor.fetchall():
        res.append(Subscribe(user_id, sub[0], datetime.datetime.strptime(sub[1], "%d-%m-%Y").date(), sub[2]))

    return res


def find_subscription(user_id, group):
    logger.info(f"Finding subscription for user {user_id} and group {group}")
    subscriptions = get_subscriptions(user_id)
    for sub in subscriptions:
        if sub.subgroup == group:
            return sub

    return None


def add_subscription(user_id: int, subgroup: str) -> None:
    logger.info(f"Adding subscription for user {user_id} and group {subgroup}")
    cursor.execute("""INSERT INTO Subs(user_id, subgroup, last_update, last_change) VALUES(?,?,?,?)""",
                   (user_id, subgroup, datetime.date.today().strftime("%d-%m-%Y"), scrapper.get_varday(subgroup, datetime.date.today())[0] if scrapper.get_varday(subgroup, datetime.date.today()) else "None",))
    conn.commit()

def check_subscription(subscription: Subscribe) -> bool:
    logger.info(f"Checking subscription for user {subscription.user_id} and group {subscription.subgroup}")
    cursor.execute("""SELECT * FROM Subs WHERE user_id=? AND subgroup=?""",
                   (subscription.user_id, subscription.subgroup))
    return bool(cursor.fetchone())

def delete_subscription(subscription: Subscribe) -> None:
    logger.info(f"Deleting subscription for user {subscription.user_id} and group {subscription.subgroup}")
    cursor.execute("""DELETE FROM Subs WHERE user_id=? AND subgroup=?""",
                   (subscription.user_id, subscription.subgroup))
    conn.commit()

def get_subscribers(group: str) -> List[Subscribe]:
    logger.debug(f"Getting subscriptions for group {group}")
    cursor.execute("""SELECT * FROM Subs WHERE subgroup=?""",
                   (group,))
    res = []
    for sub in cursor.fetchall():
        res.append(Subscribe(int(sub[1]), sub[2], datetime.datetime.strptime(sub[3], "%d-%m-%Y").date(), sub[4]))

    return res

def update_subscription(subscription: Subscribe, new_changes, new_date: datetime.date) -> bool:
    logger.info(f"Updating subscription for user {subscription.user_id} and group {subscription.subgroup}")
    cursor.execute("""UPDATE Subs SET last_change=?, last_update=? WHERE user_id=? AND subgroup=?""",
                   (new_changes, new_date.strftime("%d-%m-%Y"), subscription.user_id, subscription.subgroup))
    conn.commit()
    return bool(cursor.rowcount)

# Команда /start
@bot.message_handler(commands=["start"])
def start_command(message):
    logger.info(f"User {message.from_user.id} started the bot")
    cursor.execute("""SELECT * FROM Users WHERE user_id=?""",
                   (message.from_user.id,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, '''Привет! 👋  
    Я ваш помощник для отслеживания изменений в расписании.  
    
    ✨ Что я умею:  
    - 📄 Подписка на уведомления для вашего класса.  
    - 🔍 Поиск изменений за дату или последние.  
    - 📋 Просмотр изменений для всех классов.  
    - 📂 Скачивание PDF с обновлениями.  
    
    Воспользуйтесь меню, чтобы выбрать нужную опцию, и не мониторьте изменения вручную! 🚀
    Бот может иногда падать потому-что разраб рукожоп, пишите в лс, подниму https://t.me/Tiver211.
    Исходный код: https://github.com/Tiver211/varday_scrapper
    Данные относятся только к МОУ "Лицей №1" г.Всеволожска. 
    Разработан как личный проект и не связан с администрацией школы.''')
        cursor.execute("""INSERT INTO Users(user_id) VALUES(?)""",
                       (message.from_user.id,))
        conn.commit()

    menu(message=message)


@bot.message_handler(commands=["menu"])
def menu(message):
    logger.info(f"User {message.from_user.id} opened the menu")
    keyboard = telebot.types.InlineKeyboardMarkup()
    button_subscribes_control = telebot.types.InlineKeyboardButton(
        text="🔔 управлять подписками",
        callback_data="subscribe_controll")
    get_info_button = telebot.types.InlineKeyboardButton(
        text="🔍 получить изменения",
        callback_data="get_info_control")

    keyboard.row(button_subscribes_control)
    keyboard.row(get_info_button)
    bot.send_message(message.chat.id, "Меню:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == "subscribe_controll")
def subscribes_control(call):
    logger.info(f"User {call.from_user.id} opened the subscribes control")
    dialogue_manager.finish_dialogue(call.message.chat.id)
    keyboard = telebot.types.InlineKeyboardMarkup()
    button_subscribe = telebot.types.InlineKeyboardButton(
        text="➕ подписаться на уведомления",
        callback_data="subscribe_menu")
    button_unsubscribe = telebot.types.InlineKeyboardButton(
        text="➖ отписаться от уведомлений",
        callback_data="unsubscribe_menu")
    button_cancel = telebot.types.InlineKeyboardButton(
        text="⬅️ назад",
        callback_data="cancel_main")
    keyboard.add(button_subscribe, button_unsubscribe)
    keyboard.row(button_cancel)

    subs = get_subscriptions(call.message.chat.id)
    answer_groups = ""
    for subscription in subs:
        answer_groups += f" {subscription.subgroup}     последнее обновление - {subscription.last_update.strftime("%d.%m.%Y")}\n"
    ans_message = f"активные подписки: \n{answer_groups}"
    bot.send_message(call.message.chat.id, ans_message, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == "unsubscribe_menu")
def unsubscribe_menu(call):
    logger.info(f"User {call.from_user.id} opened the unsubscribe menu")
    keyboard = telebot.types.InlineKeyboardMarkup()
    groups = get_subscriptions(call.message.chat.id)
    for group in groups:
        keyboard.add(telebot.types.InlineKeyboardButton(str(group), callback_data=str(group)+"_unsubscribe"))
    keyboard.add(telebot.types.InlineKeyboardButton("назад", callback_data="cancel"+"_unsubscribe"))

    bot.send_message(
        call.message.chat.id,
        "Выберите класс для отписки:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: "_unsubscribe" in call.data)
def unsubscribe_group(call):
    logger.info(f"User {call.from_user.id} unsubscribed from group {call.data.split('_')[0]}")
    group = call.data.split("_")[0]
    if group == "cancel":
        subscribes_control(call)
        return

    sub = find_subscription(call.message.chat.id, group)
    if sub:
        delete_subscription(sub)
        bot.send_message(call.message.chat.id, f"Вы успешно отписались от уведомлений для класса {group}")
        subscribes_control(call)
        return


    bot.send_message(call.message.chat.id, f"Вы не подписаны на уведомления для этого класса")
    subscribes_control(call)


@bot.callback_query_handler(func=lambda call: call.data == "subscribe_menu")
def subscribe_menu(call):
    logger.info(f"User {call.from_user.id} opened the subscribe menu")
    dialogue = Dialogue(call.message.chat.id, handler=subscribe_group)
    dialogue_manager.add_dialogue(dialogue)
    bot.send_message(call.message.chat.id, "Напищите класс для подписки (например 8в):")


def subscribe_group(message, dialogue: Dialogue):
    logger.info(f"User {message.from_user.id} subscribed to group {message.text}")
    sub = find_subscription(message.from_user.id, message.text)
    if sub:
        bot.send_message(message.chat.id, f"Вы уже подписаны на уведомления для класса {message.text}")
        return

    if message.text not in GROUPS:
        bot.send_message(message.chat.id, "Такого класса нет в списке")
        return

    add_subscription(message.from_user.id, message.text)
    bot.send_message(message.chat.id, f"Вы успешно подписаны на уведомления для класса {message.text}")
    menu(message)
    dialogue_manager.finish_dialogue(message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "get_info_control")
def get_info_control(call):
    logger.info(f"User {call.from_user.id} opened the get info control")
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("📁 Получить измения в виде pdf", callback_data="get_pdf"))
    keyboard.add(telebot.types.InlineKeyboardButton("🗓️ Получить изменения за дату", callback_data="get_changes_by_date"))
    keyboard.add(telebot.types.InlineKeyboardButton("🕛 Получить последние изменения", callback_data="get_last_changes"))
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="cancel_main"))

    bot.send_message(call.message.chat.id, "Какие изменения вы хотите получить?", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "get_pdf")
def get_pdf_menu(call):
    logger.info(f"User {call.message.chat.id} opened get pdf menu")
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("🕛 Получить последний файл", callback_data="download_pdf_last"))
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="cancel_info"))

    bot.send_message(call.message.chat.id, "Введите дату в формате гггг.мм.дд, или получите последний файл", reply_markup=keyboard)
    dialogue = Dialogue(call.message.chat.id, handler=send_pdf_by_date)
    dialogue_manager.add_dialogue(dialogue)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_info")
def cancel_info(call):
    logger.info(f"User {call.from_user.id} canceled info control")
    dialogue_manager.finish_dialogue(call.message.chat.id)
    get_info_control(call)

@bot.callback_query_handler(func=lambda call: call.data == "download_pdf_last")
def download_pdf_last(call):
    logger.info(f"User {call.from_user.id} downloaded last pdf")
    files = [f for f in os.listdir("pdf_files") if f.endswith('.pdf') and f != 'temp.pdf']
    date_files = {}
    dialogue_manager.finish_dialogue(call.message.chat.id)
    for file in files:
        try:
            date = datetime.datetime.strptime(file.replace('.pdf', ''), '%Y-%m-%d')
            date_files[file] = date
        except ValueError:
            continue

    if not date_files:
        return None

    latest_file = max(date_files, key=date_files.get)
    try:
        with open(os.path.join("pdf_files", latest_file), 'rb') as pdf_file:
            bot.send_document(call.message.chat.id, document=pdf_file)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"Ошибка при отправке файла: {e}")

def send_pdf_by_date(message, dialogue: Dialogue):
    logger.info(f"User {message.from_user.id} downloaded pdf by date {message.text}")
    try:
        date = datetime.datetime.strptime(message.text, "%Y.%m.%d").strftime("%Y-%m-%d")

    except ValueError:
        bot.send_message(dialogue.user_id, "Неверный формат даты, пожалуста введите дату в формате гггг.мм.дд")
        return
    path = os.path.join("pdf_files", date+".pdf")
    if not os.path.exists(path):
        bot.send_message(dialogue.user_id, "Файла на эту дату не существует, пожалуста выберите другую")
        return

    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="cancel_info"))
    try:
        with open(path, 'rb') as pdf_file:
            bot.send_document(dialogue.user_id, document=pdf_file, reply_markup=keyboard)

    except Exception as e:
        bot.send_message(dialogue.user_id, f"Ошибка при отправке файла: {e}", reply_markup=keyboard)


    dialogue_manager.finish_dialogue(dialogue.user_id)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_main")
def cancel_main(call):
    logger.info(f"User {call.from_user.id} canceled main menu")
    dialogue_manager.finish_dialogue(call.message.chat.id)
    menu(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "get_last_changes")
def get_latest_change(call):
    logger.info(f"User {call.from_user.id} opened get last changes menu")
    dialogue = Dialogue(call.message.chat.id, handler=get_last_change_by_group)
    dialogue_manager.add_dialogue(dialogue)
    bot.send_message(call.message.chat.id, "В каком классе вы хотите получить последние изменения?")

def get_last_change_by_group(message, dialogue: Dialogue):
    logger.info(f"User {message.from_user.id} downloaded last changes by group {message.text}")
    group = message.text
    if group not in GROUPS:
        bot.send_message(dialogue.user_id, "Такого класса нет в списке")
        return

    result = scrapper.get_last_varday(group)

    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="cancel_info"))

    if result:
        date, change = result
        bot.send_message(message.chat.id, f"Последнее изменение в классе {message.text}:\n{date} - {change}",
                         reply_markup=keyboard)
    else:
        bot.send_message(dialogue.user_id, "В данном классе нет изменений", reply_markup=keyboard)

    dialogue_manager.finish_dialogue(dialogue.user_id)

@bot.callback_query_handler(func=lambda call: call.data == "get_changes_by_date")
def get_changes_by_date_menu(call):
    logger.info(f"User {call.from_user.id} opened get changes by date menu")
    dialogue = Dialogue(call.message.chat.id, handler=get_date_for_changes)
    dialogue_manager.add_dialogue(dialogue)
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("🗓️ завтра", callback_data="changes_tomorrow"))
    keyboard.add(telebot.types.InlineKeyboardButton("🗓️ сегодня", callback_data="changes_today"))
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️️ Назад", callback_data="cancel_info"))
    bot.send_message(call.message.chat.id,
                     "За какую дату вы хотите получить изменения? "
                     "ответ дайте в формате гггг.мм.дд, или выберите вариант из меню",
                     reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "changes_today")
def changes_today(call):
    logger.info(f"User {call.from_user.id} requested changes today")
    if not dialogue_manager.find_dialogue(call.message.chat.id):
        dialogue = Dialogue(call.message.chat.id, handler=get_group_for_chages)
        dialogue.update_context("date", datetime.date.today())
        dialogue_manager.add_dialogue(dialogue)

    else:
        with dialogue_manager.update(call.message.chat.id) as dialogue:
            dialogue.handler = get_group_for_chages
            dialogue.update_context("date", datetime.date.today())

    bot.send_message(call.message.chat.id, "Теперь введите класс:")


@bot.callback_query_handler(func=lambda call: call.data == "changes_tomorrow")
def changes_tomorrow(call):
    logger.info(f"User {call.from_user.id} requested changes tomorrow")
    if not dialogue_manager.find_dialogue(call.message.chat.id):
        dialogue = Dialogue(call.message.chat.id, handler=get_group_for_chages)
        dialogue.update_context("date", datetime.date.today()+timedelta(days=1))
        dialogue_manager.add_dialogue(dialogue)

    else:
        with dialogue_manager.update(call.message.chat.id) as dialogue:
            dialogue.handler = get_group_for_chages
            dialogue.update_context("date", datetime.date.today()+timedelta(days=1))
    bot.send_message(call.message.chat.id, "Теперь введите класс:")


def get_date_for_changes(message: telebot.types.Message, dialogue: Dialogue):
    logger.info(f"User {message.from_user.id} downloaded changes by date {message.text}")
    try:
        date = datetime.datetime.strptime(message.text, "%Y.%m.%d").date()

    except ValueError:
        bot.send_message(dialogue.user_id, "Неверный формат даты. Пожалуйста, введите дату в формате гггг.мм.дд")
        return

    with dialogue_manager.update(dialogue.user_id) as dialogue:
        dialogue.handler = get_group_for_chages
        dialogue.update_context("date", date)
        dialogue.update_context("group", None)
    bot.send_message(message.chat.id, "Теперь введите класс:")

def get_group_for_chages(message, dialogue: Dialogue):
    logger.info(f"User {message.from_user.id} downloaded changes by group {message.text}")
    group = message.text
    if group not in GROUPS:
        bot.send_message(dialogue.user_id, "Такого класса нет в списке")
        return

    with dialogue_manager.update(dialogue.user_id) as dialogue:
        dialogue.update_context("group", group)

    get_changes_by_date_group(dialogue_manager.find_dialogue(dialogue.user_id))


def get_changes_by_date_group(dialogue):
    group = dialogue.get_context("group")
    date = dialogue.get_context("date")
    logger.info(f"User {dialogue.user_id} requested changes by date {date} and group {group}")
    changes = scrapper.get_varday(group, date)
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("⬅️️ Назад", callback_data="cancel_info"))
    if changes:
        change, date = changes
        bot.send_message(dialogue.user_id, f"Изменения за {date} класса {group}: \n{change}", reply_markup=keyboard)

    else:
        bot.send_message(dialogue.user_id, "В данном классе за эту дату нет изменений", reply_markup=keyboard)

    dialogue_manager.finish_dialogue(dialogue.user_id)

@bot.message_handler(content_types=["text"], func=lambda message: not message.text.startswith("/"))
def multihandler(message):
    logger.info(f"User {message.from_user.id} sent message: {message.text}")
    dialogue_manager.handle_message(message)

if __name__ == "__main__":
    from tg_handler import *

    # Запускаем скраппер в отдельном потоке
    tg_handler = TgHandler(bot=bot, scrapper=scrapper, db=db)
    scraper_thread = threading.Thread(target=tg_handler.start_cycle, daemon=True, args=(10,))
    scraper_thread.start()
    logger.info("bot started")
    bot.infinity_polling()
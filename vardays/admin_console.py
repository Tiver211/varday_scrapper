import datetime
import functools
import os
from telebot_dialogue import Dialogue, DialogueManager
from tg_bot import bot, cursor, dialogue_manager
import sqlite3
from scrapper import Scrapper
from settings import settings, logger
from telebot import types


def is_admin(admins):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Предполагается, что Message или Call передаются как первый аргумент
            obj = args[0]

            # Проверяем, является ли объект Message или Call и извлекаем ID
            if hasattr(obj, 'from_user') and hasattr(obj.from_user, 'id'):
                user_id = obj.from_user.id
            elif hasattr(obj, 'message') and hasattr(obj.message, 'chat') and hasattr(obj.message.chat, 'id'):
                user_id = obj.message.chat.id
            else:
                raise ValueError("Неизвестный объект или структура данных.")

            # Проверяем, есть ли ID в списке администраторов
            if user_id in admins:
                logger.info(f"Доступ разрешён для ID: {user_id}")
                return func(*args, **kwargs)
            else:
                logger.info(f"Доступ запрещён для ID: {user_id}")
                return None  # Или другой механизм обработки

        return wrapper

    return decorator

@bot.message_handler(commands=['check_admin'])
@is_admin(settings.admins)
def check_admin(message):
    logger.info(f"User {message.from_user.id} check admin status")
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name}! ���")


@bot.message_handler(commands=['admin_console'])
@is_admin(settings.admins)
def admin_menu(message):
    print('test')
    logger.info(f"User {message.from_user.id} open admin console")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text='Логи', callback_data='logs'),
        types.InlineKeyboardButton(text='БД', callback_data='db_control'),
        types.InlineKeyboardButton(text='Уведомления', callback_data='notifications_control'),
    )
    bot.send_message(message.chat.id, 'Консоль администратора:', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data == 'logs')
@is_admin(settings.admins)
def logs_control(call):
    files = [f for f in os.listdir("logs") if f.endswith('.log')]
    date_files = {}
    dialogue_manager.finish_dialogue(call.message.chat.id)
    for file in files:
        try:
            date = datetime.datetime.strptime(file.replace('.log', ''), '%Y-%m-%d %H-%M-%S')
            date_files[file] = date
        except ValueError:
            continue

    if not date_files:
        return None

    latest_file = max(date_files, key=date_files.get)
    with open(os.path.join("logs", latest_file), encoding='UTF-8') as log_file:
        bot.send_document(call.message.chat.id, log_file)

@bot.callback_query_handler(func=lambda call: call.data == 'db_control')
def db_control(call):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='Выйти', callback_data='cancel_admin'))
    bot.send_message(call.message.chat.id, "Введите запрос в базу данных", reply_markup=keyboard)
    dialogue = Dialogue(call.message.chat.id, handler=execute_query)
    dialogue_manager.add_dialogue(dialogue)


def execute_query(message, dialogue):
    connection = None
    try:
        # Устанавливаем соединение с базой данных
        connection = sqlite3.connect(settings.db)
        cursor = connection.cursor()
        query = message.text

        # Выполняем запрос и получаем результаты
        cursor.execute(query)

        # Определяем, есть ли результат (например, SELECT)
        if query.strip().lower().startswith("select"):
            ans = ''
            result = cursor.fetchall()
            for res in result:
                ans += "\n"
                for row in res:
                    ans += "|"  + str(row)

            bot.send_message(dialogue.user_id, ans)
        else:
            # Для запросов, изменяющих данные (INSERT, UPDATE, DELETE)
            connection.commit()
        cursor.execute(query)

    except sqlite3.Error as e:
        connection.rollback()
        bot.send_message(dialogue.user_id, f"Ошибка при выполнении запроса: {e}")
        return
    finally:
        if connection:
            connection.close()

    bot.send_message(message.chat.id, "Запрос выполнен успешно")

@bot.callback_query_handler(func=lambda call: call.data == 'notifications_control')
def notifications_control(call):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='назад', callback_data='cancel_admin'))
    dialogue = Dialogue(call.message.chat.id, handler=send_notification)
    dialogue_manager.add_dialogue(dialogue)
    bot.send_message(call.message.chat.id, "отправить уведомление", reply_markup=keyboard)

def send_notification(message, dialogue):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    for user in users:
        print(user)
        bot.send_message(user[0], message.text)

    dialogue.finish_dialogue(dialogue.user_id)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_admin')
def cancel_admin(call: types.CallbackQuery):
    dialogue_manager.finish_dialogue(call.message.chat.id)
    call.message.from_user.id = call.message.chat.id
    admin_menu(call.message)

if __name__ == '__main__':
    bot.polling()
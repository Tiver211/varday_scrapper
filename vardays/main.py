from tg_bot import *
from scrapper import *


if __name__ == '__main__':
    from tg_handler import *

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

    # Запускаем скраппер в отдельном потоке
    tg_handler = TgHandler(bot=bot, scrapper=scrapper, db=db)
    scraper_thread = threading.Thread(target=tg_handler.start_cycle, daemon=True, args=(10,))
    scraper_thread.start()
    logger.info("Бот запущен!")
    bot.infinity_polling()

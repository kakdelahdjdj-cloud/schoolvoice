"""
Точка входа для хостинга (Bothost по умолчанию запускает bot.py).

Токен и ID администраторов на сервере задаются не в файле .env,
а в панели хостинга в разделе «Environment Variables»:
    BOT_TOKEN = токен от @BotFather
    ADMIN_IDS = ваш Telegram ID
"""

import asyncio

from main import main

if __name__ == "__main__":
    asyncio.run(main())

import os
import asyncio
import aiohttp
import signal
import sys
import platform
from datetime import datetime, timezone
from dotenv import load_dotenv
from googleapiclient.discovery import build
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from io import BytesIO
from telegram_config import TelegramConfig  # Импорт из локального файла telegram_config.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode

# Загрузить переменные окружения
load_dotenv()


class YouTubeTelegramBot:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.bot = Bot(token=self.bot_token)
        self.admin_users = [int(uid) for uid in str(os.getenv('ADMIN_USERS', '')).split(',') if uid]
        self.config = TelegramConfig()
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '300'))
        self.running = False
        self.last_check = {}
        self.shutdown_event = asyncio.Event()
        self.channel_cache = {}

    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        return user_id in self.admin_users

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /start_notify"""
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать этого бота.\n"
                "Свяжитесь с владельцем бота для получения доступа.",
                parse_mode=ParseMode.HTML
            )
            return

        await update.message.reply_text(
            f"👋 Добро пожаловать в YouTube Мониторинг Бот!\n\n"
            f"Доступные команды:\n"
            f"/help_notify - Показать все команды и их использование\n"
            f"/add_telegram_notify - Добавить текущий чат в список уведомлений\n"
            f"/remove_notify - Удалить текущий чат из списка уведомлений\n"
            f"/list_notify - Показать все чаты, получающие уведомления\n\n"
            f"Добавьте меня в ваши группы/каналы и используйте эти команды там!",
            parse_mode=ParseMode.HTML
        )

    # ------------------------------------------------------------------------------------#
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /help_notify"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать этого бота.",
                parse_mode=ParseMode.HTML
            )
            return

        help_text = (
            "🤖 <b>Помощь по YouTube Уведомлениям Боту</b>\n\n"
            "<b>Доступные команды:</b>\n\n"
            "🔔 <b>Команды уведомлений:</b>\n"
            "/add_telegram_notify - Добавить текущий чат в список уведомлений\n"
            "/remove_notify - Удалить текущий чат из списка уведомлений\n"
            "/list_notify - Показать все чаты, получающие уведомления\n\n"
            "📺 <b>Команды YouTube каналов:</b>\n"
            "/add_youtube_channel - Добавить YouTube канал для мониторинга\n"
            "/remove_youtube_channel - Удалить YouTube канал\n"
            "/list_youtube_channels - Показать все мониторируемые каналы\n\n"
            "❓ <b>Другие команды:</b>\n"
            "/start_notify - Показать приветственное сообщение\n"
            "/help_notify - Показать это сообщение помощи\n"
            "/how_notify - Показать краткую инструкцию по настройке\n\n"
            "Для подробной инструкции по настройке используйте /how_notify"
        )

        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )

    async def cmd_how(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /how_notify"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать этого бота.",
                parse_mode=ParseMode.HTML
            )
            return

        setup_text = (
            "🚀 <b>Инструкция по настройке бота</b>\n\n"
            "<b>1. Настройка уведомлений:</b>\n"
            "• Добавьте бота в вашу группу/канал\n"
            "• Сделайте бота администратором\n"
            "• Используйте /add_telegram_notify в чате\n"
            "• Проверьте с помощью /list_notify\n\n"
            "<b>2. Добавление YouTube каналов:</b>\n"
            "• Найдите ID YouTube канала\n"
            "• Используйте: /add_youtube_channel [channel_name] [channel_id]\n"
            "• Пример: /add_youtube_channel PewDiePie UC-lHJZR3Gqxm24_Vd_AJ5Yw\n"
            "• Проверьте с помощью /list_youtube_channels\n\n"
            "<b>3. Работа бота:</b>\n"
            "• Бот проверяет новые видео каждые 5 минут\n"
            "• Уведомления отправляются автоматически\n"
            "• Убедитесь, что бот остается администратором\n\n"
            "<b>4. Управление:</b>\n"
            "• Удалить каналы: /remove_youtube_channel [channel_id]\n"
            "• Остановить уведомления: /remove_notify\n"
            "• Показать настройки: /list_notify и /list_youtube_channels\n\n"
            "Для списка команд используйте /help_notify"
        )

        await update.message.reply_text(
            setup_text,
            parse_mode=ParseMode.HTML
        )

    # ------------------------------------------------------------------------------------#

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /add_telegram_notify"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            chat = await self.bot.get_chat(chat_id)
            chat_title = chat.title or str(chat_id)

            if self.config.add_chat(chat_id, chat_title, chat_type):
                await update.message.reply_text(
                    f"✅ Успешно добавлен чат в список уведомлений!\n\n"
                    f"Чат: <b>{chat_title}</b>\n"
                    f"Тип: {chat_type}\n"
                    f"ID: <code>{chat_id}</code>\n\n"
                    f"Проверьте /list_notify, чтобы увидеть все настроенные чаты.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Этот чат уже получает уведомления.\n\n"
                    f"Чат: <b>{chat_title}</b>\n"
                    f"ID: <code>{chat_id}</code>",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка добавления чата: {str(e)}",
                parse_mode=ParseMode.HTML
            )

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /remove_notify"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            chat = await self.bot.get_chat(chat_id)
            chat_title = chat.title or str(chat_id)

            if self.config.remove_chat(chat_id):
                await update.message.reply_text(
                    f"✅ Успешно удален чат из списка уведомлений!\n\n"
                    f"Чат: <b>{chat_title}</b>\n"
                    f"ID: <code>{chat_id}</code>\n\n"
                    f"Используйте /add_telegram_notify, чтобы снова начать получать уведомления.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Этот чат не был в списке уведомлений.\n\n"
                    f"Чат: <b>{chat_title}</b>\n"
                    f"ID: <code>{chat_id}</code>\n\n"
                    f"Используйте /add_telegram_notify, чтобы начать получать уведомления.",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка удаления чата: {str(e)}",
                parse_mode=ParseMode.HTML
            )

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /list_notify"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            chats = self.config.get_chats()

            if not chats:
                await update.message.reply_text(
                    "📝 Нет чатов, получающих уведомления.\n\n"
                    "Используйте /add_telegram_notify в группе/канале, чтобы добавить его в список.",
                    parse_mode=ParseMode.HTML
                )
                return

            chat_list = []
            for chat in chats:
                chat_id = chat['id']
                try:
                    chat_info = await self.bot.get_chat(chat_id)
                    chat_title = chat_info.title or str(chat_id)
                    chat_type = chat_info.type
                    chat_list.append(
                        f"• <b>{chat_title}</b>\n"
                        f"  Тип: {chat_type}\n"
                        f"  ID: <code>{chat_id}</code>\n"
                        f"  Добавлен: {chat.get('added_at', 'Неизвестно')}"
                    )
                except Exception:
                    chat_list.append(
                        f"• ID: <code>{chat_id}</code>\n"
                        f"  Тип: {chat.get('type', 'неизвестно')}\n"
                        f"  Добавлен: {chat.get('added_at', 'Неизвестно')}\n"
                        f"  (Не удалось получить текущую информацию о чате)"
                    )

            message = "📝 <b>Чаты, получающие уведомления:</b>\n\n" + "\n\n".join(chat_list)

            if len(message) > 4096:
                chunks = [message[i:i + 4096] for i in range(0, len(message), 4096)]
                for chunk in chunks:
                    await update.message.reply_text(
                        chunk,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка отображения чатов: {str(e)}",
                parse_mode=ParseMode.HTML
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать ошибки Telegram"""
        print(f'Ошибка Telegram: {context.error}')

    # ------------------------------------------------------------------------------------#
    async def cmd_add_youtube_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /add_youtube_channel"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        # Проверить аргументы команды
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование: /add_youtube_channel <channel_name> <channel_id>\n\n"
                "Пример: /add_youtube_channel PewDiePie UC-lHJZR3Gqxm24_Vd_AJ5Yw",
                parse_mode=ParseMode.HTML
            )
            return

        channel_name = context.args[0]
        channel_id = context.args[1]

        try:
            # Проверить, существует ли канал на YouTube перед добавлением
            response = self.youtube.channels().list(
                part="snippet",
                id=channel_id
            ).execute()

            if not response.get('items'):
                await update.message.reply_text(
                    f"❌ Не удалось найти YouTube канал с ID: {channel_id}\n"
                    f"Пожалуйста, проверьте правильность ID канала.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Получить фактическое имя канала с YouTube, если доступно
            actual_name = response['items'][0]['snippet']['title']

            if self.config.add_youtube_channel(actual_name, channel_id):
                await update.message.reply_text(
                    f"✅ Успешно добавлен YouTube канал!\n\n"
                    f"Канал: <b>{actual_name}</b>\n"
                    f"ID: <code>{channel_id}</code>",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"ℹ️ Этот канал уже в списке мониторинга.\n\n"
                    f"Канал: <b>{actual_name}</b>\n"
                    f"ID: <code>{channel_id}</code>",
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка добавления канала: {str(e)}",
                parse_mode=ParseMode.HTML
            )

    async def cmd_remove_youtube_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /remove_youtube_channel"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        if not context.args:
            await update.message.reply_text(
                "❌ Использование: /remove_youtube_channel <channel_id>\n\n"
                "Используйте /list_youtube_channels, чтобы увидеть все ID каналов",
                parse_mode=ParseMode.HTML
            )
            return

        channel_id = context.args[0]
        channel = self.config.get_youtube_channel(channel_id)

        if self.config.remove_youtube_channel(channel_id):
            await update.message.reply_text(
                f"✅ Успешно удален YouTube канал!\n\n"
                f"Канал: <b>{channel['name']}</b>\n"
                f"ID: <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"❌ Канал с ID <code>{channel_id}</code> не найден в списке мониторинга.\n\n"
                f"Используйте /list_youtube_channels, чтобы увидеть все мониторируемые каналы.",
                parse_mode=ParseMode.HTML
            )

    async def cmd_list_youtube_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработать команду /list_youtube_channels"""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                "⛔️ Извините, только администраторы могут использовать эту команду.",
                parse_mode=ParseMode.HTML
            )
            return

        channels = self.config.get_youtube_channels()

        if not channels:
            await update.message.reply_text(
                "📝 Нет YouTube каналов, находящихся под мониторингом.\n\n"
                "Используйте /add_youtube_channel, чтобы добавить канал.",
                parse_mode=ParseMode.HTML
            )
            return

        channel_list = []
        for channel in channels:
            channel_list.append(
                f"• <b>{channel['name']}</b>\n"
                f"  ID: <code>{channel['id']}</code>"
            )

        message = "📝 <b>Мониторинг YouTube Каналов:</b>\n\n" + "\n\n".join(channel_list)

        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML
        )

    # ----------------------------------------------------------------------------------#

    async def get_channel_id(self, channel_data):
        """Получить ID канала из словаря данных канала"""
        try:
            channel_id = channel_data['id'].strip()
            channel_name = channel_data['name']

            # Сначала проверить кэш
            if channel_id in self.channel_cache:
                return self.channel_cache[channel_id]

            # Проверить, существует ли ID канала
            response = self.youtube.channels().list(
                part="id,snippet",
                id=channel_id
            ).execute()

            if response.get('items'):
                self.channel_cache[channel_id] = channel_id
                print(f"Успешно проверен канал: {channel_name} ({channel_id})")
                return channel_id

            print(f"Не удалось проверить ID канала {channel_id} для {channel_name}")
            return None

        except Exception as e:
            print(f"Ошибка проверки канала {channel_data.get('name', 'Неизвестно')}: {str(e)}")
            return None

    async def check_channel(self, session, channel_data):
        """Проверить YouTube канал на наличие новых загрузок"""
        try:
            channel_id = await self.get_channel_id(channel_data)
            if not channel_id:
                print(f"Пропуск канала {channel_data['name']} - не удалось проверить ID {channel_data['id']}")
                return

            # Получить видео после последней проверки
            last_check_time = self.last_check.get(channel_id, datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )).isoformat()

            activities = self.youtube.activities().list(
                part="contentDetails,snippet",
                channelId=channel_id,
                publishedAfter=last_check_time,
                maxResults=5
            ).execute()

            videos_to_process = []
            for item in activities.get('items', []):
                if 'upload' not in item.get('contentDetails', {}):
                    continue

                video_id = item['contentDetails']['upload']['videoId']
                video = self.youtube.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=video_id
                ).execute()['items'][0]

                upload_date = datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00'))
                videos_to_process.append((upload_date, video))

            # Сортировать видео по дате загрузки, сначала новые
            videos_to_process.sort(key=lambda x: x[0], reverse=True)

            for upload_date, video in videos_to_process:
                await self.process_video(session, video)

            # Обновить время последней проверки
            self.last_check[channel_id] = datetime.now(timezone.utc)

        except Exception as e:
            print(f"Ошибка проверки {channel_data['name']}: {str(e)}")
            await asyncio.sleep(5)

    async def process_video(self, session, video):
        """Обработать одно видео и отправить уведомления"""
        if self.shutdown_event.is_set():
            return

        video_id = video['id']
        thumbnail_url = (
                video['snippet']['thumbnails'].get('maxres') or
                video['snippet']['thumbnails'].get('high') or
                video['snippet']['thumbnails']['default']
        )['url']

        async with session.get(thumbnail_url) as response:
            if response.status != 200:
                return
            thumbnail_data = await response.read()

        duration = video['contentDetails']['duration'].replace('PT', '').lower()
        duration = duration.replace('h', ':').replace('m', ':').replace('s', '')

        upload_date = datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00'))
        formatted_date = upload_date.strftime('%Y-%m-%d %H:%M UTC')

        caption = (
            f"🔥<b>НОВАЯ ЗАГРУЗКА СМОТРИТЕ СЕЙЧАС</b>🔥\n"
            f"═══════════════\n"
            f"🎬 <b><a href='https://youtube.com/watch?v={video_id}'>{video['snippet']['title']}</a></b>\n"
            f"📺 <b><a href='https://youtube.com/channel/{video['snippet']['channelId']}?sub_confirmation=1'>{video['snippet']['channelTitle']}</a></b>\n"
            f"📅 {formatted_date}\n"
            f"#НовоеВидео #{video['snippet']['channelTitle'].replace(' ', '')}"
        )

        await self.send_notifications(thumbnail_data, caption)

    async def send_notifications(self, thumbnail_data, caption):
        """Отправить уведомления во все настроенные Telegram чаты"""
        chat_ids = self.config.get_telegram_chats()
        total_chats = len(chat_ids)

        batch_size = 3
        for i in range(0, total_chats, batch_size):
            if self.shutdown_event.is_set():
                return

            batch = chat_ids[i:i + batch_size]
            for chat_id in batch:
                await self.send_notification_to_chat(chat_id, thumbnail_data, caption)

            if i + batch_size < total_chats:
                await asyncio.sleep(3)

    async def send_notification_to_chat(self, chat_id, thumbnail_data, caption):
        """Отправить уведомление в один чат"""
        try:
            await self.bot.send_photo(
                chat_id=chat_id,
                photo=BytesIO(thumbnail_data),
                caption=caption,
                parse_mode=ParseMode.HTML,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            print(f"✅ Отправлено уведомление в чат {chat_id}")
            await asyncio.sleep(2)

        except Exception as e:
            error_message = str(e).lower()
            if "chat not found" in error_message or "bot was blocked" in error_message:
                print(f"❌ Чат {chat_id} недоступен (будет удален): {str(e)}")
                self.config.remove_telegram_chat(chat_id)
                return

            if "timeout" in error_message or "connection" in error_message:
                print(f"⚠️ Сетевая ошибка для чата {chat_id}, повторная попытка: {str(e)}")
                await asyncio.sleep(5)
                try:
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=BytesIO(thumbnail_data),
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        read_timeout=30,
                        write_timeout=30,
                        connect_timeout=30,
                        pool_timeout=30
                    )
                    print(f"✅ Повторная попытка для чата {chat_id} успешна")
                except Exception as retry_e:
                    print(f"❌ Повторная попытка для чата {chat_id} не удалась: {str(retry_e)}")
            else:
                print(f"❌ Не удалось отправить в чат {chat_id}: {str(e)}")

    async def monitor_channels(self):
        """Основной цикл мониторинга"""
        self.running = True
        while not self.shutdown_event.is_set():
            try:
                channels = self.config.get_youtube_channels()
                print(f"\nПроверка {len(channels)} каналов в {datetime.now()}")
                print("Каналы для проверки:", ", ".join(c['name'] for c in channels))

                conn = aiohttp.TCPConnector(limit=5, force_close=True)
                timeout = aiohttp.ClientTimeout(total=60)

                async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                    tasks = []
                    for channel_data in channels:
                        if self.shutdown_event.is_set():
                            break
                        task = asyncio.create_task(self.check_channel(session, channel_data))
                        tasks.append(task)
                        await asyncio.sleep(2)

                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)

                if self.shutdown_event.is_set():
                    break

                print("\nОжидание следующей проверки...")
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=self.check_interval
                    )
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                print(f"Ошибка мониторинга: {str(e)}")
                await asyncio.sleep(30)

        print("Мониторинг остановлен корректно")
        self.running = False

    async def run(self):
        """Запустить мониторинг и Telegram бота"""
        application = Application.builder().token(self.bot_token).build()

        # Добавить обработчики команд
        application.add_handler(CommandHandler('start_notify', self.cmd_start))
        application.add_handler(CommandHandler('help_notify', self.cmd_help))
        application.add_handler(CommandHandler('how_notify', self.cmd_how))
        application.add_handler(CommandHandler('add_telegram_notify', self.cmd_add))
        application.add_handler(CommandHandler('remove_notify', self.cmd_remove))
        application.add_handler(CommandHandler('list_notify', self.cmd_list))

        # Команды управления YouTube каналами
        application.add_handler(CommandHandler('add_youtube_channel', self.cmd_add_youtube_channel))
        application.add_handler(CommandHandler('remove_youtube_channel', self.cmd_remove_youtube_channel))
        application.add_handler(CommandHandler('list_youtube_channels', self.cmd_list_youtube_channels))

        application.add_error_handler(self.error_handler)

        # Запустить приложение и мониторинг
        async with application:
            await application.initialize()
            await application.start()
            await application.updater.start_polling()

            monitor_task = asyncio.create_task(self.monitor_channels())

            # Настроить обработчики сигналов
            if platform.system() != 'Windows':
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(
                        sig,
                        lambda s=sig: asyncio.create_task(self.handle_shutdown(application, monitor_task, s))
                    )
            else:
                for sig in (signal.SIGTERM, signal.SIGINT):
                    signal.signal(
                        sig,
                        lambda s, f, app=application, task=monitor_task:
                        asyncio.create_task(self.handle_shutdown(app, task, s))
                    )

            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    async def handle_shutdown(self, application, monitor_task, sig):
        """Обработать сигнал завершения"""
        print(f"\nПолучен сигнал {sig}")
        self.shutdown_event.set()
        monitor_task.cancel()
        await application.stop()
        await application.shutdown()
        sys.exit(0)


async def main():
    bot = YouTubeTelegramBot()
    bot.config.list_all()
    await bot.run()


if __name__ == "__main__":
    print("Запуск YouTube Мониторинга и Telegram Бота...")
    asyncio.run(main())

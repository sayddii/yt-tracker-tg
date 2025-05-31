import json
import os
from datetime import datetime
from pathlib import Path


class TelegramConfig:
    def __init__(self):
        self.data_folder = Path('pydata')
        self.chats_file = self.data_folder / 'telegram_chats.json'
        self.channels_file = self.data_folder / 'influencers.json'
        self.ensure_data_folder()
        self.load_chats()
        self.load_channels()

    def ensure_data_folder(self):
        if not self.data_folder.exists():
            print(f"Создание папки данных: {self.data_folder}")
            self.data_folder.mkdir(parents=True)

        if not self.chats_file.exists():
            print(f"Инициализация файла чатов: {self.chats_file}")
            self.save_chats([])

        if not self.channels_file.exists():
            print(f"Инициализация файла каналов: {self.channels_file}")
            initial_channels = {
                "channels": []
            }
            with open(self.channels_file, 'w') as f:
                json.dump(initial_channels, f, indent=4)

    def load_chats(self):
        try:
            with open(self.chats_file, 'r') as f:
                self.chats = json.load(f)
            print(f"Загружено {len(self.chats)} чатов из {self.chats_file}")
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"Не найден файл чатов, начинаем с нуля")
            self.chats = []
            self.save_chats(self.chats)

    def load_channels(self):
        try:
            with open(self.channels_file, 'r') as f:
                data = json.load(f)
                self.channels = data.get('channels', [])
            print(f"Загружено {len(self.channels)} каналов из {self.channels_file}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Ошибка загрузки файла каналов: {str(e)}")
            self.channels = []

    def save_chats(self, chats):
        with open(self.chats_file, 'w') as f:
            json.dump(chats, f, indent=2)
        self.chats = chats
        print(f"Сохранено {len(chats)} чатов в {self.chats_file}")

    def add_chat(self, chat_id: int, chat_title: str = None, chat_type: str = None) -> bool:
        chat_id = int(chat_id)

        if chat_id in [chat['id'] for chat in self.chats]:
            print(f"Чат {chat_id} уже существует в конфигурации")
            return False

        chat_data = {
            'id': chat_id,
            'title': chat_title or str(chat_id),
            'type': chat_type or 'неизвестно',
            'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        self.chats.append(chat_data)
        self.save_chats(self.chats)
        print(f"Добавлен новый чат: {chat_data}")
        return True

    def remove_chat(self, chat_id: int) -> bool:
        chat_id = int(chat_id)
        original_length = len(self.chats)

        self.chats = [chat for chat in self.chats if chat['id'] != chat_id]

        if len(self.chats) < original_length:
            self.save_chats(self.chats)
            print(f"Удален чат {chat_id}")
            return True
        print(f"Чат {chat_id} не найден в конфигурации")
        return False

    def add_youtube_channel(self, channel_name: str, channel_id: str) -> bool:
        channel_name = channel_name.strip()
        channel_id = channel_id.strip()

        if any(c['id'] == channel_id for c in self.channels):
            return False

        self.channels.append({
            'name': channel_name,
            'id': channel_id
        })

        with open(self.channels_file, 'w') as f:
            json.dump({'channels': self.channels}, f, indent=4)

        return True

    def remove_youtube_channel(self, channel_id: str) -> bool:
        channel_id = channel_id.strip()
        original_length = len(self.channels)

        self.channels = [c for c in self.channels if c['id'] != channel_id]

        if len(self.channels) < original_length:
            with open(self.channels_file, 'w') as f:
                json.dump({'channels': self.channels}, f, indent=4)
            return True

        return False

    def get_youtube_channel(self, channel_id: str) -> dict:
        channel_id = channel_id.strip()
        for channel in self.channels:
            if channel['id'] == channel_id:
                return channel
        return None

    def get_chats(self) -> list:
        return self.chats

    def get_chat_ids(self) -> list:
        return [chat['id'] for chat in self.chats]

    def get_telegram_chats(self) -> list:
        return [chat['id'] for chat in self.chats]

    def get_youtube_channels(self) -> list:
        return self.channels

    def list_all(self):
        print("\n=== Текущая Конфигурация ===")
        print(f"Папка данных: {self.data_folder}")
        print(f"Файл чатов: {self.chats_file}")
        print(f"Файл каналов: {self.channels_file}")

        print(f"\nМониторинг YouTube Каналов ({len(self.channels)}):")
        for channel in self.channels:
            print(f"- {channel['name']} (ID: {channel['id']})")

        print(f"\nНастроенные Telegram Чат ({len(self.chats)}):")
        if not self.chats:
            print("Нет настроенных чатов")
        else:
            for chat in self.chats:
                print(f"- {chat['title']} (ID: {chat['id']})")
                print(f"  Тип: {chat['type']}")
                print(f"  Добавлен: {chat['added_at']}")
        print("=" * 30 + "\n")

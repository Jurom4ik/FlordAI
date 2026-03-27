import asyncio
import logging
from typing import Optional, List
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import Config
from llm_provider import LLMProvider


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram бот для управления Flord AI"""
    
    def __init__(self, config: Config, llm_provider: LLMProvider, mind=None):
        self.config = config
        self.llm_provider = llm_provider
        self.mind = mind
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить бота"""
        if not self.config.telegram_bot_token:
            logger.warning("Telegram токен не настроен. Бот не запущен.")
            return False
        
        if not self.config.telegram_enabled:
            logger.info("Telegram бот отключен в настройках.")
            return False
        
        try:
            self.bot = Bot(token=self.config.telegram_bot_token)
            self.dp = Dispatcher()
            
            self._register_handlers()
            
            self._running = True
            logger.info("Telegram бот запущен!")
            
            # Запускаем polling в отдельной задаче
            self._task = asyncio.create_task(self.dp.start_polling(self.bot))
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска Telegram бота: {e}")
            return False
    
    async def stop(self):
        """Остановить бота"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.bot:
            await self.bot.session.close()
        logger.info("Telegram бот остановлен")
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        
        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            if not self._check_access(message.from_user.id):
                await message.answer("⛔ У вас нет доступа к этому боту.")
                return
            
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🤖 Статус ИИ")],
                    [KeyboardButton(text="💬 Новый чат")],
                    [KeyboardButton(text="⚙️ Провайдер")],
                ],
                resize_keyboard=True
            )
            
            await message.answer(
                f"👋 Привет! Я *Flord AI* - ваш умный ассистент.\n\n"
                f"Просто отправьте мне сообщение, и я помогу вам!\n\n"
                f"Текущий провайдер: *{self.config.provider}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        
        @self.dp.message(Command("status"))
        async def cmd_status(message: Message):
            if not self._check_access(message.from_user.id):
                return
            
            status = self._get_status_text()
            await message.answer(status, parse_mode=ParseMode.MARKDOWN)
        
        @self.dp.message(Command("provider"))
        async def cmd_provider(message: Message):
            if not self._check_access(message.from_user.id):
                return
            
            await message.answer(
                f"*Текущий провайдер:* {self.config.provider}\n\n"
                f"Доступные провайдеры:\n"
                f"• `openrouter` - OpenRouter API\n"
                f"• `ollama` - Локальные модели\n\n"
                f"Для смены используйте настройки в приложении.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        @self.dp.message(Command("newchat"))
        async def cmd_newchat(message: Message):
            if not self._check_access(message.from_user.id):
                return
            
            if self.mind:
                self.mind.init_new_chat()
            
            await message.answer("✅ Новый чат создан! История очищена.")
        
        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            if not self._check_access(message.from_user.id):
                return
            
            help_text = """
*Доступные команды:*

/start - Начать работу
/status - Статус системы
/provider - Информация о провайдере
/newchat - Новый чат (очистить историю)
/help - Показать помощь

Просто отправьте текстовое сообщение для общения с ИИ!
            """
            await message.answer(help_text, parse_mode=ParseMode.MARKDOWN)
        
        @self.dp.message(F.text == "🤖 Статус ИИ")
        async def btn_status(message: Message):
            await cmd_status(message)
        
        @self.dp.message(F.text == "💬 Новый чат")
        async def btn_newchat(message: Message):
            await cmd_newchat(message)
        
        @self.dp.message(F.text == "⚙️ Провайдер")
        async def btn_provider(message: Message):
            await cmd_provider(message)
        
        @self.dp.message()
        async def handle_message(message: Message):
            if not self._check_access(message.from_user.id):
                return
            
            # Показываем статус "печатает"
            await self.bot.send_chat_action(message.chat.id, "typing")
            
            try:
                # Получаем ответ от ИИ
                user_message = message.text
                
                if self.mind:
                    # Используем Mind для обработки
                    response = await self._get_mind_response(user_message)
                else:
                    # Прямой запрос к LLM
                    messages = [{"role": "user", "content": user_message}]
                    response = self.llm_provider.chat_stream(messages)
                
                # Отправляем ответ
                if len(response) > 4000:
                    # Разбиваем длинные сообщения
                    for i in range(0, len(response), 4000):
                        chunk = response[i:i+4000]
                        await message.answer(chunk)
                else:
                    await message.answer(response)
                    
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
                await message.answer(f"❌ Ошибка: {e}")
    
    def _check_access(self, user_id: int) -> bool:
        """Проверить доступ пользователя"""
        if not self.config.telegram_allowed_users:
            return True  # Если список пустой - доступ всем
        return user_id in self.config.telegram_allowed_users
    
    def _get_status_text(self) -> str:
        """Получить текст статуса"""
        provider_status = "✅" if self.llm_provider.is_available() else "❌"
        
        if self.config.provider == "openrouter":
            model = self.config.openrouter_model
        else:
            model = self.config.ollama_model
        
        return (
            f"*📊 Статус Flord AI*\n\n"
            f"Провайдер: {self.config.provider} {provider_status}\n"
            f"Модель: `{model}`\n"
            f"Телеграм бот: {'✅ Активен' if self._running else '❌ Остановлен'}"
        )
    
    async def _get_mind_response(self, user_message: str) -> str:
        """Получить ответ через Mind"""
        # Создаем placeholder для ответа
        full_response = ""
        
        def on_chunk(text: str):
            nonlocal full_response
            full_response = text
        
        # Добавляем сообщение в историю и получаем ответ
        if hasattr(self.mind, 'messages_array'):
            self.mind.messages_array.append({"role": "user", "content": user_message})
            
            # Получаем потоковый ответ
            response = self.llm_provider.chat_stream(
                self.mind.messages_array,
                on_chunk=on_chunk
            )
            
            # Сохраняем в историю
            self.mind.messages_array.append({"role": "assistant", "content": response})
            
            # Проверяем и выполняем код если есть
            if hasattr(self.mind, 'code_exec_result'):
                code_result = self.mind.code_exec_result(response)
                if code_result:
                    return code_result
            
            return response
        
        return "Ошибка: Mind не настроен"
    
    def send_notification(self, text: str):
        """Отправить уведомление всем разрешенным пользователям"""
        if not self.bot or not self._running:
            return
        
        # Асинхронная отправка
        asyncio.create_task(self._send_notification_async(text))
    
    async def _send_notification_async(self, text: str):
        """Асинхронная отправка уведомлений"""
        if self.config.telegram_allowed_users:
            for user_id in self.config.telegram_allowed_users:
                try:
                    await self.bot.send_message(user_id, f"🔔 *Уведомление:*\n{text}", parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

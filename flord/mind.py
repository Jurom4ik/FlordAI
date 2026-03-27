import importlib
import re
import threading
import asyncio
import sys
import os
from dataclasses import dataclass
from typing import Optional, Callable

from llm_provider import LLMProvider
from config import Config
from package_manager import package_manager
from admin_helper import ensure_admin_and_execute, is_admin


pattern_code = r"<python>(.*?)</python>"

code_snippets = '''
#Примеры кода:
<python>
def answer(): #Открой меню Пуск
    import pyautogui
    pyautogui.press(\'win\')
    return "Я открыл меню Пуск"
</python>

<python>
def answer(): #Какой заряд батареи?
    import psutil
    battery = psutil.sensors_battery()
    percent = int(battery.percent)
    return f"Заряд батареи: {percent}%"
</python>

<python>
def answer(): #Создой файл word на рабочем столе с текстом "Привет, мир!"
    from docx import Document
    import os
    doc = Document()
    doc.add_paragraph("Привет, мир!")
    doc.save(f"C:/Users/{os.getlogin()}/Desktop/файл.docx")
    return "Хорошо"
</python>

<python>
def answer(): #Открой центр уведомлений
    import pyautogui
    pyautogui.hotkey(\'win\', \'n\', interval=0.2)
    return "Я открыл центр уведомлений"
</python>

<python>
def answer(): #Открой настройки
    import os
    os.system('start ms-settings:')
    return "Хорошо"
</python>

<python>
def answer(): #Открой настройки интернета
    import os
    os.system(f'start ms-settings:network')
    return "Хорошо"
</python>

<python>
def answer(): #Громкость на 60%
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(0.6, None)
    return "Громкость установлена на 60%"
</python>

'''

init_message = f'''
Ты - умный помощник для операционной системы Windows 11. Тебя зовут Flord.
Ты выполняешь задачи пользователя и имеешь полный доступ к его компьютеру.
Ты можешь использовать Python для решения задач, поставленных пользователем.
Чтобы выполнить какой-либо код, оформи ответ следующим образом:
<python>
def answer():
    #твой код
    return result #result - это str
</python>
Важно использовать теги <python>...</python>
Ты можешь пользоваться ЛЮБЫМИ модулями Python. Если нужный модуль не установлен - он будет установлен автоматически.
Функция всегда должна называться "answer" и возвращать строку.
Используй код, когда это необходимо для решения задачи пользователя.
Можешь выполнять любые операции: работа с файлами, системные вызовы, автоматизация.

{code_snippets}

Для начала поздоровайся
'''


class Mind:
    messages_array = []
    thread = None
    titleBar = None
    on_response_update: Optional[Callable] = None
    llm_provider: Optional[LLMProvider] = None
    current_request_cancelled: bool = False
    is_processing: bool = False
    
    def __init__(self, config: Config = None):
        super().__init__()
        self.config = config or Config.load()
        self.init_llm_provider()
        self.init_new_chat()
    
    def init_llm_provider(self):
        """Инициализировать LLM провайдер"""
        provider = self.config.provider
        
        if provider == "openrouter":
            self.llm_provider = LLMProvider(
                provider_type="openrouter",
                config={
                    "api_key": self.config.openrouter_api_key,
                    "model": self.config.openrouter_model
                }
            )
        elif provider == "gemini":
            self.llm_provider = LLMProvider(
                provider_type="gemini",
                config={
                    "api_key": self.config.gemini_api_key,
                    "model": self.config.gemini_model
                }
            )
        elif provider == "groq":
            self.llm_provider = LLMProvider(
                provider_type="groq",
                config={
                    "api_key": self.config.groq_api_key,
                    "model": self.config.groq_model
                }
            )
        else:  # ollama
            self.llm_provider = LLMProvider(
                provider_type="ollama",
                config={
                    "host": self.config.ollama_host,
                    "model": self.config.ollama_model
                }
            )
    
    def switch_provider(self, provider_type: str):
        """Сменить провайдера"""
        self.config.provider = provider_type
        self.init_llm_provider()
        self.config.save()
    
    def init_new_chat(self):
        """Начать новый чат"""
        self.messages_array = [
            {"role": "user", "content": init_message},
        ]

    def cancel_current_request(self):
        """Отменить текущий запрос"""
        if self.is_processing:
            self.current_request_cancelled = True
            self.is_processing = False
            if self.titleBar:
                self.titleBar.set_animation(0)
            return True
        return False

    def get_ai_response(self, input_string, card=None):
        """Получить ответ от ИИ"""
        self.current_request_cancelled = False
        self.is_processing = True
        
        if self.titleBar:
            self.titleBar.set_animation(1)
        
        self.messages_array.append({"role": "user", "content": input_string})
        
        # Определяем callback для обновления UI
        def on_chunk(text: str):
            if self.current_request_cancelled:
                return
            if card:
                result = Message()
                result.from_string(text)
                card.set_content(result)
        
        # Запускаем в отдельном потоке
        self.thread = threading.Thread(
            target=self._response_thread, 
            args=(on_chunk,)
        )
        self.thread.start()
    
    def _response_thread(self, on_chunk: Callable[[str], None] = None):
        """Поток получения ответа"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries and not self.current_request_cancelled:
            try:
                # Получаем ответ через LLM провайдер
                response = self.llm_provider.chat_stream(
                    messages=self.messages_array,
                    on_chunk=on_chunk
                )
                
                if self.current_request_cancelled:
                    break

                # Проверяем, пустой ли ответ
                if response.strip() == "":
                    retry_count += 1
                    print(f"Пустой ответ получен. Повторная попытка {retry_count} из {max_retries}.")
                    continue
                else:
                    self.messages_array.append({"role": "assistant", "content": response})

                    # Проверяем и выполняем код если есть
                    code_result = self.code_exec_result(response)
                    if code_result is not None and on_chunk and not self.current_request_cancelled:
                        # Обновляем с результатом выполнения кода
                        result = Message(text=code_result)
                        if self.on_response_update:
                            self.on_response_update(result)
                    
                    break

            except Exception as e:
                retry_count += 1
                print(f"Ошибка при получении ответа: {e}. Попытка {retry_count} из {max_retries}.")
                continue

        if retry_count == max_retries:
            print("Не удалось получить ответ от модели после нескольких попыток.")
            if on_chunk and not self.current_request_cancelled:
                on_chunk("Извините, не удалось получить ответ. Попробуйте ещё раз.")
        
        self.is_processing = False
        if self.titleBar:
            self.titleBar.set_animation(0)

    def code_exec_result(self, input_str):
        """Выполнить код из ответа ИИ с автоустановкой пакетов и UAC если нужно"""
        try:
            if "<python>" in input_str and "</python>" in input_str:
                match = re.search(pattern_code, input_str, re.DOTALL)
                if match:
                    code_inside_tags = match.group(1)
                    code = code_inside_tags
                    
                    # 1. Проверяем и устанавливаем необходимые пакеты
                    installed, failed = package_manager.install_for_code(code)
                    if installed:
                        print(f"✅ Установлены пакеты: {', '.join(installed)}")
                    if failed:
                        print(f"❌ Не удалось установить: {', '.join(failed)}")
                    
                    # 2. Выполняем код с автоматическим UAC запросом если нужно
                    result = ensure_admin_and_execute(code)
                    return result
                    
            else:
                return None
        except Exception as e:
            return f"Ошибка выполнения кода: {e}"
    
    def _check_if_requires_admin(self, code: str) -> bool:
        """Проверить требует ли код прав администратора (встроенная проверка)"""
        admin_keywords = [
            'os.system', 'subprocess', 'ctypes.windll',
            'win32api', 'win32con', 'pycaw', 'comtypes',
            'registry', 'HKEY_', 'windows', 'program files',
        ]
        
        code_lower = code.lower()
        for keyword in admin_keywords:
            if keyword.lower() in code_lower:
                return True
        return False


@dataclass
class Message:
    text: str = None
    code: str = None

    def from_string(self, s: str):
        if "<python>" in s:
            self.text = s.split("<python>")[0]
            self.code = s.split("<python>")[1]
        else:
            self.text = s
            return self

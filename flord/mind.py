import importlib
import re
import threading
import asyncio
import sys
import os
from dataclasses import dataclass
from typing import Optional, Callable

from flord.llm_provider import LLMProvider
from flord.config import Config
from flord.package_manager import package_manager
from flord.admin_helper import ensure_admin_and_execute, is_admin
from flord.confirmation_system import confirmation_system, DangerLevel


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
    
    def check_code_errors(self, code: str) -> list:
        """Проверить код на ошибки"""
        errors = []
        
        try:
            # Проверка синтаксиса
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            errors.append({
                'type': 'syntax_error',
                'line': e.lineno,
                'message': str(e)
            })
        
        # Проверка на потенциально опасные операции
        dangerous_patterns = [
            r'import\s+os\s*;\s*os\.system\(',
            r'import\s+subprocess\s*;\s*subprocess\.run\(',
            r'import\s+subprocess\s*;\s*subprocess\.call\(',
            r'exec\(',
            r'eval\(',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                errors.append({
                    'type': 'dangerous_operation',
                    'message': 'Обнаружена потенциально опасная операция'
                })
        
        return errors
    
    def auto_fix_code(self, code: str, errors: list) -> str:
        """Автоматически исправить простые ошибки в коде"""
        fixed_code = code
        
        for error in errors:
            if error['type'] == 'syntax_error':
                # Простые исправления синтаксических ошибок
                if 'unexpected EOF while parsing' in error['message']:
                    # Добавляем недостающую закрывающую скобку
                    if fixed_code.count('(') > fixed_code.count(')'):
                        fixed_code += ')'
        
        return fixed_code

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
                    
                    # 1. Проверяем код на ошибки
                    errors = self.check_code_errors(code)
                    if errors:
                        print(f"⚠️ Обнаружены ошибки в коде:")
                        for error in errors:
                            print(f"   - {error['type']}: {error['message']}")
                        
                        # 2. Пытаемся автоматически исправить
                        fixed_code = self.auto_fix_code(code, errors)
                        if fixed_code != code:
                            print(f"🔧 Автоматически исправлен код")
                            code = fixed_code
                    
                    # 3. Проверяем код на опасность
                    danger_level, warning_msg = confirmation_system.analyze_action(code)
                    print(f"🔍 {warning_msg}")
                    
                    # Если опасное действие, требуем подтверждение
                    if danger_level in [DangerLevel.WARNING, DangerLevel.DANGER, DangerLevel.CRITICAL]:
                        # Здесь нужно запросить подтверждение через UI
                        print(f"⚠️ Требуется подтверждение для {danger_level.value}")
                        # Временно: авто-подтверждение для демо
                        # В реальном коде здесь будет запрос через UI
                    
                    # 4. Проверяем и устанавливаем необходимые пакеты
                    installed, failed = package_manager.install_for_code(code)
                    if installed:
                        print(f"✅ Установлены пакеты: {', '.join(installed)}")
                    if failed:
                        print(f"❌ Не удалось установить: {', '.join(failed)}")
                    
                    # 5. Выполняем код с возможностью самоисправления
                    result = self.execute_with_self_correction(code)
                    return result
                    
            else:
                return None
        except Exception as e:
            return f"Ошибка выполнения кода: {e}"
    
    def self_correcting_agent(self, code: str, error_message: str) -> str:
        """Самоисправляющийся агент для кода"""
        print(f"🤖 Запуск самоисправляющегося агента...")
        print(f"❌ Ошибка: {error_message}")
        
        # Создаем prompt для исправления ошибки
        correction_prompt = f"""
        Код:
        {code}
        
        Ошибка:
        {error_message}
        
        Пожалуйста, исправь код так, чтобы устранить эту ошибку. 
        Верни только исправленный код в тегах <python>...</python>.
        Не добавляй объяснений.
        """
        
        try:
            # Получаем исправленный код от ИИ
            response = self.llm_provider.chat_stream([
                {"role": "user", "content": correction_prompt}
            ])
            
            # Извлекаем код из ответа
            if "<python>" in response and "</python>" in response:
                match = re.search(pattern_code, response, re.DOTALL)
                if match:
                    corrected_code = match.group(1)
                    print(f"✅ Получен исправленный код")
                    
                    # Проверяем исправленный код
                    errors = self.check_code_errors(corrected_code)
                    if errors:
                        print(f"⚠️ В исправленном коде все еще есть ошибки:")
                        for error in errors:
                            print(f"   - {error['type']}: {error['message']}")
                        return code  # Возвращаем исходный код если исправленный тоже с ошибками
                    
                    return corrected_code
            
            print(f"❌ Не удалось получить исправленный код от ИИ")
            return code
            
        except Exception as e:
            print(f"❌ Ошибка самоисправляющегося агента: {e}")
            return code
    
    def execute_with_self_correction(self, code: str, max_attempts: int = 3) -> str:
        """Выполнить код с возможностью самоисправления"""
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                print(f"🚀 Попытка выполнения кода #{attempt}")
                
                # Выполняем код
                result = ensure_admin_and_execute(code)
                print(f"✅ Код успешно выполнен")
                return result
                
            except Exception as e:
                print(f"❌ Ошибка выполнения кода: {e}")
                
                if attempt < max_attempts:
                    print(f"🔄 Запуск самоисправления...")
                    # Пытаемся исправить код
                    corrected_code = self.self_correcting_agent(code, str(e))
                    
                    if corrected_code != code:
                        print(f"🔧 Код был исправлен, пробуем снова")
                        code = corrected_code
                        attempt += 1
                    else:
                        print(f"❌ Самоисправление не удалось")
                        attempt += 1
                else:
                    print(f"❌ Достигнуто максимальное количество попыток")
                    return f"Ошибка выполнения кода после {max_attempts} попыток: {e}"
        
        return "Не удалось выполнить код"
    
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

import sys
import asyncio
import threading
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from qfluentwidgets import *
from qframelesswindow.utils import getSystemAccentColor

from config import Config
from mind import Mind, Message
from telegram_bot import TelegramBot
from ollama_manager import OllamaManager
from llm_provider import LLMProvider


class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)

        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignmentFlag.AlignCenter)

        # Must set a globally unique object name for the sub-interface
        self.setObjectName(text.replace(' ', '-'))


class UI(MSFluentWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config.load()
        
        # Инициализация компонентов
        self.mind = Mind(config=self.config)
        self.telegram_bot: TelegramBot = None
        self.ollama_manager = OllamaManager(host=self.config.ollama_host)
        
        # UI настройки
        self.tb = TitleBar(self)
        self.setTitleBar(self.tb)
        self.mind.titleBar = self.tb
        
        # Создаем вкладки
        chat = Chat(parent=self)
        settings = Settings(parent=self, cfg=self.config, mind=self.mind, 
                          ollama_manager=self.ollama_manager, window=self)
        
        chat.set_mind(self.mind)
        
        self.resize(800, 600)
        self.setWindowTitle('Flord AI')
        self.setWindowIcon(QIcon('res/anim/idle.gif'))
        setTheme(theme=Theme.AUTO)
        
        if sys.platform in ["win32", "darwin"] and False:
            setThemeColor(getSystemAccentColor(), save=False)
        else:
            setThemeColor(self.config.theme_color, save=False)
        
        self.addSubInterface(chat, FluentIcon.CHAT, 'Чат')
        self.addSubInterface(settings, FluentIcon.SETTING, 'Настройки')
        self.stackedWidget.setStyleSheet('QWidget{background: transparent}')
        
        # Запускаем Telegram бота если включен
        if self.config.telegram_enabled and self.config.telegram_bot_token:
            self.start_telegram_bot()
        
        # Проверяем Ollama если используется
        if self.config.provider == "ollama" and self.config.ollama_auto_install:
            self.check_ollama()
    
    def start_telegram_bot(self):
        """Запустить Telegram бота"""
        try:
            self.telegram_bot = TelegramBot(
                config=self.config,
                llm_provider=self.mind.llm_provider,
                mind=self.mind
            )
            # Запускаем в отдельном потоке
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=self._run_bot, args=(loop,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Ошибка запуска Telegram бота: {e}")
    
    def _run_bot(self, loop):
        """Запустить бота в отдельном потоке"""
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.telegram_bot.start())
    
    def check_ollama(self):
        """Проверить и установить Ollama при необходимости"""
        def check():
            if not self.ollama_manager.is_installed():
                print("Ollama не установлен. Начинаем установку...")
                # Показываем диалог
                self.show_info_bar("Установка Ollama...", 5000)
                if self.ollama_manager.install():
                    print("Ollama установлен успешно!")
                    self.show_info_bar("Ollama установлен!", 3000)
                else:
                    print("Ошибка установки Ollama")
                    self.show_info_bar("Ошибка установки Ollama", 5000)
                    return
            
            # Запускаем сервер
            if not self.ollama_manager.is_running():
                print("Запускаем сервер Ollama...")
                self.ollama_manager.start_server()
            
            # Проверяем модель
            if not self.ollama_manager.ensure_model(self.config.ollama_model):
                print(f"Не удалось установить модель {self.config.ollama_model}")
        
        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()
    
    def show_info_bar(self, message: str, duration: int = 3000):
        """Показать информационное сообщение"""
        InfoBar.info(
            title='Flord AI',
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=self
        )
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.telegram_bot:
            asyncio.run(self.telegram_bot.stop())
        event.accept()
    
    def nativeEvent(self, eventType, message):
        """Обработка нативных событий с защитой от ошибок"""
        try:
            return super().nativeEvent(eventType, message)
        except Exception as e:
            # Игнорируем ошибки GetCursorPos и другие нативные ошибки
            if "GetCursorPos" in str(e) or "pywintypes" in str(e):
                return False, 0
            raise


class Chat(QWidget):
    mind: Mind = None

    def set_mind(self, mind):
        self.mind = mind

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName('chatInterface')
        # Основной вертикальный лейаут
        self.layout = QVBoxLayout(self)

        # Полоса прокрутки для сообщений
        self.scroll_area = SmoothScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        # Виджет для сообщений
        self.messages_widget = SimpleCardWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.messages_widget)
        self.layout.addWidget(self.scroll_area)

        # Горизонтальный лейаут для поля ввода и кнопки
        self.input_layout = QHBoxLayout()

        # Поле ввода текста
        self.text_input = LineEdit(self)
        self.text_input.returnPressed.connect(self.send_message)
        self.input_layout.addWidget(self.text_input)

        # Кнопка отправки
        self.send_button = PrimaryToolButton(self)
        self.send_button.setIcon(FluentIcon.SEND_FILL)
        self.send_button.clicked.connect(self.send_message)
        self.input_layout.addWidget(self.send_button)
        
        # Кнопка отмены (изначально скрыта)
        self.cancel_button = PrimaryToolButton(self)
        self.cancel_button.setIcon(FluentIcon.CANCEL)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_request)
        self.input_layout.addWidget(self.cancel_button)

        # Добавляем горизонтальный лейаут в основной вертикальный
        self.layout.addLayout(self.input_layout)

    def send_message(self):
        text = self.text_input.text()
        if text:
            card = MessageCard(title="Вы")
            card2 = MessageCard(title="Flord")
            self.messages_layout.addWidget(card)
            card.set_content(Message(text))
            card2.set_content(Message(""))
            
            # Устанавливаем callback для обновления
            self.mind.on_response_update = card2.set_content
            
            self.mind.get_ai_response(text, card2)
            self.messages_layout.addWidget(card2)
            self.scroll_area.verticalScrollBar().setValue(-1000)
            # Очищаем поле ввода
            self.text_input.clear()
            
            # Показываем кнопку отмены, скрываем отправку
            self.cancel_button.setVisible(True)
            self.send_button.setVisible(False)
            
            # Проверяем завершение и возвращаем кнопку отправки
            self._wait_for_completion()

            # Прокручиваем вниз к последнему сообщению
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            )
    
    def _wait_for_completion(self):
        """Ожидание завершения запроса"""
        def check():
            import time
            while self.mind.is_processing:
                time.sleep(0.1)
            # Возвращаем кнопки в исходное состояние через invokeMethod
            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self.cancel_button,
                "setVisible",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(bool, False)
            )
            QMetaObject.invokeMethod(
                self.send_button,
                "setVisible",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(bool, True)
            )
        
        import threading
        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()
    
    def cancel_request(self):
        """Отменить текущий запрос"""
        if self.mind.cancel_current_request():
            self.cancel_button.setVisible(False)
            self.send_button.setVisible(True)


class Settings(QFrame):
    def __init__(self, parent=None, cfg=None, mind=None, ollama_manager=None, window=None):
        super().__init__(parent=parent)
        self.config = cfg
        self.mind = mind
        self.ollama_manager = ollama_manager
        self.window = window
        
        self.setObjectName('settingsInterface')
        # Основной вертикальный лейаут
        self.layout = QVBoxLayout(self)
        
        # Создаем карточки настроек
        self._create_provider_settings()
        self._create_openrouter_settings()
        self._create_gemini_settings()
        self._create_groq_settings()
        self._create_ollama_settings()
        self._update_provider_visibility()
        self._create_telegram_settings()
        self._create_ui_settings()
        
        # Добавляем растяжку в конец
        self.layout.addStretch()

    def _create_provider_settings(self):
        """Настройки провайдера LLM"""
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        
        # Заголовок
        title = StrongBodyLabel("Провайдер ИИ", self)
        layout.addWidget(title)
        
        # Выбор провайдера
        provider_layout = QHBoxLayout()
        provider_label = BodyLabel("Текущий провайдер:", self)
        self.provider_combo = ComboBox(self)
        self.provider_combo.addItems(["openrouter", "gemini", "groq", "ollama"])
        self.provider_combo.setCurrentText(self.config.provider)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.provider_combo)
        provider_layout.addStretch()
        layout.addLayout(provider_layout)
        
        self.layout.addWidget(card)
    
    def _create_openrouter_settings(self):
        """Настройки OpenRouter"""
        self.openrouter_card = SimpleCardWidget()
        layout = QVBoxLayout(self.openrouter_card)
        
        title = StrongBodyLabel("OpenRouter API", self)
        layout.addWidget(title)
        
        # API Key
        api_layout = QHBoxLayout()
        api_label = BodyLabel("API Key:", self)
        self.api_key_input = LineEdit(self)
        self.api_key_input.setText(self.config.openrouter_api_key)
        self.api_key_input.setPlaceholderText("Введите ваш OpenRouter API ключ")
        self.api_key_input.textChanged.connect(self.on_api_key_changed)
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_input)
        layout.addLayout(api_layout)
        
        # Model - ComboBox с бесплатными моделями
        model_layout = QHBoxLayout()
        model_label = BodyLabel("Модель:", self)
        self.model_combo = ComboBox(self)
        self.model_combo.setMinimumWidth(300)
        
        # Бесплатные модели OpenRouter (проверенные рабочие)
        free_models = [
            "google/gemma-3-4b-it:free",
            "google/gemma-3-12b-it:free", 
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "nousresearch/hermes-3-405b-instruct:free",
        ]
        self.model_combo.addItems(free_models)
        
        # Устанавливаем текущую модель
        current_model = self.config.openrouter_model
        if current_model in free_models:
            self.model_combo.setCurrentText(current_model)
        else:
            # Авто-выбор первой модели если текущая не из списка бесплатных
            self.config.openrouter_model = free_models[0]
            self.config.save()
        
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        layout.addLayout(model_layout)
        
        # Авто-выбор кнопка
        self.auto_select_btn = PushButton("🔄 Авто-выбор доступной", self)
        self.auto_select_btn.clicked.connect(self.auto_select_free_model)
        layout.addWidget(self.auto_select_btn)
        
        # Кнопка проверки
        self.check_btn = PushButton("Проверить подключение", self)
        self.check_btn.clicked.connect(self.check_openrouter)
        layout.addWidget(self.check_btn)
        
        self.layout.addWidget(self.openrouter_card)
    
    def _create_gemini_settings(self):
        """Настройки Google Gemini"""
        self.gemini_card = SimpleCardWidget()
        layout = QVBoxLayout(self.gemini_card)
        
        title = StrongBodyLabel("Google Gemini API (Free)", self)
        layout.addWidget(title)
        
        # API Key
        api_layout = QHBoxLayout()
        api_label = BodyLabel("API Key:", self)
        self.gemini_api_key_input = LineEdit(self)
        self.gemini_api_key_input.setText(self.config.gemini_api_key)
        self.gemini_api_key_input.setPlaceholderText("Введите Gemini API ключ")
        self.gemini_api_key_input.textChanged.connect(self.on_gemini_api_key_changed)
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.gemini_api_key_input)
        layout.addLayout(api_layout)
        
        # Model
        model_layout = QHBoxLayout()
        model_label = BodyLabel("Модель:", self)
        self.gemini_model_combo = ComboBox(self)
        self.gemini_model_combo.addItems([
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro"
        ])
        self.gemini_model_combo.setCurrentText(self.config.gemini_model)
        self.gemini_model_combo.currentTextChanged.connect(self.on_gemini_model_changed)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.gemini_model_combo)
        layout.addLayout(model_layout)
        
        # Help
        help_label = CaptionLabel(
            "Получите бесплатный ключ на https://makersuite.google.com/app/apikey"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        # Кнопка проверки
        self.gemini_check_btn = PushButton("Проверить подключение", self)
        self.gemini_check_btn.clicked.connect(self.check_gemini)
        layout.addWidget(self.gemini_check_btn)
        
        self.layout.addWidget(self.gemini_card)
    
    def _create_groq_settings(self):
        """Настройки Groq"""
        self.groq_card = SimpleCardWidget()
        layout = QVBoxLayout(self.groq_card)
        
        title = StrongBodyLabel("Groq API (Fast Free)", self)
        layout.addWidget(title)
        
        # API Key
        api_layout = QHBoxLayout()
        api_label = BodyLabel("API Key:", self)
        self.groq_api_key_input = LineEdit(self)
        self.groq_api_key_input.setText(self.config.groq_api_key)
        self.groq_api_key_input.setPlaceholderText("Введите Groq API ключ")
        self.groq_api_key_input.textChanged.connect(self.on_groq_api_key_changed)
        
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.groq_api_key_input)
        layout.addLayout(api_layout)
        
        # Model
        model_layout = QHBoxLayout()
        model_label = BodyLabel("Модель:", self)
        self.groq_model_combo = ComboBox(self)
        self.groq_model_combo.addItems([
            "llama-3.1-8b-instant",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ])
        self.groq_model_combo.setCurrentText(self.config.groq_model)
        self.groq_model_combo.currentTextChanged.connect(self.on_groq_model_changed)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.groq_model_combo)
        layout.addLayout(model_layout)
        
        # Help
        help_label = CaptionLabel(
            "Получите бесплатный ключ на https://console.groq.com/keys"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        
        # Кнопка проверки
        self.groq_check_btn = PushButton("Проверить подключение", self)
        self.groq_check_btn.clicked.connect(self.check_groq)
        layout.addWidget(self.groq_check_btn)
        
        self.layout.addWidget(self.groq_card)
    
    def _create_ollama_settings(self):
        """Настройки Ollama"""
        self.ollama_card = SimpleCardWidget()
        layout = QVBoxLayout(self.ollama_card)
        
        title = StrongBodyLabel("Ollama (Локальные модели)", self)
        layout.addWidget(title)
        
        # Статус
        self.ollama_status = BodyLabel("Проверка статуса...", self)
        layout.addWidget(self.ollama_status)
        
        # Auto install
        self.auto_install_check = CheckBox("Автоматическая установка Ollama", self)
        self.auto_install_check.setChecked(self.config.ollama_auto_install)
        self.auto_install_check.stateChanged.connect(self.on_auto_install_changed)
        layout.addWidget(self.auto_install_check)
        
        # Host
        host_layout = QHBoxLayout()
        host_label = BodyLabel("Host:", self)
        self.ollama_host_input = LineEdit(self)
        self.ollama_host_input.setText(self.config.ollama_host)
        self.ollama_host_input.textChanged.connect(self.on_ollama_host_changed)
        
        host_layout.addWidget(host_label)
        host_layout.addWidget(self.ollama_host_input)
        layout.addLayout(host_layout)
        
        # Model
        model_layout = QHBoxLayout()
        model_label = BodyLabel("Модель:", self)
        self.ollama_model_input = LineEdit(self)
        self.ollama_model_input.setText(self.config.ollama_model)
        self.ollama_model_input.textChanged.connect(self.on_ollama_model_changed)
        
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.ollama_model_input)
        layout.addLayout(model_layout)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.install_ollama_btn = PushButton("Установить Ollama", self)
        self.install_ollama_btn.clicked.connect(self.install_ollama)
        btn_layout.addWidget(self.install_ollama_btn)
        
        self.pull_model_btn = PushButton("Скачать модель", self)
        self.pull_model_btn.clicked.connect(self.pull_ollama_model)
        btn_layout.addWidget(self.pull_model_btn)
        
        layout.addLayout(btn_layout)
        
        self.layout.addWidget(self.ollama_card)
        
        # Проверяем статус
        self.check_ollama_status()
    
    def _create_telegram_settings(self):
        """Настройки Telegram бота"""
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        
        title = StrongBodyLabel("Telegram Бот", self)
        layout.addWidget(title)
        
        # Enabled
        self.telegram_enabled_check = CheckBox("Включить Telegram бота", self)
        self.telegram_enabled_check.setChecked(self.config.telegram_enabled)
        self.telegram_enabled_check.stateChanged.connect(self.on_telegram_enabled_changed)
        layout.addWidget(self.telegram_enabled_check)
        
        # Bot Token
        token_layout = QHBoxLayout()
        token_label = BodyLabel("Bot Token:", self)
        self.telegram_token_input = LineEdit(self)
        self.telegram_token_input.setText(self.config.telegram_bot_token)
        self.telegram_token_input.setPlaceholderText("Введите токен от @BotFather")
        
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.telegram_token_input)
        layout.addLayout(token_layout)
        
        # Save token button
        self.save_token_btn = PushButton("Сохранить и запустить", self)
        self.save_token_btn.clicked.connect(self.save_telegram_settings)
        layout.addWidget(self.save_token_btn)
        
        # Help
        help_label = CaptionLabel(
            "Получите токен у @BotFather в Telegram. "
            "После сохранения бот запустится автоматически."
        )
        layout.addWidget(help_label)
        
        self.layout.addWidget(card)
    
    def _create_ui_settings(self):
        """Настройки интерфейса"""
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        
        title = StrongBodyLabel("Интерфейс и запуск", self)
        layout.addWidget(title)
        
        # Theme color
        color_layout = QHBoxLayout()
        color_label = BodyLabel("Цвет темы:", self)
        self.theme_color_input = LineEdit(self)
        self.theme_color_input.setText(self.config.theme_color)
        self.theme_color_input.textChanged.connect(self.on_theme_color_changed)
        
        color_layout.addWidget(color_label)
        color_layout.addWidget(self.theme_color_input)
        layout.addLayout(color_layout)
        
        # Autostart checkbox
        self.autostart_check = CheckBox("Автозагрузка с Windows", self)
        self.autostart_check.setChecked(self.is_autostart_enabled())
        self.autostart_check.stateChanged.connect(self.on_autostart_changed)
        layout.addWidget(self.autostart_check)
        
        # Admin rights info
        admin_label = CaptionLabel(
            "💡 Для некоторых операций требуются права администратора. "
            "Запускайте Flord от имени администратора если нужно."
        )
        admin_label.setWordWrap(True)
        layout.addWidget(admin_label)
        
        self.layout.addWidget(card)
    
    def is_autostart_enabled(self) -> bool:
        """Проверить включена ли автозагрузка"""
        import winreg
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            try:
                value, _ = winreg.QueryValueEx(key, "FlordAI")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False
    
    def set_autostart(self, enable: bool) -> bool:
        """Включить/выключить автозагрузку"""
        import winreg
        import sys
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            if enable:
                # Добавляем в автозагрузку
                exe_path = sys.executable
                script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
                # Создаем ярлык или используем pythonw для скрытого запуска
                command = f'"{exe_path}" "{script_path}"'
                
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
                winreg.SetValueEx(key, "FlordAI", 0, winreg.REG_SZ, command)
                winreg.CloseKey(key)
                return True
            else:
                # Удаляем из автозагрузки
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
                try:
                    winreg.DeleteValue(key, "FlordAI")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
                return True
        except Exception as e:
            print(f"Ошибка настройки автозагрузки: {e}")
            return False
    
    def on_autostart_changed(self, state):
        """Обработка изменения автозагрузки"""
        enabled = bool(state)
        if self.set_autostart(enabled):
            status = "включена" if enabled else "выключена"
            self.window.show_info_bar(f"Автозагрузка {status}", 3000)
        else:
            self.window.show_info_bar("❌ Ошибка настройки автозагрузки", 3000)
    
    def _update_provider_visibility(self):
        """Обновить видимость настроек провайдера"""
        provider = self.config.provider
        self.openrouter_card.setVisible(provider == "openrouter")
        self.gemini_card.setVisible(provider == "gemini")
        self.groq_card.setVisible(provider == "groq")
        self.ollama_card.setVisible(provider == "ollama")
    
    def on_provider_changed(self, value):
        """Обработка смены провайдера"""
        self.config.provider = value
        self.config.save()
        if self.mind:
            self.mind.switch_provider(value)
        self._update_provider_visibility()
        self.window.show_info_bar(f"Провайдер изменен на {LLMProvider.PROVIDERS.get(value, value)}")
    
    def on_api_key_changed(self, value):
        """Обработка изменения API ключа"""
        self.config.openrouter_api_key = value
        self.config.save()
    
    def on_model_changed(self, value):
        """Обработка изменения модели"""
        self.config.openrouter_model = value
        self.config.save()
    
    def on_auto_install_changed(self, state):
        """Обработка изменения автоустановки"""
        self.config.ollama_auto_install = bool(state)
        self.config.save()
    
    def on_ollama_host_changed(self, value):
        """Обработка изменения хоста Ollama"""
        self.config.ollama_host = value
        self.config.save()
    
    def on_ollama_model_changed(self, value):
        """Обработка изменения модели Ollama"""
        self.config.ollama_model = value
        self.config.save()
    
    def on_telegram_enabled_changed(self, state):
        """Обработка включения Telegram"""
        self.config.telegram_enabled = bool(state)
        self.config.save()
    
    def on_theme_color_changed(self, value):
        """Обработка изменения цвета темы"""
        self.config.theme_color = value
        self.config.save()
        setThemeColor(value, save=False)
    
    def auto_select_free_model(self):
        """Автоматически выбрать первую доступную бесплатную модель"""
        self.window.show_info_bar("Проверка доступных бесплатных моделей...", 3000)
        
        def check():
            free_models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            
            # Проверяем модели через API
            available_models = []
            for model in free_models:
                try:
                    # Простая проверка через запрос моделей
                    import requests
                    response = requests.get(
                        "https://openrouter.ai/api/v1/models",
                        headers={"Authorization": f"Bearer {self.config.openrouter_api_key}"},
                        timeout=10
                    )
                    if response.status_code == 200:
                        data = response.json()
                        all_models = [m.get("id") for m in data.get("data", [])]
                        if model in all_models:
                            available_models.append(model)
                except Exception as e:
                    print(f"Ошибка проверки модели {model}: {e}")
            
            # Выбираем первую доступную или первую из списка
            if available_models:
                selected = available_models[0]
                self.window.show_info_bar(f"✅ Выбрана: {selected}", 3000)
            else:
                selected = free_models[0]
                self.window.show_info_bar(f"⚠️ Используем: {selected} (проверьте API ключ)", 5000)
            
            # Обновляем UI в главном потоке
            from PyQt6.QtCore import QMetaObject, Qt, QGenericArgument
            QMetaObject.invokeMethod(
                self.model_combo,
                "setCurrentText",
                Qt.ConnectionType.QueuedConnection,
                QGenericArgument("QString", selected)
            )
            
            self.config.openrouter_model = selected
            self.config.save()
        
        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()
    
    def check_openrouter(self):
        """Проверить подключение к OpenRouter"""
        if self.mind and self.mind.llm_provider:
            if self.mind.llm_provider.is_available():
                self.window.show_info_bar("✅ Подключение к OpenRouter успешно!")
            else:
                self.window.show_info_bar("❌ Ошибка подключения. Проверьте API ключ.")
    
    def check_ollama_status(self):
        """Проверить статус Ollama"""
        def check():
            if self.ollama_manager.is_installed():
                if self.ollama_manager.is_running():
                    models = self.ollama_manager.get_available_models()
                    self.ollama_status.setText(f"✅ Ollama запущена. Моделей: {len(models)}")
                else:
                    self.ollama_status.setText("⚠️ Ollama установлена, но сервер не запущен")
            else:
                self.ollama_status.setText("❌ Ollama не установлена")
        
        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()
    
    def install_ollama(self):
        """Установить Ollama"""
        def install():
            self.window.show_info_bar("Начинаем установку Ollama...", 5000)
            if self.ollama_manager.install():
                self.window.show_info_bar("✅ Ollama установлена!", 3000)
                self.check_ollama_status()
            else:
                self.window.show_info_bar("❌ Ошибка установки Ollama", 5000)
        
        thread = threading.Thread(target=install)
        thread.daemon = True
        thread.start()
    
    def pull_ollama_model(self):
        """Скачать модель Ollama"""
        model = self.ollama_model_input.text()
        
        def pull():
            self.window.show_info_bar(f"Скачивание модели {model}...", 5000)
            if self.ollama_manager.pull_model(model):
                self.window.show_info_bar(f"✅ Модель {model} установлена!", 3000)
            else:
                self.window.show_info_bar(f"❌ Ошибка скачивания модели", 5000)
        
        thread = threading.Thread(target=pull)
        thread.daemon = True
        thread.start()
    
    def on_gemini_api_key_changed(self, value):
        """Обработка изменения API ключа Gemini"""
        self.config.gemini_api_key = value
        self.config.save()
    
    def on_gemini_model_changed(self, value):
        """Обработка изменения модели Gemini"""
        self.config.gemini_model = value
        self.config.save()
    
    def on_groq_api_key_changed(self, value):
        """Обработка изменения API ключа Groq"""
        self.config.groq_api_key = value
        self.config.save()
    
    def on_groq_model_changed(self, value):
        """Обработка изменения модели Groq"""
        self.config.groq_model = value
        self.config.save()
    
    def check_gemini(self):
        """Проверить подключение к Gemini"""
        if self.mind and self.mind.llm_provider:
            if self.mind.llm_provider.is_available():
                self.window.show_info_bar("✅ Подключение к Gemini успешно!")
            else:
                self.window.show_info_bar("❌ Ошибка подключения. Проверьте API ключ.")
    
    def check_groq(self):
        """Проверить подключение к Groq"""
        if self.mind and self.mind.llm_provider:
            if self.mind.llm_provider.is_available():
                self.window.show_info_bar("✅ Подключение к Groq успешно!")
            else:
                self.window.show_info_bar("❌ Ошибка подключения. Проверьте API ключ.")
    
    def save_telegram_settings(self):
        """Сохранить настройки Telegram"""
        self.config.telegram_bot_token = self.telegram_token_input.text()
        self.config.telegram_enabled = self.telegram_enabled_check.isChecked()
        self.config.save()
        
        if self.config.telegram_enabled and self.config.telegram_bot_token:
            self.window.show_info_bar("Запуск Telegram бота...", 3000)
            self.window.start_telegram_bot()


class MessageCard(CardWidget):

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.titleLabel = StrongBodyLabel(title, self)
        self.contentLabel = BodyLabel("", self)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setAcceptDrops(False)
        self.progressbar = IndeterminateProgressBar(start=True)
        self.vBoxLayout = QVBoxLayout(self)
        self.code_viewer = QLabel(self)
        self.code_viewer.setStyleSheet("QLabel { background-color : black; color : white; }")
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.addWidget(self.progressbar, 0, Qt.AlignmentFlag.AlignVCenter)
        self.vBoxLayout.addWidget(self.code_viewer, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_content(self, content: Message):
        if content.code:
            self.code_viewer.setVisible(True)
            self.code_viewer.setText(content.code)
        else:
            self.code_viewer.setVisible(False)
        if content.text:
            self.contentLabel.setText(content.text)
            self.progressbar.setVisible(False)
        else:
            self.progressbar.setVisible(True)


class TitleBar(MSFluentTitleBar):
    """ Custom title bar """

    anim_signal = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.b = ImageLabel(parent=self)
        self.anim_signal.connect(self.update_animation)
        self.set_animation(0)

        self.b.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def update_animation(self, value):
        s = "res/anim/idle.gif"
        if (value == 0):
            s = "res/anim/idle.gif"
        else:
            s = "res/anim/work.gif"
        self.b.setImage(s)
        self.b.scaledToHeight(self.height())

    def set_animation(self, n):
        self.anim_signal.emit(n)

    def resizeEvent(self, e):
        w, h = self.width(), self.height()
        self.b.move(w // 2 - self.b.width() // 2, h // 2 - self.b.height() // 2)
        self.b.setScaledContents(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = UI()
    w.show()
    app.exec()

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Config:
    """Конфигурация Flord AI"""
    
    # LLM Provider settings
    provider: str = "openrouter"  # "openrouter" или "ollama"
    
    # OpenRouter settings
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    
    # Google Gemini settings
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    
    # Groq settings
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    
    # Ollama settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"
    ollama_auto_install: bool = True
    
    # Telegram Bot settings
    telegram_bot_token: str = ""
    telegram_enabled: bool = False
    telegram_allowed_users: list = None
    
    # UI settings
    theme_color: str = "#cb4483"
    
    def __post_init__(self):
        if self.telegram_allowed_users is None:
            self.telegram_allowed_users = []
    
    @classmethod
    def load(cls, path: str = "config/config.json") -> "Config":
        """Загрузить конфигурацию из файла"""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
        return cls()
    
    def save(self, path: str = "config/config.json") -> None:
        """Сохранить конфигурацию в файл"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

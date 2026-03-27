from typing import List, Dict, Any, Iterator, Optional, Callable
import json
import requests
import subprocess
from openai import OpenAI
import ollama
from dataclasses import dataclass
import time


@dataclass
class StreamChunk:
    """Часть потокового ответа"""
    content: str
    is_finished: bool = False


class LLMProvider:
    """Унифицированный провайдер для OpenRouter, Gemini, Ollama и других бесплатных API"""
    
    # Доступные провайдеры
    PROVIDERS = {
        "openrouter": "OpenRouter (Free Models)",
        "gemini": "Google Gemini (Free API)",
        "groq": "Groq (Fast Free)",
        "ollama": "Ollama (Local)",
    }
    
    # Бесплатные модели по провайдерам
    FREE_MODELS = {
        "openrouter": [
            "google/gemma-3-4b-it:free",
            "google/gemma-3-12b-it:free",
            "meta-llama/llama-3.2-3b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "deepseek/deepseek-chat:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "qwen/qwen-2.5-7b-instruct:free",
            "nousresearch/hermes-3-405b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "huggingfaceh4/zephyr-7b-beta:free",
        ],
        "gemini": [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
        ],
        "groq": [
            "llama-3.1-8b-instant",
            "llama3-8b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it",
        ],
    }
    
    def __init__(self, provider_type: str = "openrouter", config: Dict = None):
        self.provider_type = provider_type
        self.config = config or {}
        self.client = None
        self._setup_client()
    
    def _setup_client(self):
        """Настроить клиент в зависимости от провайдера"""
        if self.provider_type == "openrouter":
            api_key = self.config.get("api_key", "")
            if api_key:
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/Jurom4ik/Flord",
                        "X-Title": "Flord AI"
                    }
                )
        elif self.provider_type == "gemini":
            # Gemini использует requests напрямую
            pass
        elif self.provider_type == "groq":
            api_key = self.config.get("api_key", "")
            if api_key:
                self.client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=api_key
                )
        elif self.provider_type == "ollama":
            pass
    
    def set_provider(self, provider_type: str, config: Dict = None):
        """Сменить провайдер"""
        self.provider_type = provider_type
        if config:
            self.config.update(config)
        self._setup_client()
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Получить список доступных моделей"""
        if self.provider_type == "openrouter":
            try:
                response = requests.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {self.config.get('api_key', '')}"},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
            except Exception as e:
                print(f"Ошибка получения моделей OpenRouter: {e}")
            return []
            
        elif self.provider_type == "gemini":
            return [{"id": m, "name": m} for m in self.FREE_MODELS["gemini"]]
            
        elif self.provider_type == "groq":
            return [{"id": m, "name": m} for m in self.FREE_MODELS["groq"]]
            
        elif self.provider_type == "ollama":
            try:
                host = self.config.get("host", "http://localhost:11434")
                response = requests.get(f"{host}/api/tags", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return [{"id": m.get("name"), "name": m.get("name")} for m in models]
            except Exception as e:
                print(f"Ошибка получения моделей Ollama: {e}")
            return []
        
        return []
    
    def get_free_models(self, provider: str = None) -> List[str]:
        """Получить список бесплатных моделей для провайдера"""
        provider = provider or self.provider_type
        return self.FREE_MODELS.get(provider, [])
    
    def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        model: str = None,
        on_chunk: Callable[[str], None] = None
    ) -> str:
        """Потоковый чат с LLM"""
        
        if self.provider_type == "openrouter":
            return self._chat_openrouter(messages, model, on_chunk)
        elif self.provider_type == "gemini":
            return self._chat_gemini(messages, model, on_chunk)
        elif self.provider_type == "groq":
            return self._chat_groq(messages, model, on_chunk)
        elif self.provider_type == "ollama":
            return self._chat_ollama(messages, model, on_chunk)
        else:
            raise ValueError(f"Неизвестный провайдер: {self.provider_type}")
    
    def _chat_openrouter(
        self, 
        messages: List[Dict[str, str]], 
        model: str = None,
        on_chunk: Callable[[str], None] = None
    ) -> str:
        """Чат через OpenRouter"""
        if not self.client:
            error_msg = "❌ OpenRouter клиент не настроен. Введите API ключ в настройках."
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
        
        api_key = self.config.get('api_key', '')
        if not api_key or api_key.strip() == '':
            error_msg = "❌ API ключ OpenRouter пустой. Получите ключ на https://openrouter.ai/keys"
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
        
        model = model or self.config.get("model", "meta-llama/llama-3.2-3b-instruct:free")
        
        print(f"🤖 Отправка запроса к OpenRouter, модель: {model}")
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                extra_headers={
                    "HTTP-Referer": "https://github.com/Jurom4ik/Flord",
                    "X-Title": "Flord AI",
                }
            )
            
            full_response = ""
            chunk_count = 0
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                chunk_count += 1
                if on_chunk:
                    on_chunk(full_response)
            
            print(f"✅ Ответ получен ({chunk_count} чанков, {len(full_response)} символов)")
            
            if not full_response.strip():
                return "⚠️ Модель вернула пустой ответ. Попробуйте другую модель или проверьте API ключ."
            
            return full_response
            
        except Exception as e:
            error_str = str(e)
            if "401" in error_str:
                error_msg = f"❌ Ошибка авторизации OpenRouter (401): Неверный API ключ или ключ не активирован"
            elif "402" in error_str:
                error_msg = f"❌ Ошибка оплаты OpenRouter (402): Недостаточно средств или модель не доступна для free-tier"
            elif "429" in error_str:
                error_msg = f"❌ Слишком много запросов (429): Лимит запросов превышен"
            elif "404" in error_str:
                error_msg = f"❌ Модель не найдена (404): {model}"
            else:
                error_msg = f"❌ Ошибка OpenRouter: {e}"
            
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
    
    def _chat_ollama(
        self, 
        messages: List[Dict[str, str]], 
        model: str = None,
        on_chunk: Callable[[str], None] = None
    ) -> str:
        """Чат через Ollama"""
        model = model or self.config.get("model", "llama3.2:latest")
        host = self.config.get("host", "http://localhost:11434")
        
        try:
            client = ollama.Client(host=host)
            
            # Форматируем сообщения для Ollama
            formatted_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                formatted_messages.append({"role": role, "content": content})
            
            full_response = ""
            for chunk in client.chat(
                model=model,
                messages=formatted_messages,
                stream=True
            ):
                content = chunk.get("message", {}).get("content", "")
                full_response += content
                if on_chunk:
                    on_chunk(full_response)
            
            return full_response
            
        except Exception as e:
            error_msg = f"Ошибка Ollama: {e}"
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
    
    def _chat_gemini(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        on_chunk: Callable[[str], None] = None
    ) -> str:
        """Чат через Google Gemini API (бесплатный)"""
        api_key = self.config.get("api_key", "")
        if not api_key:
            error_msg = "❌ API ключ Gemini не настроен. Получите ключ на https://makersuite.google.com/app/apikey"
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
        
        model = model or "gemini-1.5-flash"
        
        # Форматируем сообщения для Gemini
        gemini_messages = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        data = {"contents": gemini_messages}
        
        try:
            response = requests.post(url, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0].get("content", {})
                    text = content.get("parts", [{}])[0].get("text", "")
                    if on_chunk:
                        on_chunk(text)
                    return text
                else:
                    error_msg = "⚠️ Gemini вернул пустой ответ"
                    if on_chunk:
                        on_chunk(error_msg)
                    return error_msg
            else:
                error_msg = f"❌ Ошибка Gemini ({response.status_code}): {response.text}"
                print(error_msg)
                if on_chunk:
                    on_chunk(error_msg)
                return error_msg
        except Exception as e:
            error_msg = f"❌ Ошибка Gemini: {e}"
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
    
    def _chat_groq(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        on_chunk: Callable[[str], None] = None
    ) -> str:
        """Чат через Groq API (быстрый бесплатный)"""
        if not self.client:
            error_msg = "❌ Groq клиент не настроен. Получите ключ на https://console.groq.com/keys"
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
        
        model = model or "llama-3.1-8b-instant"
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True
            )
            
            full_response = ""
            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                if on_chunk:
                    on_chunk(full_response)
            
            return full_response
            
        except Exception as e:
            error_str = str(e)
            if "401" in error_str:
                error_msg = "❌ Неверный API ключ Groq"
            elif "429" in error_str:
                error_msg = "❌ Превышен лимит запросов Groq (попробуйте позже)"
            else:
                error_msg = f"❌ Ошибка Groq: {e}"
            
            print(error_msg)
            if on_chunk:
                on_chunk(error_msg)
            return error_msg
    
    def is_available(self) -> bool:
        """Проверить доступность провайдера"""
        if self.provider_type == "openrouter":
            return self.client is not None and bool(self.config.get("api_key"))
        elif self.provider_type == "gemini":
            return bool(self.config.get("api_key"))
        elif self.provider_type == "groq":
            return self.client is not None and bool(self.config.get("api_key"))
        elif self.provider_type == "ollama":
            try:
                host = self.config.get("host", "http://localhost:11434")
                response = requests.get(f"{host}/api/tags", timeout=2)
                return response.status_code == 200
            except:
                return False
        return False

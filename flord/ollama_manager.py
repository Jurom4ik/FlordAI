import os
import subprocess
import platform
import requests
import time
from typing import List, Optional, Dict, Any
import json


class OllamaManager:
    """Менеджер для установки и управления Ollama"""
    
    DEFAULT_HOST = "http://localhost:11434"
    
    def __init__(self, host: str = DEFAULT_HOST):
        self.host = host
        self.system = platform.system()
        
    def is_installed(self) -> bool:
        """Проверить, установлен ли Ollama"""
        try:
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def is_running(self) -> bool:
        """Проверить, запущен ли сервер Ollama"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def install(self) -> bool:
        """Автоматическая установка Ollama"""
        print("Начинаем установку Ollama...")
        
        try:
            if self.system == "Windows":
                # Скачиваем установщик
                url = "https://ollama.com/download/OllamaSetup.exe"
                installer_path = os.path.join(os.environ.get("TEMP", "."), "OllamaSetup.exe")
                
                print(f"Скачивание Ollama для Windows...")
                response = requests.get(url, stream=True)
                with open(installer_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print("Запуск установщика...")
                subprocess.Popen([installer_path, "/S"], shell=True)
                
                # Ждем завершения установки
                for i in range(60):
                    if self.is_installed():
                        print("Ollama успешно установлен!")
                        return True
                    time.sleep(1)
                
            elif self.system == "Linux":
                # Установка через curl
                cmd = 'curl -fsSL https://ollama.com/install.sh | sh'
                subprocess.run(cmd, shell=True, check=True)
                return self.is_installed()
                
            elif self.system == "Darwin":  # macOS
                # Проверяем Homebrew
                try:
                    subprocess.run(["brew", "--version"], capture_output=True, check=True)
                    subprocess.run(["brew", "install", "ollama"], check=True)
                    return self.is_installed()
                except:
                    # Скачиваем установщик для macOS
                    url = "https://ollama.com/download/Ollama-darwin.zip"
                    print(f"Скачивание Ollama для macOS...")
                    # TODO: Реализовать установку для macOS
                    pass
                    
        except Exception as e:
            print(f"Ошибка установки Ollama: {e}")
            
        return False
    
    def start_server(self) -> bool:
        """Запустить сервер Ollama"""
        if not self.is_installed():
            print("Ollama не установлен. Установите сначала.")
            return False
            
        if self.is_running():
            print("Сервер Ollama уже запущен")
            return True
            
        try:
            print("Запуск сервера Ollama...")
            if self.system == "Windows":
                # Запускаем ollama serve в фоне
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            # Ждем запуска сервера
            for i in range(30):
                if self.is_running():
                    print("Сервер Ollama запущен!")
                    return True
                time.sleep(1)
                
        except Exception as e:
            print(f"Ошибка запуска сервера: {e}")
            
        return False
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Получить список доступных моделей"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            print(f"Ошибка получения списка моделей: {e}")
        return []
    
    def pull_model(self, model_name: str, callback=None) -> bool:
        """Скачать модель"""
        print(f"Скачивание модели {model_name}...")
        
        try:
            response = requests.post(
                f"{self.host}/api/pull",
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=300
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if callback:
                        callback(data)
                    if "completed" in data and data["completed"]:
                        print(f"Модель {model_name} успешно скачана!")
                        return True
                        
        except Exception as e:
            print(f"Ошибка скачивания модели: {e}")
            
        return False
    
    def delete_model(self, model_name: str) -> bool:
        """Удалить модель"""
        try:
            response = requests.delete(
                f"{self.host}/api/delete",
                json={"name": model_name},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Ошибка удаления модели: {e}")
        return False
    
    def ensure_model(self, model_name: str) -> bool:
        """Убедиться что модель установлена, если нет - скачать"""
        models = self.get_available_models()
        model_names = [m.get("name") for m in models]
        
        if model_name in model_names:
            return True
            
        print(f"Модель {model_name} не найдена. Начинаю скачивание...")
        return self.pull_model(model_name)
    
    def get_popular_models(self) -> List[str]:
        """Получить список популярных моделей"""
        return [
            "llama3.2:latest",
            "llama3.2:3b",
            "llama3.1:8b",
            "phi4:latest",
            "qwen2.5:latest",
            "mistral:latest",
            "codellama:latest",
            "deepseek-coder:latest",
        ]

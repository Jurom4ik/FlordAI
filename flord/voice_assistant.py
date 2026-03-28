"""
Flord AI - Голосовой ассистент
Голосовой ввод и вывод для Flord AI
"""
import threading
import time
import queue
from typing import Optional, Callable
import speech_recognition as sr
from gtts import gTTS
import pygame
import tempfile
import os


class VoiceAssistant:
    """Голосовой ассистент для Flord AI"""
    
    def __init__(self, mind=None):
        self.mind = mind
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        self.listening_thread = None
        self.on_voice_input: Optional[Callable] = None
        self.on_voice_output: Optional[Callable] = None
        
        # Настройки микрофона
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        
        # Инициализация pygame для аудио
        pygame.mixer.init()
    
    def start_listening(self):
        """Начать прослушивание голоса"""
        if self.is_listening:
            return
        
        self.is_listening = True
        self.listening_thread = threading.Thread(target=self._listen_loop)
        self.listening_thread.daemon = True
        self.listening_thread.start()
        print("🎤 Голосовой ассистент активирован")
    
    def stop_listening(self):
        """Остановить прослушивание голоса"""
        self.is_listening = False
        if self.listening_thread:
            self.listening_thread.join(timeout=1)
        print("🔇 Голосовой ассистент деактивирован")
    
    def _listen_loop(self):
        """Цикл прослушивания голоса"""
        while self.is_listening:
            try:
                with self.microphone as source:
                    print("Говорите...")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Распознаем речь
                text = self.recognizer.recognize_google(audio, language="ru-RU")
                print(f"Вы сказали: {text}")
                
                # Вызываем callback
                if self.on_voice_input:
                    self.on_voice_input(text)
                
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                print("Не удалось распознать речь")
                continue
            except sr.RequestError as e:
                print(f"Ошибка сервиса распознавания: {e}")
                time.sleep(5)
                continue
    
    def speak(self, text: str):
        """Озвучить текст"""
        if not text:
            return
        
        try:
            # Создаем голосовое сообщение
            tts = gTTS(text=text, lang='ru', slow=False)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                temp_file = f.name
                tts.write_to_fp(f)
            
            # Воспроизводим аудио
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            # Ждем окончания воспроизведения
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Удаляем временный файл
            os.unlink(temp_file)
            
            if self.on_voice_output:
                self.on_voice_output(text)
                
        except Exception as e:
            print(f"Ошибка озвучивания: {e}")
    
    def process_voice_command(self, command: str):
        """Обработать голосовую команду"""
        if not self.mind:
            return
        
        # Отправляем команду в Mind
        def on_response(message):
            self.speak(message.text)
        
        self.mind.on_response_update = on_response
        self.mind.get_ai_response(command)


class VoiceChatWidget:
    """Виджет голосового чата"""
    
    def __init__(self, parent=None, voice_assistant=None):
        self.parent = parent
        self.voice_assistant = voice_assistant
        self.is_active = False
    
    def toggle_voice_mode(self):
        """Включить/выключить голосовой режим"""
        if self.is_active:
            self.stop_voice_mode()
        else:
            self.start_voice_mode()
    
    def start_voice_mode(self):
        """Активировать голосовой режим"""
        if self.voice_assistant:
            self.voice_assistant.start_listening()
            self.is_active = True
            print("🔊 Голосовой режим активирован")
    
    def stop_voice_mode(self):
        """Деактивировать голосовой режим"""
        if self.voice_assistant:
            self.voice_assistant.stop_listening()
            self.is_active = False
            print("🔇 Голосовой режим деактивирован")
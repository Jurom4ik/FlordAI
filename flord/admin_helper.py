"""
Управление правами администратора - с реальным UAC запросом перед выполнением кода
"""
import ctypes
import sys
import os
import subprocess
import tempfile
import io
import traceback
from typing import Callable, Optional
import win32con
import win32gui


def is_admin() -> bool:
    """Проверить есть ли права администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def execute_code_direct(code: str) -> tuple[bool, str, str]:
    """Выполнить код напрямую (уже с правами админа)"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    
    try:
        local_vars = {}
        exec(code, {}, local_vars)
        
        if 'answer' in local_vars:
            result = local_vars['answer']()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            return True, str(result), ""
        else:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            return False, "", "Функция answer не найдена"
            
    except Exception as e:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return False, "", error_msg
    
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def _check_requires_admin(code: str) -> bool:
    """Проверить требует ли код прав администратора"""
    requires_admin_keywords = [
        'os.system', 'subprocess', 'ctypes.windll',
        'win32api', 'win32con', 'win32gui',
        'pycaw', 'comtypes',
        'HKEY_', 'registry', 'reg ',
        'sc ', 'sc.exe',
        'net ', 'net.exe',
        'taskkill ', 'taskkill.exe',
        'schtasks', 'format ', 'diskpart',
        'takeown', 'icacls',
        'windows', 'program files',
    ]
    
    code_lower = code.lower()
    for kw in requires_admin_keywords:
        if kw.lower() in code_lower:
            return True
    return False


def execute_with_uac(code: str, timeout: int = 60) -> tuple[bool, str]:
    """
    Выполнить код с правами администратора через UAC
    Создает временный скрипт и запускает его через ShellExecute с runas
    
    Returns: (success, result_or_error)
    """
    # Создаем временный файл с кодом
    temp_dir = tempfile.gettempdir()
    temp_script = os.path.join(temp_dir, f'flord_admin_{os.getpid()}.py')
    result_file = temp_script + '.result'
    
    # Готовим код для выполнения
    script_content = f'''# -*- coding: utf-8 -*-
import sys
import io
import os

# Перехват stdout/stderr
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

try:
{chr(10).join("    " + line for line in code.split(chr(10)))}
    
    # Вызываем функцию answer если существует
    if 'answer' in locals():
        result = answer()
        output = sys.stdout.getvalue()
        error = sys.stderr.getvalue()
        
        with open(r'{result_file}', 'w', encoding='utf-8') as f:
            f.write(f"SUCCESS|{{result}}|{{output}}|{{error}}")
    else:
        output = sys.stdout.getvalue()
        error = sys.stderr.getvalue()
        with open(r'{result_file}', 'w', encoding='utf-8') as f:
            f.write(f"SUCCESS|Функция answer не найдена|{{output}}|{{error}}")
            
except Exception as e:
    import traceback
    error_msg = f"{{str(e)}}\\n{{traceback.format_exc()}}"
    with open(r'{result_file}', 'w', encoding='utf-8') as f:
        f.write(f"ERROR|{{error_msg}}||")
'''
    
    # Записываем скрипт
    with open(temp_script, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    try:
        # Запускаем через UAC (runas)
        # ShellExecuteW возвращает значение >32 при успехе
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,  # hwnd
            "runas",  # операция - запрос прав администратора
            sys.executable,  # программа
            f'"{temp_script}"',  # параметры
            None,  # директория
            0  # SW_HIDE - скрытое окно
        )
        
        if ret <= 32:
            # Ошибка ShellExecute
            error_codes = {
                0: "Ошибка памяти",
                2: "Файл не найден",
                3: "Путь не найден",
                5: "Доступ запрещен (отменено UAC?)",
                8: "Недостаточно памяти",
                32: "DLL не найдена",
            }
            error_msg = error_codes.get(ret, f"Ошибка ShellExecute: {ret}")
            return False, f"Не удалось запустить с правами администратора: {error_msg}"
        
        # Ждем результат
        import time
        for i in range(timeout * 10):  # Ждем до timeout секунд
            time.sleep(0.1)
            if os.path.exists(result_file):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    parts = content.split('|', 3)
                    if len(parts) >= 2:
                        status = parts[0]
                        result = parts[1]
                        stdout = parts[2] if len(parts) > 2 else ""
                        stderr = parts[3] if len(parts) > 3 else ""
                        
                        if status == "SUCCESS":
                            return True, result
                        else:
                            return False, f"Ошибка выполнения: {result}"
                    else:
                        return False, "Некорректный формат результата"
                        
                except Exception as e:
                    return False, f"Ошибка чтения результата: {e}"
                finally:
                    # Очистка
                    for f in [temp_script, result_file]:
                        try:
                            if os.path.exists(f):
                                os.unlink(f)
                        except:
                            pass
        
        # Таймаут
        return False, "Таймаут ожидания выполнения с правами администратора"
        
    except Exception as e:
        return False, f"Исключение при запуске с UAC: {str(e)}"
    finally:
        # Очистка
        for f in [temp_script, result_file]:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except:
                pass


def ensure_admin_and_execute(code: str) -> str:
    """
    Главная функция: проверяет нужны ли права, запрашивает UAC если нужно, выполняет код
    Возвращает строку с результатом или ошибкой
    """
    # Проверяем нужны ли права
    needs_admin = _check_requires_admin(code)
    
    if not needs_admin:
        # Права не нужны - выполняем напрямую
        success, output, error = execute_code_direct(code)
        if success:
            return output
        else:
            return f"Ошибка: {error}"
    
    # Нужны права
    if is_admin():
        # Уже с правами
        success, output, error = execute_code_direct(code)
        if success:
            return output
        else:
            return f"Ошибка выполнения: {error}"
    else:
        # Запрашиваем права через UAC и выполняем
        success, result = execute_with_uac(code)
        if success:
            return result
        else:
            return f"⚠️ {result}"

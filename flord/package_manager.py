"""
Менеджер пакетов Python для автоматической установки
"""
import subprocess
import sys
import os
import importlib
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class PackageManager:
    """Автоматическая установка Python пакетов"""
    
    def __init__(self):
        self.python_exe = sys.executable
        self.pip_cmd = self._find_pip()
    
    def _find_pip(self) -> str:
        """Найти pip (в PATH или рядом с python)"""
        # Пробуем найти pip в том же каталоге что и python
        python_dir = os.path.dirname(self.python_exe)
        
        possible_pips = [
            os.path.join(python_dir, "pip.exe"),
            os.path.join(python_dir, "Scripts", "pip.exe"),
            os.path.join(python_dir, "pip"),
            os.path.join(python_dir, "Scripts", "pip"),
            "pip",  # Если в PATH
            "pip3",
        ]
        
        for pip in possible_pips:
            if pip in ["pip", "pip3"] or os.path.exists(pip):
                try:
                    result = subprocess.run(
                        [pip, "--version"],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return pip
                except:
                    continue
        
        # Если не нашли, используем модуль pip
        return f"{self.python_exe} -m pip"
    
    def is_installed(self, package_name: str) -> bool:
        """Проверить установлен ли пакет"""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False
    
    def install(self, package_name: str, timeout: int = 120) -> bool:
        """Установить пакет"""
        logger.info(f"Установка пакета: {package_name}")
        
        try:
            # Нормализуем имя пакета (убираем версии, extras)
            clean_name = package_name.split("[")[0].split("=")[0].split("<")[0].split(">")[0].strip()
            
            if self.pip_cmd.endswith("pip") or self.pip_cmd in ["pip", "pip3"]:
                # Используем pip напрямую
                cmd = [self.pip_cmd, "install", "-U", clean_name]
            else:
                # Используем python -m pip
                cmd = self.pip_cmd.split() + ["install", "-U", clean_name]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {package_name} установлен успешно")
                return True
            else:
                logger.error(f"❌ Ошибка установки {package_name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱ Таймаут при установке {package_name}")
            return False
        except Exception as e:
            logger.error(f"❌ Исключение при установке {package_name}: {e}")
            return False
    
    def ensure_installed(self, package_name: str) -> bool:
        """Убедиться что пакет установлен"""
        if self.is_installed(package_name):
            return True
        return self.install(package_name)
    
    def extract_imports(self, code: str) -> List[str]:
        """Извлечь импорты из кода"""
        imports = []
        lines = code.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('import '):
                # import xxx или import xxx.yyy
                parts = line.replace('import ', '').split(',')
                for part in parts:
                    module = part.strip().split('.')[0].split(' as ')[0].strip()
                    if module and module not in ['os', 'sys', 'json', 're', 'time', 'datetime']:
                        imports.append(module)
                        
            elif line.startswith('from '):
                # from xxx import yyy
                parts = line.split(' import ')
                if len(parts) == 2:
                    module = parts[0].replace('from ', '').split('.')[0].strip()
                    if module and module not in ['os', 'sys', 'json', 're', 'time', 'datetime']:
                        imports.append(module)
        
        # Уникальные имена пакетов
        unique_imports = list(set(imports))
        
        # Маппинг имён импортов на имена пакетов
        package_mapping = {
            'PIL': 'Pillow',
            'sklearn': 'scikit-learn',
            'cv2': 'opencv-python',
            'bs4': 'beautifulsoup4',
            'yaml': 'PyYAML',
            'git': 'GitPython',
            'dotenv': 'python-dotenv',
            'requests': 'requests',
            'psutil': 'psutil',
            'pyautogui': 'pyautogui',
            'win32api': 'pywin32',
            'win32con': 'pywin32',
            'comtypes': 'comtypes',
            'pycaw': 'pycaw',
        }
        
        result = []
        for imp in unique_imports:
            if imp in package_mapping:
                result.append(package_mapping[imp])
            else:
                result.append(imp)
        
        return result
    
    def install_for_code(self, code: str) -> List[str]:
        """Установить все пакеты необходимые для кода"""
        packages = self.extract_imports(code)
        installed = []
        failed = []
        
        for package in packages:
            if self.ensure_installed(package):
                installed.append(package)
            else:
                failed.append(package)
        
        return installed, failed


# Глобальный экземпляр
package_manager = PackageManager()

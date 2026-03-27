"""
Build script for Flord AI
Creates standalone executable with PyInstaller
"""
import os
import sys
import subprocess
import shutil


def build():
    """Build standalone executable"""
    print("🔨 Building Flord AI...")
    
    # Проверяем наличие pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Создаем spec файл или используем команду
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=FlordAI",
        "--onefile",
        "--windowed",
        "--icon=res/icon.ico" if os.path.exists("res/icon.ico") else "",
        "--add-data=res;res",
        "--hidden-import=PyQt6",
        "--hidden-import=qfluentwidgets",
        "--hidden-import=aiogram",
        "--hidden-import=openai",
        "--hidden-import=ollama",
        "--hidden-import=psutil",
        "--hidden-import=pyautogui",
        "--hidden-import=pycaw",
        "--hidden-import=comtypes",
        "--hidden-import=win32api",
        "--hidden-import=win32con",
        "--hidden-import=win32gui",
        "--hidden-import=requests",
        "--hidden-import=python-docx",
        "--clean",
        "flord/main.py"
    ]
    
    # Убираем пустые строки
    cmd = [c for c in cmd if c]
    
    print("🚀 Running PyInstaller...")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("✅ Build successful!")
        print(f"📁 Executable location: dist/FlordAI.exe")
        
        # Копируем дополнительные файлы
        if os.path.exists("dist/FlordAI.exe"):
            # Создаем папку для релиза
            release_dir = "release"
            if os.path.exists(release_dir):
                shutil.rmtree(release_dir)
            os.makedirs(release_dir)
            
            # Копируем exe
            shutil.copy("dist/FlordAI.exe", release_dir)
            
            # Копируем res
            if os.path.exists("res"):
                shutil.copytree("res", os.path.join(release_dir, "res"))
            
            print(f"📦 Release package created in '{release_dir}/'")
    else:
        print("❌ Build failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(build())

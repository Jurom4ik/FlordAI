"""
Build script for Flord AI v2.0.0
Creates standalone executable with PyInstaller
"""
import os
import sys
import subprocess
import shutil


def build():
    """Build standalone executable for Windows"""
    print("🔨 Building Flord AI v2.0.0...")
    print("=" * 50)
    
    # Проверяем наличие pyinstaller
    try:
        import PyInstaller
        print("✅ PyInstaller found")
    except ImportError:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Очищаем старые билды
    if os.path.exists("build"):
        print("🧹 Cleaning build directory...")
        shutil.rmtree("build")
    if os.path.exists("dist"):
        print("🧹 Cleaning dist directory...")
        shutil.rmtree("dist")
    
    # Настройка иконки
    icon_path = "res/icon.ico" if os.path.exists("res/icon.ico") else ""
    if icon_path:
        print(f"🎨 Using icon: {icon_path}")
    else:
        print("⚠️  No icon found, using default")
    
    # Команда для PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=FlordAI",
        "--onefile",
        "--windowed",
        "--uac-admin",  # Запрос прав администратора
        "--icon=" + icon_path if icon_path else "",
        "--add-data=res;res",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.sip",
        "--hidden-import=qfluentwidgets",
        "--hidden-import=qfluentwidgets.components",
        "--hidden-import=aiogram",
        "--hidden-import=aiogram.types",
        "--hidden-import=openai",
        "--hidden-import=ollama",
        "--hidden-import=psutil",
        "--hidden-import=pyautogui",
        "--hidden-import=pycaw",
        "--hidden-import=pycaw.utils",
        "--hidden-import=comtypes",
        "--hidden-import=win32api",
        "--hidden-import=win32con",
        "--hidden-import=win32gui",
        "--hidden-import=win32process",
        "--hidden-import=win32event",
        "--hidden-import=win32security",
        "--hidden-import=requests",
        "--hidden-import=docx",
        "--hidden-import=ctypes",
        "--hidden-import=ctypes.wintypes",
        "--collect-all=qfluentwidgets",
        "--clean",
        "--noconfirm",
        "flord/main.py"
    ]
    
    # Убираем пустые строки
    cmd = [c for c in cmd if c]
    
    print("\n🚀 Running PyInstaller...")
    print("-" * 50)
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("✅ Build successful!")
        print(f"📁 Executable location: dist/FlordAI.exe")
        
        # Создаем папку для релиза
        release_dir = "release"
        if os.path.exists(release_dir):
            print(f"🧹 Cleaning old release directory...")
            shutil.rmtree(release_dir)
        
        os.makedirs(release_dir)
        print(f"📦 Creating release package...")
        
        # Копируем exe
        if os.path.exists("dist/FlordAI.exe"):
            shutil.copy("dist/FlordAI.exe", release_dir)
            print(f"   ✓ Copied FlordAI.exe")
        
        # Копируем res
        if os.path.exists("res"):
            shutil.copytree("res", os.path.join(release_dir, "res"))
            print(f"   ✓ Copied resources")
        
        # Копируем README
        if os.path.exists("README.md"):
            shutil.copy("README.md", release_dir)
            print(f"   ✓ Copied README.md")
        
        print(f"\n🎉 Release package created in '{release_dir}/'")
        print(f"📦 Ready to distribute!")
        print("=" * 50)
    else:
        print("\n❌ Build failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(build())

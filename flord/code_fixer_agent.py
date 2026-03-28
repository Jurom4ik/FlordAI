"""
Flord AI - Code Fixer Agent
Автоматический агент для исправления ошибок в коде
"""
import os
import re
import ast
import sys
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class CodeFixerAgent:
    """Агент для автоматического исправления ошибок в коде"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path)
        self.errors_found = []
        self.fixes_applied = []
        
    def scan_for_errors(self) -> List[Dict]:
        """Сканировать все Python файлы на ошибки"""
        errors = []
        
        for py_file in self.project_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            file_errors = self._check_file(py_file)
            errors.extend(file_errors)
            
        self.errors_found = errors
        return errors
    
    def _check_file(self, file_path: Path) -> List[Dict]:
        """Проверить один файл на ошибки"""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Проверка синтаксиса
            try:
                ast.parse(content)
            except SyntaxError as e:
                errors.append({
                    'file': file_path,
                    'line': e.lineno,
                    'type': 'syntax_error',
                    'message': str(e),
                    'auto_fixable': False
                })
                return errors
            
            # Проверка импортов
            import_errors = self._check_imports(file_path, content)
            errors.extend(import_errors)
            
            # Проверка распространенных ошибок
            common_errors = self._check_common_patterns(file_path, content)
            errors.extend(common_errors)
            
        except Exception as e:
            errors.append({
                'file': file_path,
                'line': 0,
                'type': 'read_error',
                'message': str(e),
                'auto_fixable': False
            })
            
        return errors
    
    def _check_imports(self, file_path: Path, content: str) -> List[Dict]:
        """Проверить импорты на ошибки"""
        errors = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Проверка относительных импортов внутри пакета flord
            if re.match(r'^from (config|mind|telegram_bot|ollama_manager|llm_provider|admin_helper|package_manager|execute) import', line):
                errors.append({
                    'file': file_path,
                    'line': i,
                    'type': 'relative_import',
                    'message': f"Относительный импорт: {line.strip()}",
                    'original': line,
                    'fix': line.replace('from ', 'from flord.'),
                    'auto_fixable': True
                })
                
        return errors
    
    def _check_common_patterns(self, file_path: Path, content: str) -> List[Dict]:
        """Проверить распространенные ошибки паттерны"""
        errors = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Проверка на Flord
            if 'flord' in line.lower() or 'Flord' in line:
                errors.append({
                    'file': file_path,
                    'line': i,
                    'type': 'old_name',
                    'message': f"Найдено упоминание Flord: {line.strip()}",
                    'original': line,
                    'fix': line.replace('flord', 'flord').replace('Flord', 'Flord'),
                    'auto_fixable': True
                })
                
        return errors
    
    def fix_errors(self, errors: List[Dict] = None) -> List[Dict]:
        """Исправить найденные ошибки"""
        if errors is None:
            errors = self.errors_found
            
        fixed = []
        
        for error in errors:
            if error.get('auto_fixable') and 'fix' in error:
                try:
                    self._apply_fix(error)
                    fixed.append(error)
                except Exception as e:
                    print(f"❌ Не удалось исправить {error['file']}:{error['line']}: {e}")
                    
        self.fixes_applied = fixed
        return fixed
    
    def _apply_fix(self, error: Dict):
        """Применить исправление к файлу"""
        file_path = error['file']
        line_num = error['line']
        fix = error['fix']
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if 1 <= line_num <= len(lines):
            original = lines[line_num - 1]
            lines[line_num - 1] = fix + '\n' if not fix.endswith('\n') else fix
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            print(f"✅ Исправлено {file_path}:{line_num}")
            print(f"   Было: {original.strip()}")
            print(f"   Стало: {fix.strip()}")
        
    def run_auto_fix(self):
        """Запустить автоматическое исправление"""
        print("🔍 Сканирование проекта на ошибки...")
        errors = self.scan_for_errors()
        
        if not errors:
            print("✅ Ошибок не найдено!")
            return
            
        auto_fixable = [e for e in errors if e.get('auto_fixable')]
        manual_fix = [e for e in errors if not e.get('auto_fixable')]
        
        print(f"\n📊 Найдено ошибок: {len(errors)}")
        print(f"   Автоисправление: {len(auto_fixable)}")
        print(f"   Ручное исправление: {len(manual_fix)}")
        
        if auto_fixable:
            print(f"\n🔧 Автоматическое исправление...")
            self.fix_errors(auto_fixable)
            
        if manual_fix:
            print(f"\n⚠️ Требуют ручного исправления:")
            for e in manual_fix:
                print(f"   {e['file']}:{e['line']} - {e['message']}")
                
        print("\n✅ Готово!")


if __name__ == "__main__":
    # Запуск агента
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agent = CodeFixerAgent(project_path)
    agent.run_auto_fix()

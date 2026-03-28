"""
Система подтверждения действий ИИ
Предотвращает случайное выполнение опасных команд
"""
import logging
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DangerLevel(Enum):
    """Уровни опасности действий"""
    SAFE = "safe"           # Безопасно
    CAUTION = "caution"     # Внимание
    WARNING = "warning"     # Предупреждение
    DANGER = "danger"       # Опасно
    CRITICAL = "critical"   # Критично


@dataclass
class ActionConfirmation:
    """Запрос на подтверждение действия"""
    action_id: str
    description: str
    danger_level: DangerLevel
    callback: Callable
    cancel_callback: Optional[Callable] = None


class ConfirmationSystem:
    """Система подтверждения опасных действий"""
    
    def __init__(self):
        self.pending_confirmations = {}
        self.confirmation_callback = None
        self.counter = 0
    
    def set_confirmation_callback(self, callback: Callable):
        """Установить callback для показа диалога подтверждения"""
        self.confirmation_callback = callback
    
    def analyze_action(self, code: str) -> tuple[DangerLevel, str]:
        """Анализировать код на опасность"""
        code_lower = code.lower()
        
        # Критичные действия
        critical_keywords = [
            'shutdown', 'restart', 'reboot', 'format', 'удалить', 'format',
            'system32', 'windows', 'boot', 'registry'
        ]
        for keyword in critical_keywords:
            if keyword in code_lower:
                return DangerLevel.CRITICAL, f"⚠️ КРИТИЧНО: Обнаружена системная команда '{keyword}'"
        
        # Опасные действия
        danger_keywords = [
            'del ', 'delete', 'remove', 'rmdir', 'rm -rf', 'удалить',
            'format', 'wipe', 'очистить', 'destroy'
        ]
        for keyword in danger_keywords:
            if keyword in code_lower:
                return DangerLevel.DANGER, f"⚠️ ОПАСНО: Обнаружена команда удаления '{keyword}'"
        
        # Предупреждения
        warning_keywords = [
            'taskkill', 'kill', 'stop', 'terminate', 'закрыть', 'остановить',
            'block', 'блокировать', 'disable', 'отключить'
        ]
        for keyword in warning_keywords:
            if keyword in code_lower:
                return DangerLevel.WARNING, f"⚠️ ВНИМАНИЕ: Обнаружена команда остановки '{keyword}'"
        
        # Внимание
        caution_keywords = [
            'copy', 'move', 'rename', 'write', 'save', 'download', 'install'
        ]
        for keyword in caution_keywords:
            if keyword in code_lower:
                return DangerLevel.CAUTION, f"ℹ️ Обнаружена команда изменения '{keyword}'"
        
        return DangerLevel.SAFE, "✅ Действие безопасно"
    
    def request_confirmation(self, action_id: str, description: str, 
                           danger_level: DangerLevel, 
                           callback: Callable,
                           cancel_callback: Optional[Callable] = None) -> bool:
        """Запросить подтверждение действия"""
        self.counter += 1
        confirmation = ActionConfirmation(
            action_id=f"{action_id}_{self.counter}",
            description=description,
            danger_level=danger_level,
            callback=callback,
            cancel_callback=cancel_callback
        )
        
        self.pending_confirmations[confirmation.action_id] = confirmation
        
        if self.confirmation_callback:
            self.confirmation_callback(confirmation)
            return True
        else:
            # Если нет callback, автоматически подтверждаем безопасные действия
            if danger_level in [DangerLevel.SAFE, DangerLevel.CAUTION]:
                self.confirm_action(confirmation.action_id)
                return True
            else:
                logger.warning(f"Требуется подтверждение для {danger_level.value}: {description}")
                return False
    
    def confirm_action(self, action_id: str) -> bool:
        """Подтвердить действие"""
        if action_id in self.pending_confirmations:
            confirmation = self.pending_confirmations[action_id]
            try:
                confirmation.callback()
                del self.pending_confirmations[action_id]
                logger.info(f"✅ Действие подтверждено: {action_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка выполнения действия: {e}")
                return False
        return False
    
    def cancel_action(self, action_id: str) -> bool:
        """Отменить действие"""
        if action_id in self.pending_confirmations:
            confirmation = self.pending_confirmations[action_id]
            if confirmation.cancel_callback:
                try:
                    confirmation.cancel_callback()
                except Exception as e:
                    logger.error(f"❌ Ошибка отмены: {e}")
            del self.pending_confirmations[action_id]
            logger.info(f"❌ Действие отменено: {action_id}")
            return True
        return False


# Глобальный экземпляр системы подтверждения
confirmation_system = ConfirmationSystem()

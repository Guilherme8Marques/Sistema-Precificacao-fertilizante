"""Logger com broadcast para WebSocket — logs aparecem na UI em tempo real."""

import logging
from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    """Estrutura de uma entrada de log."""
    timestamp: str
    level: str
    actor: str
    message: str
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "actor": self.actor,
            "message": self.message,
            **self.extra,
        }

    def __str__(self) -> str:
        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️",
                "ERROR": "❌", "PROGRESS": "📊"}.get(self.level, "📋")
        return f"{self.timestamp} {icon} [{self.actor}] {self.message}"


class LogBroadcaster:
    """Gerencia callbacks de WebSocket para broadcast de logs."""

    def __init__(self):
        self._callbacks: list[Callable] = []
        self._history: list[LogEntry] = []
        self._file_logger = self._setup_file_logger()

    def _setup_file_logger(self) -> logging.Logger:
        from backend.config.settings import settings
        logger = logging.getLogger("rpa_fertilizantes")
        logger.setLevel(logging.DEBUG)
        log_file = settings.LOGS_DIR / f"rpa_{datetime.now():%Y%m%d}.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        if not logger.handlers:
            logger.addHandler(handler)
        return logger

    def register(self, callback: Callable):
        """Registra um callback de WebSocket."""
        self._callbacks.append(callback)

    def unregister(self, callback: Callable):
        """Remove um callback de WebSocket."""
        self._callbacks = [cb for cb in self._callbacks if cb != callback]

    async def _broadcast(self, entry: LogEntry):
        """Envia log para todos os WebSockets conectados."""
        for cb in self._callbacks:
            try:
                await cb(entry.to_dict())
            except Exception:
                pass

    async def emit(self, level: str, actor: str, message: str, **extra):
        """Emite um log — salva em arquivo, memória e broadcast WebSocket."""
        entry = LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            actor=actor,
            message=message,
            extra=extra,
        )
        self._history.append(entry)
        self._file_logger.info(str(entry))
        await self._broadcast(entry)

    @property
    def history(self) -> list[dict]:
        return [e.to_dict() for e in self._history]

    def clear(self):
        self._history.clear()


# Instância global
_broadcaster = LogBroadcaster()


async def log(level: str, actor: str, message: str, **extra):
    """Atalho global para emitir logs."""
    await _broadcaster.emit(level, actor, message, **extra)


def get_broadcaster() -> LogBroadcaster:
    """Retorna a instância global do broadcaster."""
    return _broadcaster

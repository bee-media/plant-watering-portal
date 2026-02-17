# async_utils.py
import asyncio
import threading
from functools import wraps


class AsyncLoopThread:
    """Поток с постоянным event loop для асинхронных операций"""

    _instance = None
    _loop = None
    _thread = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._start_loop()
        return cls._instance

    def _start_loop(self):
        """Запустить event loop в отдельном потоке"""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        """Запустить event loop"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coroutine(self, coro):
        """Запустить корутину в event loop"""
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=30)  # Таймаут 30 секунд
        else:
            raise RuntimeError("Event loop не запущен")

    def stop(self):
        """Остановить event loop"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)


# Глобальный экземпляр
async_loop = AsyncLoopThread()
from typing import Protocol

class Logger(Protocol):
    """
    Protocol for logger objects supporting info, warning, and error messages.

    Any logger implementing this protocol must provide info, warning, and error methods that accept a string message.
    """
    def info(self, msg: str, *args, **kwargs) -> None: ...
    def warning(self, msg: str, *args, **kwargs) -> None: ...
    def error(self, msg: str, *args, **kwargs) -> None: ...
    def exception(self, msg: str, *args, **kwargs) -> None: ...


class NullLogger:
    """
    A logger implementation that ignores all log messages.

    This logger provides info, warning, and error methods that do nothing, useful for disabling logging in certain contexts.
    """
    def info(self, msg: str, *args, **kwargs) -> None: pass
    def warning(self, msg: str, *args, **kwargs) -> None: pass
    def error(self, msg: str, *args, **kwargs) -> None: pass
    def exception(self, msg: str, *args, **kwargs) -> None: pass

"""Errors raised by document processing contracts."""


class DocumentProcessingError(ValueError):
    """Safe, structured error for parser and chunker failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

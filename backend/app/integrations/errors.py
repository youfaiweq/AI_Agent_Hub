"""Common errors raised by infrastructure adapters."""


class IntegrationError(RuntimeError):
    """Safe, structured error for an external infrastructure operation."""

    def __init__(self, service: str, operation: str, message: str = "service unavailable") -> None:
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.message = message

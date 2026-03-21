from typing import Optional, Any, Dict


class AvokException(Exception):
    """Base exception for Avok system."""
    
    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AvokException):
    """Resource not found error."""
    
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} with identifier {identifier} not found",
            code="NOT_FOUND",
            status_code=404
        )


class ValidationError(AvokException):
    """Validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class UnauthorizedError(AvokException):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401
        )


class PermissionDeniedError(AvokException):
    """Authorization error."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=403
        )


class EscrowError(AvokException):
    """Escrow operation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="ESCROW_ERROR",
            status_code=400,
            details=details
        )


class PaymentError(AvokException):
    """Payment processing error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="PAYMENT_ERROR",
            status_code=400,
            details=details
        )


class DisputeError(AvokException):
    """Dispute handling error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DISPUTE_ERROR",
            status_code=400,
            details=details
        )
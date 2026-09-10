class APIError(Exception):
    status_code: int = 500
    default_detail: str = "Internal error."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail


class NotFoundError(APIError):
    status_code = 404
    default_detail = "Resource not found."


class ConflictError(APIError):
    status_code = 409
    default_detail = "Resource conflicts with existing data."


class UnauthorizedError(APIError):
    status_code = 401
    default_detail = "Authentication required."


class ForbiddenError(APIError):
    status_code = 403
    default_detail = "Insufficient permissions."


class RateLimitedError(APIError):
    status_code = 429
    default_detail = "Too many requests."


class ValidationError(APIError):
    status_code = 400
    default_detail = "Invalid request."


class BusinessRuleError(APIError):
    status_code = 422
    default_detail = "Business rule violation."
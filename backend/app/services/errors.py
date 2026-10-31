"""Business-rule errors. Messages are in Spanish and safe to show to the user."""


class DomainError(ValueError):
    status_code = 422


class ConflictError(DomainError):
    status_code = 409


class PermissionDeniedError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404

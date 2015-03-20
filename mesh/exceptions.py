import socket

from scheme.exceptions import StructuralError

from mesh.constants import *

ConnectionError = socket.error

class MeshError(Exception):
    """A mesh error."""

class ConnectionFailed(MeshError):
    """Raised when a connection fails."""

class ConnectionRefused(ConnectionFailed):
    """Raised when a connection is refused."""

class ConnectionTimedOut(ConnectionFailed):
    """Raised when a connection times out."""

class OperationError(StructuralError, MeshError):
    """An operational error."""

class SpecificationError(MeshError):
    """Raised when a specification error occurs."""

class RequestError(MeshError):
    """Raised when a request fails for some reason."""

    def __init__(self, content=None, *args):
        MeshError.__init__(self, content, *args)
        self.content = content

    @classmethod
    def construct(cls, status, content=None):
        exception = cls.errors.get(status)
        if exception:
            return exception(content)

class BadRequestError(RequestError):
    status = BAD_REQUEST

class ForbiddenError(RequestError):
    status = FORBIDDEN

class NotFoundError(RequestError):
    status = NOT_FOUND

class MethodNotAllowedError(RequestError):
    status = METHOD_NOT_ALLOWED

class InvalidError(RequestError):
    status = INVALID

class TimeoutError(RequestError):
    status = TIMEOUT

class ConflictError(RequestError):
    status = CONFLICT

class GoneError(RequestError):
    status = GONE

class ServerError(RequestError):
    status = SERVER_ERROR

class UnimplementedError(RequestError):
    status = UNIMPLEMENTED

class BadGatewayError(RequestError):
    status = BAD_GATEWAY

class UnavailableError(RequestError):
    status = UNAVAILABLE

RequestError.errors = {
    BAD_REQUEST: BadRequestError,
    FORBIDDEN: ForbiddenError,
    NOT_FOUND: NotFoundError,
    INVALID: InvalidError,
    METHOD_NOT_ALLOWED: MethodNotAllowedError,
    TIMEOUT: TimeoutError,
    CONFLICT: ConflictError,
    GONE: GoneError,
    SERVER_ERROR: ServerError,
    UNIMPLEMENTED: UnimplementedError,
    BAD_GATEWAY: BadGatewayError,
    UNAVAILABLE: UnavailableError,
}

__all__ = [name for name, value in locals().items() if isinstance(value, type)
    and issubclass(value, Exception)]

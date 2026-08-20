from fastapi import HTTPException, status


class ErrorCode:
    INVALID_API_KEY = 1010
    IP_NOT_ALLOWED = 1011
    CONCURRENCY_LIMIT = 1012
    INSUFFICIENT_QUOTA = 1013
    TOKEN_DISABLED = 1014
    UPSTREAM_ERROR = 1020
    PARAMETER_ERROR = 1400
    UNAUTHORIZED = 1401
    FORBIDDEN = 1403
    NOT_FOUND = 1404
    CONFLICT = 1409


def raise_http(status_code: int, code: int, message: str, detail_type: str = "invalid_request_error") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "type": detail_type, "status": False},
    )


def parameter_error(msg: str = "Invalid parameter") -> HTTPException:
    return raise_http(status.HTTP_400_BAD_REQUEST, ErrorCode.PARAMETER_ERROR, msg)


def unauthorized(msg: str = "Unauthorized") -> HTTPException:
    return raise_http(status.HTTP_401_UNAUTHORIZED, ErrorCode.UNAUTHORIZED, msg, "authentication_error")


def forbidden(msg: str = "Forbidden") -> HTTPException:
    return raise_http(status.HTTP_403_FORBIDDEN, ErrorCode.FORBIDDEN, msg)


def not_found(msg: str = "Not found") -> HTTPException:
    return raise_http(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, msg)

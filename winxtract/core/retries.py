from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")


def with_retry(
    *,
    attempts: int,
    min_wait: float,
    max_wait: float,
    exception_types: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        return retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exception_types),
        )(fn)

    return decorator


def safe_call(fn: Callable[..., Any], default: Any = None, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default

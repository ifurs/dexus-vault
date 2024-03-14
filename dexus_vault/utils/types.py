from typing import Any, TypeVar, Type

T = TypeVar("T")


def check_var_type(value: Any, target_type: Type[T]) -> T:
    """
    Cast the given value to the specified target type.
    """
    try:
        if value and isinstance(value, target_type):
            return value
    except (ValueError, TypeError):
        # If the cast fails, return the original value
        return None

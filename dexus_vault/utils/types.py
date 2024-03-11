from typing import Any


def check_var_type(value: Any, target_type: type) -> Any:
    """
    Cast the given value to the specified target type.
    """
    try:
        if value and type(value) == target_type:
            return value
    except (ValueError, TypeError):
        # If the cast fails, return the original value
        return None

import os
import pickle


def load_file(filepath: str) -> bytes:
    """
    Loads file from filepath(preffered absolute path)
    """
    if filepath is not None:
        real_path = os.path.join(os.path.dirname(__file__), filepath)
        try:
            with open(real_path, "rb") as f:
                return f.read()

        except FileNotFoundError:
            raise FileNotFoundError(
                f"File {filepath} path is incorrect or file does not exist!"
            )
    return None

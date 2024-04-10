import os


def load_file(filepath: str) -> bytes:
    """
    Loads file from filepath(preferred absolute path)
    """
    if filepath is not None:
        real_path = os.path.join(os.getcwd(), filepath)
        try:
            with open(real_path, "rb") as f:
                return f.read()

        except FileNotFoundError:
            raise FileNotFoundError(
                f"File {filepath} path is incorrect or file does not exist!"
            )
    return None

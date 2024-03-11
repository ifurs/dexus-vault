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


### Temporary solution to store var with current dex clients, would be deprecated
def get_cached_variable(variable=set()):
    try:
        with open("cache.pkl", "rb") as f:
            cached_variable = pickle.load(f)
            return cached_variable
    except:
        cached_variable = variable
        return cached_variable


def cache_variable(variable):
    with open("cache.pkl", "wb") as f:
        pickle.dump(variable, f)

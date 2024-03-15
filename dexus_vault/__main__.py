import threading

from dexus_vault.client import run
from dexus_vault.utils.logger import logger

# Try to import dotenv, if it's installed
try:
    from dotenv import load_dotenv, find_dotenv

    load_dotenv(find_dotenv())
except ImportError:
    logger.debug(f"if you want to use .env file, please install python-dotenv")


def main():
    """
    Start a new thread to run the synchronization process.
    """
    try:
        sync_thread = threading.Thread(target=run)
        sync_thread.start()
        sync_thread.join()  # Wait for the thread to finish
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupt received, stopping...")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    logger.info("Starting dexus_vault...")
    main()

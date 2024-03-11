import threading

from dexus_vault.client import run

if __name__ == "__main__":
    sync_thread = threading.Thread(target=run)
    sync_thread.start()

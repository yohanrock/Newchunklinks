import requests
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APP_URL = "https://total-appolonia-chinnimummy16-19a206ff.koyeb.app/"

def keep_alive():
    while True:
        try:
            response = requests.get(APP_URL)
            if response.status_code == 200:
                logger.info(f"Ping successful: {APP_URL} responded with status {response.status_code}")
            else:
                logger.warning(f"Ping failed: {APP_URL} responded with status {response.status_code}")
        except Exception as e:
            logger.error(f"Error pinging {APP_URL}: {e}")
        time.sleep(120)

if __name__ == "__main__":
    logger.info("Starting keep-alive script...")
    keep_alive()

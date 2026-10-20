import logging
import logging.config
import importlib
from dotenv import load_dotenv
import asyncio  # Add this import

# Remove or comment out uvloop import to avoid conflicts
# try:
#     import uvloop
#     uvloop.install()
# except ImportError:
#     pass

def main():
    # Get logging configurations
    logging.config.fileConfig('logging.conf')
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    load_dotenv()
    # Set a new event loop before importing the bot
    asyncio.set_event_loop(asyncio.new_event_loop())
    bot = importlib.import_module("jiosaavn.bot").Bot
    bot().run()


if __name__ == "__main__":
    main()

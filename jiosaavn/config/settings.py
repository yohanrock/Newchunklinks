from os import getenv

API_ID = getenv("API_ID", "1220805")
API_HASH = getenv("API_HASH", "b01d18cba6e1b7f206cc2d3d415ceed1")
BOT_TOKEN = getenv("BOT_TOKEN", "8498699646:AAEAQIEDZQip-HPUuSnW79ptCkn1sd5hvpM")
BOT_COMMANDS = (
    ("start", "Initialize the bot and check its status"),
    ("settings", "Configure and manage bot settings"),
    ("help", "Get information on how to use the bot"),
    ("about", "Learn more about the bot and its features"),
)

DATABASE_URL = getenv("DATABASE_URL", "mongodb+srv://Chinnimummy16:Chinnimummy16@moviescluster.yx3b9in.mongodb.net/?retryWrites=true&w=majority&appName=Moviescluster")
HOST = getenv("HOST", "0.0.0.0")
PORT = int(getenv("PORT", "8080"))

# Spotify (optional — enables Spotify links + downloads via spotdl)
# Create an app at https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "")


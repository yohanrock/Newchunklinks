class TEXT:
    EMOJI_LIST = ["👍", "👎", "😊", "😢", "😍", "🔥", "🎉"]
    
    START_MSG ="""
**Hello {mention},**
<blockquote>Welcome to the music bot! Search & download from **JioSaavn** and **Spotify**.</blockquote>

**Features:**
- Search JioSaavn songs, albums, playlists, artists
- Paste Spotify track / album / playlist links
- Albums & playlists: browse songs, pick one, or **Upload All**
- Downloads go straight to Telegram

**Maintained By: [ɪɴғɪɴɪᴛʏ ᴍᴏᴠɪᴇs](https://t.me/Infinity_Movies2)**
"""
    HELP_MSG ="""
**How to use**

**JioSaavn**
1. `/settings` — quality & search type
2. Send a song / album / playlist name
3. Pick a result and upload

**Spotify**
- Send a Spotify link:
  - Track → downloads immediately
  - Album / Playlist → song list + pagination + **Upload All**
- Needs `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` in `.env`
- Server needs `spotdl` and `ffmpeg` installed
"""

    ABOUT_MSG = """
<blockquote>
**🤖 Bot Name:** [🤖 {me.username}](https://t.me/{me.username})
**📝 Language:** [Python 3](https://www.python.org/)
**🧰 Framework:** [Pyrogram](https://github.com/pyrogram/pyrogram)
**👨‍💻 Developer:** [ʀᴏᴄᴋsᴛᴀʀ](https://t.me/Keepmessage_bot)
**👑 Maintained By:** [ʀᴏᴄᴋsᴛᴀʀ](https://t.me/Keepmessage_bot)
**📢 Updates Channel:** [ɪɴғɪɴɪᴛʏ ᴍᴏᴠɪᴇs](https://t.me/Infinity_Movies2)
</blockquote>
"""

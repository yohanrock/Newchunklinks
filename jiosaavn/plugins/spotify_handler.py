"""
Spotify support for the JioSaavn bot — same UX as playlist/album handlers:
- Track link → download
- Album / playlist link → interactive song list + Upload All + pagination
Downloads use `spotdl` (must be installed on the host).
Song cache keys are prefixed with `sp:` in MongoDB.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import shutil
import time
from pathlib import Path

import aiofiles
import aiohttp
from pyrogram import filters
from pyrogram.enums import ChatAction
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from api.spotify import (
    PAGE_SIZE,
    SpotifyAPI,
    extract_id,
    get_link_type,
    resolve_short_link,
)
from jiosaavn.bot import Bot

logger = logging.getLogger(__name__)

SPOTIFY_LINK_RE = r"(?:https?://)?(?:open\.spotify\.com/(?:track|album|playlist)/|spotify\.link/)"


def _sp_song_key(track_id: str) -> str:
    return f"sp:{track_id}"


def _safe_filename(name: str) -> str:
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")
    return (name or "track")[:80]


# ---------------------------------------------------------------------------
# Link entry point
# ---------------------------------------------------------------------------

@Bot.on_message(
    filters.regex(SPOTIFY_LINK_RE) & filters.private & filters.incoming,
    group=-1,  # run before generic http handler
)
async def spotify_link_handler(client: Bot, message: Message):
    text = message.text or ""
    link_type = get_link_type(text)
    if not link_type:
        return

    msg = await message.reply("**Processing Spotify link…**", quote=True)

    if link_type == "shortened":
        text = await asyncio.to_thread(resolve_short_link, text.strip().split()[0])
        link_type = get_link_type(text)
        if not link_type:
            return await msg.edit("Could not resolve that Spotify short link.")

    item_id = extract_id(text, link_type)
    if not item_id:
        return await msg.edit("Invalid Spotify link.")

    api = SpotifyAPI()
    if not api.sp:
        return await msg.edit(
            "**Spotify is not configured.**\n\n"
            "Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in your `.env` "
            "(create an app at https://developer.spotify.com/dashboard)."
        )

    if link_type == "track":
        await msg.edit("**Downloading track…**")
        ok = await download_spotify_track(client, message, msg, item_id)
        if ok and "Failed" not in (msg.text or ""):
            try:
                await msg.delete()
            except Exception:
                pass
        return

    # Album / playlist → interactive browser (JioSaavn style)
    await msg.edit(f"**Loading {link_type}…**")
    if link_type == "album":
        info = await asyncio.to_thread(api.get_album, item_id)
    else:
        info = await asyncio.to_thread(api.get_playlist, item_id)

    if not info or not info.get("tracks"):
        return await msg.edit(f"**Could not load that Spotify {link_type}.**")

    await render_collection(client, msg, info, page=1)


# ---------------------------------------------------------------------------
# Collection browser (same pattern as playlist_or_album_handler)
# ---------------------------------------------------------------------------

async def render_collection(client: Bot, msg: Message, info: dict, page: int = 1):
    tracks = info.get("tracks") or []
    total = len(tracks)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    page_tracks = tracks[start : start + PAGE_SIZE]

    kind = info.get("type") or "album"
    kind_label = "💾 Playlist" if kind == "playlist" else "📚 Album"
    title = html.unescape(info.get("title") or kind)
    url = info.get("url") or ""
    image = info.get("image") or ""
    artist = info.get("artist") or ""

    text_parts = [
        f"[\u2063]({image})" if image else "",
        f"**{kind_label}:** [{title}]({url})" if url else f"**{kind_label}:** {title}",
        f"**🎤 Artist:** {artist}" if artist else "",
        f"**📜 Page:** {page}/{total_pages}",
        f"**🔊 Total Songs:** {total}",
        "",
        "_Tap a song to download, or **Upload All** for the whole collection._",
    ]
    text = "\n\n".join(p for p in text_parts if p)

    buttons = []
    for t in page_tracks:
        label = f"{t.get('artist') or ''} - {t.get('name') or t['id']}".strip(" -")
        if len(label) > 60:
            label = label[:57] + "..."
        buttons.append(
            [InlineKeyboardButton(f"🎙 {label}", callback_data=f"sp_song#{t['id']}")]
        )

    nav = []
    col_id = info["id"]
    if page > 1:
        nav.append(
            InlineKeyboardButton("⬅️", callback_data=f"sp_col#{kind}#{col_id}#{page - 1}")
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton("➡️", callback_data=f"sp_col#{kind}#{col_id}#{page + 1}")
        )
    if nav:
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton("Upload All 📤", callback_data=f"sp_upload#{kind}#{col_id}")]
    )
    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close")])

    try:
        await msg.edit(text[:4096], reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error("render_collection edit failed: %s", e)


@Bot.on_callback_query(filters.regex(r"^sp_col#"))
async def spotify_collection_page(client: Bot, callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("#")
    if len(parts) < 4:
        return
    _, kind, col_id, page_s = parts[0], parts[1], parts[2], parts[3]
    try:
        page = int(page_s)
    except ValueError:
        return

    api = SpotifyAPI()
    if kind == "album":
        info = await asyncio.to_thread(api.get_album, col_id)
    else:
        info = await asyncio.to_thread(api.get_playlist, col_id)

    if not info:
        return await callback.message.edit("**Could not reload collection.**")

    await render_collection(client, callback.message, info, page=page)


@Bot.on_callback_query(filters.regex(r"^sp_song#"))
async def spotify_song_callback(client: Bot, callback: CallbackQuery):
    await callback.answer()
    track_id = callback.data.split("#", 1)[1]
    msg = await callback.message.reply("**Downloading track…**", quote=True)
    # Fake a message-like object for reply_to
    class _Fake:
        pass

    fake = _Fake()
    fake.from_user = callback.from_user
    fake.id = callback.message.id
    ok = await download_spotify_track(client, fake, msg, track_id)
    if ok and "Failed" not in (msg.text or ""):
        try:
            await msg.delete()
        except Exception:
            pass


@Bot.on_callback_query(filters.regex(r"^sp_upload#"))
async def spotify_upload_all(client: Bot, callback: CallbackQuery):
    await callback.answer("Starting upload…")
    parts = callback.data.split("#")
    if len(parts) < 3:
        return
    kind, col_id = parts[1], parts[2]

    api = SpotifyAPI()
    if kind == "album":
        info = await asyncio.to_thread(api.get_album, col_id)
    else:
        info = await asyncio.to_thread(api.get_playlist, col_id)

    if not info or not info.get("tracks"):
        return await callback.message.reply("**No tracks found.**")

    tracks = info["tracks"]
    status = await callback.message.reply(
        f"**Uploading {len(tracks)} Spotify tracks…**\n_This may take a while._",
        quote=True,
    )

    class _Fake:
        pass

    fake = _Fake()
    fake.from_user = callback.from_user
    fake.id = callback.message.id

    done = 0
    failed = 0
    for i, t in enumerate(tracks, 1):
        try:
            await status.edit(f"**Uploading {i}/{len(tracks)}:** {t.get('name', t['id'])}")
        except Exception:
            pass
        ok = await download_spotify_track(client, fake, status, t["id"], keep_status=True)
        if ok:
            done += 1
        else:
            failed += 1

    summary = f"**Done.** ✅ {done} uploaded"
    if failed:
        summary += f" · ❌ {failed} failed"
    try:
        await status.edit(summary)
    except Exception:
        await callback.message.reply(summary)


# ---------------------------------------------------------------------------
# Download via spotdl
# ---------------------------------------------------------------------------

async def download_spotify_track(
    client: Bot,
    message,
    msg: Message,
    track_id: str,
    *,
    keep_status: bool = False,
) -> bool:
    """Download one Spotify track with spotdl and send as audio. Returns True on success."""
    song_key = _sp_song_key(track_id)
    user_id = message.from_user.id

    # Cache hit?
    try:
        is_exist = await client.db.is_song_id_exist(song_key)
        if is_exist:
            song = await client.db.get_song(song_key)
            # Prefer any quality key; JioSaavn stores under quality name
            for q in ("320kbps", "160kbps", "default"):
                meta = (song or {}).get(q)
                if meta and meta.get("chat_id") and meta.get("message_id"):
                    try:
                        song_msg = await client.get_messages(
                            chat_id=int(meta["chat_id"]),
                            message_ids=int(meta["message_id"]),
                        )
                        if song_msg and not song_msg.empty:
                            reply_id = getattr(message, "id", None)
                            await song_msg.copy(
                                user_id,
                                reply_to_message_id=reply_id,
                            )
                            return True
                    except Exception as e:
                        logger.warning("cache copy failed for %s: %s", track_id, e)
                    break
    except Exception as e:
        logger.warning("db cache check failed: %s", e)

    api = SpotifyAPI()
    track = await asyncio.to_thread(api.get_track, track_id)
    if not track:
        if not keep_status:
            await msg.edit(f"**Failed:** could not fetch track `{track_id}`")
        return False

    title = track["name"]
    artist = track["artist"]
    album = track.get("album") or ""
    duration = int((track.get("duration_ms") or 0) / 1000)
    image_url = track.get("image") or ""
    song_url = track.get("url") or f"https://open.spotify.com/track/{track_id}"

    caption_parts = [
        f"[\u2063]({image_url})" if image_url else "",
        f"**🎧 Song:** [{title}]({song_url})",
        f"**🎤 Artist:** {artist}" if artist else "",
        f"**📚 Album:** {album}" if album else "",
        "**🔗 Source:** Spotify",
    ]
    caption = "\n\n".join(p for p in caption_parts if p)

    download_dir = Path(f"./download/sp_{time.time()}_{user_id}")
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not keep_status:
            await msg.edit(f"__📥 Downloading {html.unescape(title)}__")
        await client.send_chat_action(user_id, ChatAction.RECORD_AUDIO)

        # Run spotdl
        out_template = str(download_dir / "{track-id}")
        cmd = [
            "spotdl",
            "download",
            f"https://open.spotify.com/track/{track_id}",
            "--bitrate",
            "320k",
            "--output",
            out_template,
            "--skip-album-art",
        ]
        # Optional Spotify credentials for spotdl itself
        cid = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
        csec = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        if cid and csec:
            cmd.extend(["--client-id", cid, "--client-secret", csec])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(download_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            if not keep_status:
                await msg.edit(f"**Failed:** download timed out for {title}")
            return False

        if proc.returncode not in (0, None):
            err = (stderr or b"").decode(errors="ignore")[-300:]
            logger.error("spotdl failed for %s: %s", track_id, err)
            if not keep_status:
                await msg.edit(
                    f"**Failed to download** `{title}`.\n"
                    f"Make sure `spotdl` and `ffmpeg` are installed.\n`{err[:200]}`"
                )
            return False

        # Find mp3
        mp3_files = list(download_dir.rglob("*.mp3"))
        if not mp3_files:
            # sometimes m4a
            mp3_files = list(download_dir.rglob("*.m4a")) + list(download_dir.rglob("*.opus"))
        if not mp3_files:
            if not keep_status:
                await msg.edit(f"**Failed:** no audio file produced for {title}")
            return False

        audio_path = str(mp3_files[0])
        thumb_path = None
        if image_url:
            thumb_path = str(download_dir / "cover.jpg")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(thumb_path, "wb") as f:
                                await f.write(await resp.read())
            except Exception as e:
                logger.warning("cover download failed: %s", e)
                thumb_path = None

        if not keep_status:
            await msg.edit(f"__📤 Uploading {html.unescape(title)}__")
        await client.send_chat_action(user_id, ChatAction.UPLOAD_AUDIO)

        reply_id = getattr(message, "id", None)
        song_file = await client.send_audio(
            chat_id=user_id,
            audio=audio_path,
            caption=caption[:1024],
            duration=duration or None,
            title=title,
            performer=artist or None,
            thumb=thumb_path,
            reply_to_message_id=reply_id,
        )

        if song_file:
            try:
                await client.db.update_song(
                    song_key, "320kbps", song_file.chat.id, song_file.id
                )
            except Exception as e:
                logger.warning("failed to cache song %s: %s", track_id, e)
            return True

        if not keep_status:
            await msg.edit(f"**Failed to upload** {title}")
        return False

    except FileNotFoundError:
        if not keep_status:
            await msg.edit(
                "**`spotdl` not found.**\n\n"
                "Install it on the server:\n"
                "`pip install spotdl yt-dlp`\n"
                "and ensure `ffmpeg` is available."
            )
        return False
    except Exception as e:
        logger.exception("download_spotify_track error")
        if not keep_status:
            await msg.edit(f"**Error:** {e}")
        return False
    finally:
        try:
            shutil.rmtree(download_dir, ignore_errors=True)
        except Exception:
            pass

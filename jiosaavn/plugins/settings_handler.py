import logging
import random
import asyncio

from jiosaavn.bot import Bot
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import MessageNotModified

logger = logging.getLogger(__name__)

# Telegram-supported reaction emojis
VALID_REACTION_EMOJIS = ["👍", "👎", "😊", "😢", "😍", "🔥", "🎉"]

@Bot.on_message(filters.command("settings"))
@Bot.on_callback_query(filters.regex(r"^settings"))
async def settings(client: Bot, message: Message|CallbackQuery):
    # Try to get random emoji
    try:
        from jiosaavn.plugins.text import TEXT
        random_emoji = random.choice(TEXT.EMOJI_LIST)
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to access TEXT.EMOJI_LIST: {e}. Using default emoji list.")
        random_emoji = random.choice(VALID_REACTION_EMOJIS)

    if getattr(message, "text", None):
        try:
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=random_emoji,
                big=True
            )
        except AttributeError:
            logger.warning("Failed to send reaction due to AttributeError")
        except Exception as e:
            logger.error(f"Error sending reaction: {e}")
    
    await asyncio.sleep(0.5)
    if isinstance(message, Message):
        msg = await message.reply("**Processing...**", quote=True)
    else:
        msg = message.message
        await message.answer()
        data = message.data.split("#")
        if len(data) > 1:
            try:
                _, key, value = data
                if key in ["type", "quality"] and value:  # Validate key and value
                    await client.db.update_user(message.from_user.id, key, value)
                    logger.info(f"Updated user {message.from_user.id} with {key}={value}")
                else:
                    logger.warning(f"Invalid callback data: {message.data}")
            except Exception as e:
                logger.error(f"Failed to update user settings: {e}")
                await msg.edit("Error updating settings. Please try again.")

    user = await client.db.get_user(message.from_user.id)
    type = user.get('type', 'all')
    quality = user.get('quality', '320kbps')

    all = '✅ All' if type == 'all' else 'All'
    albums = '✅ Albums' if type == 'albums' else 'Albums' 
    songs = '✅ Songs' if type == 'songs' else 'Songs'
    playlists = '✅ Playlist' if type == 'playlists' else 'Playlist'
    
    quality_320 = '✅ 320kbps' if quality == '320kbps' else '320kbps'
    quality_160 = '✅ 160kbps' if quality == '160kbps' else '160kbps'
    
    buttons = [
        [
            InlineKeyboardButton("𝐒𝐞𝐚𝐫𝐜𝐡 𝐓𝐲𝐩𝐞 🔍", callback_data="dummy"),
        ],
        [
            InlineKeyboardButton(all, callback_data='settings#type#all'),
            InlineKeyboardButton(albums, callback_data='settings#type#albums'),
        ],
        [
            InlineKeyboardButton(songs, callback_data='settings#type#songs'),
            InlineKeyboardButton(playlists, callback_data='settings#type#playlists'),
        ],
        [
            InlineKeyboardButton("𝐀𝐮𝐝𝐢𝐨 𝐐𝐮𝐚𝐥𝐢𝐭𝐲 🔊", callback_data="dummy"),
        ],
        [
            InlineKeyboardButton(quality_320, callback_data='settings#quality#320kbps'),
            InlineKeyboardButton(quality_160, callback_data='settings#quality#160kbps')
        ],
        [   
            InlineKeyboardButton('ʙᴀᴄᴋ ♻️', callback_data='home'), 
            InlineKeyboardButton('ᴄʟᴏsᴇ ⛔', callback_data='close')
        ]
    ]

    text = '**Select the search result type and music quality 🧏‍♂️**'
    try:
        if msg.text != text or msg.reply_markup != InlineKeyboardMarkup(buttons):
            await msg.edit(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        logger.warning("Message not modified in settings_handler")
    except Exception as e:
        logger.error(f"Failed to edit settings message: {e}")
        await msg.edit("An error occurred while updating settings.")

@Bot.on_callback_query(filters.regex(r"^dummy$"))
async def dummy(client: Bot, callback: CallbackQuery):
    await callback.answer("PLEASE CHOOSE ANOTHER BUTTON 🙆", show_alert=True)

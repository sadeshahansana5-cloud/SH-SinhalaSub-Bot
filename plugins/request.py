import asyncio
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait, ListenerTimeout
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS
from utils import get_poster
from Script import script

logger = logging.getLogger(__name__)

# Temporary storage for user request data
user_request_data = {}

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    """Start the request process."""
    if not ENABLE_REQUESTS:
        await message.reply_text("⚠️ Request feature is currently disabled.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Ask for movie/series name
    ask_msg = await message.reply_text(
        "🔍 **චිත්‍රපටයේ හෝ වෙබ් කතාමාලාවේ නම ටයිප් කරන්න:**\n\n"
        "උදා: `Leo`, `Jawan`, `Loki`",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
        ]])
    )
    
    # Wait for user response using listener
    try:
        response = await client.listen(
            chat_id=chat_id,
            user_id=user_id,
            filters=filters.text & ~filters.command(["start", "help", "request"]),
            timeout=60
        )
    except ListenerTimeout:
        await ask_msg.edit_text("⏰ **කල් ඉකුත් විය!** කරුණාකර නැවත `/request` භාවිතා කරන්න.")
        return
    
    # Delete the ask message
    await ask_msg.delete()
    
    # If user sent a command, cancel
    if response.text.startswith("/"):
        await response.delete()
        await message.reply_text("❌ **අවලංගු කරන ලදී.**")
        return
    
    # Now ask for year
    movie_name = response.text.strip()
    await response.delete()
    
    ask_year_msg = await message.reply_text(
        f"📅 **{movie_name}** නිකුත් වූ වර්ෂය ටයිප් කරන්න (හෝ නැතිනම් `0` ඔබන්න):\n\n"
        "උදා: `2023`, `2021`\n"
        "වර්ෂය නොදන්නේ නම් `0` ටයිප් කරන්න.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
        ]])
    )
    
    # Wait for year response
    try:
        year_response = await client.listen(
            chat_id=chat_id,
            user_id=user_id,
            filters=filters.text & ~filters.command(["start", "help", "request"]),
            timeout=60
        )
    except ListenerTimeout:
        await ask_year_msg.edit_text("⏰ **කල් ඉකුත් විය!** කරුණාකර නැවත `/request` භාවිතා කරන්න.")
        return
    
    await ask_year_msg.delete()
    
    year_text = year_response.text.strip()
    await year_response.delete()
    
    # Validate year
    if year_text.isdigit():
        year = int(year_text)
        if year == 0:
            year = None
    else:
        year = None
    
    # Check database
    await check_movie_in_db(client, message, movie_name, year)

async def check_movie_in_db(client, original_msg, movie_name, year):
    """Check if movie subtitles exist in database."""
    search_query = movie_name
    if year:
        search_query += f" {year}"
    
    checking_msg = await original_msg.reply_text(
        f"🔎 **{search_query}** සඳහා දත්ත ගබඩාවේ සොයමින්..."
    )
    
    try:
        if year:
            year_pattern = str(year)
            count = await Media.count_documents({
                "file_name": {"$regex": re.escape(movie_name), "$options": "i"},
                "file_type": "document"
            })
            count_with_year = await Media.count_documents({
                "file_name": {"$regex": f"{re.escape(movie_name)}.*{year_pattern}", "$options": "i"},
                "file_type": "document"
            })
            exists = count_with_year > 0 or count > 0
        else:
            count = await Media.count_documents({
                "file_name": {"$regex": re.escape(movie_name), "$options": "i"},
                "file_type": "document"
            })
            exists = count > 0
        
        if exists:
            await checking_msg.edit_text(
                f"✅ **{search_query}** සඳහා උපසිරැසි දැනටමත් අප සතුව ඇත!\n\n"
                f"ඔබට සෙවීමෙන් ලබාගත හැක.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
                ]])
            )
        else:
            await checking_msg.edit_text(
                f"😕 **{search_query}** සඳහා උපසිරැසි දැනට නැත.\n\n"
                f"ඔබට මෙය ඉල්ලීමක් කිරීමට අවශ්‍යද?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ඔව්, ඉල්ලන්න", callback_data=f"req_confirm_{movie_name}_{year if year else 0}")],
                    [InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")]
                ])
            )
    except Exception as e:
        logger.exception(f"Error checking database: {e}")
        await checking_msg.edit_text("❌ දෝෂයක් සිදු විය. කරුණාකර පසුව නැවත උත්සාහ කරන්න.")

@Client.on_callback_query(filters.regex(r"^req_confirm_"))
async def confirm_request_callback(client, query: CallbackQuery):
    data = query.data.split("_")
    year_part = data[-1]
    movie_name = "_".join(data[2:-1])
    year = int(year_part) if year_part != "0" else None
    
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    await query.answer()
    
    # Save request
    await db.add_request(user_id, search_title, year, movie_name)
    
    await query.message.edit_text(
        f"✅ **ඔබගේ ඉල්ලීම ලැබී ඇත!**\n\n"
        f"**ඉල්ලීම:** {search_title}\n"
        f"කරුණාකර රැඳී සිටින්න..."
    )
    
    # Send to request channel
    if REQUEST_CHANNEL:
        request_text = f"""#නව_ඉල්ලීම 🆕

🎬 **චිත්‍රපටය:** {movie_name}
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention} (ID: `{user_id}`)
⏰ **වේලාව:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

**තත්වය:** ⏳ බලා සිටී"""
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ සම්පූර්ණයි", callback_data=f"req_done_{user_id}_{movie_name}_{year if year else 0}"),
                InlineKeyboardButton("❌ අවලංගු", callback_data=f"req_admin_cancel_{user_id}_{movie_name}_{year if year else 0}")
            ]
        ])
        
        try:
            await client.send_message(
                chat_id=REQUEST_CHANNEL,
                text=request_text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send request to channel: {e}")
    
    if REQUEST_LOGS and REQUEST_LOGS != REQUEST_CHANNEL:
        log_text = f"""#RequestLog

Movie: {movie_name}
Year: {year}
User: {user_mention} ({user_id})
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
        try:
            await client.send_message(chat_id=REQUEST_LOGS, text=log_text)
        except Exception as e:
            logger.error(f"Failed to send request to logs: {e}")

@Client.on_callback_query(filters.regex(r"^req_done_"))
async def request_done_callback(client, query: CallbackQuery):
    data = query.data.split("_")
    user_id = int(data[2])
    year_part = data[-1]
    movie_name = "_".join(data[3:-1])
    year = int(year_part) if year_part != "0" else None
    
    await query.answer()
    
    # Update channel message
    original_text = query.message.text
    new_text = original_text.replace("⏳ බලා සිටී", "✅ **සම්පූර්ණයි**")
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"✅ **ඔබගේ ඉල්ලීම සම්පූර්ණයි!**\n\n"
                 f"**{search_title}** සඳහා උපසිරැසි දැන් ලබා ගත හැක.\n\n"
                 f"බොට් එකට ගොස් සොයන්න.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
            ]])
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

@Client.on_callback_query(filters.regex(r"^req_admin_cancel_"))
async def request_admin_cancel_callback(client, query: CallbackQuery):
    data = query.data.split("_")
    user_id = int(data[3])
    year_part = data[-1]
    movie_name = "_".join(data[4:-1])
    year = int(year_part) if year_part != "0" else None
    
    await query.answer()
    
    # Update channel message
    original_text = query.message.text
    new_text = original_text.replace("⏳ බලා සිටී", "❌ **අවලංගු කරන ලදී**")
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"❌ **ඔබගේ ඉල්ලීම අවලංගු කරන ලදී.**\n\n"
                 f"**{search_title}** සඳහා උපසිරැසි ලබා ගත නොහැකි විය.\n"
                 f"වැඩි විස්තර සඳහා පරිපාලක අමතන්න."
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_request_callback(client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("❌ **ඉල්ලීම අවලංගු කරන ලදී.**")

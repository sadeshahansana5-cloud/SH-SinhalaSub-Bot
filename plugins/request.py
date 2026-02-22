import asyncio
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import ListenerTimeout
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS
from utils import get_poster
from Script import script

logger = logging.getLogger(__name__)

# State constants
STATE_NAME = 1
STATE_YEAR = 2

# Temporary storage for user request data
user_request_data = {}

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    """Start the request process."""
    if not ENABLE_REQUESTS:
        await message.reply_text(
            "⚠️ **ඉල්ලීම් කිරීමේ පහසුකම දැනට අක්‍රිය කර ඇත.**\n"
            "කරුණාකර පසුව නැවත උත්සාහ කරන්න."
        )
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Create a nice welcome message
    welcome_text = """
🌟 **චිත්‍රපට ඉල්ලීම් පද්ධතිය** 🌟

ඔබට අවශ්‍ය චිත්‍රපටයේ හෝ වෙබ් කතාමාලාවේ **නම** ටයිප් කරන්න.

━━━━━━━━━━━━━━━━━━━━━━
📝 **උදාහරණ:**
• `Leo`
• `Jawan`
• `Loki`
• `Money Heist`

⏳ **තත්පර 60ක් ඇතුළත** පිළිතුරු දෙන්න.
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # Ask for movie/series name
    ask_msg = await message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
        ]])
    )
    
    # Wait for user response
    try:
        response = await client.listen(
            chat_id=chat_id,
            user_id=user_id,
            filters=filters.text & ~filters.command(["start", "help", "request"]),
            timeout=60
        )
    except ListenerTimeout:
        await ask_msg.edit_text(
            "⏰ **කල් ඉකුත් විය!**\n\n"
            "කරුණාකර නැවත `/request` භාවිතා කරන්න."
        )
        return
    
    # Delete the ask message
    await ask_msg.delete()
    
    # If user sent a command, cancel
    if response.text.startswith("/"):
        await response.delete()
        await message.reply_text(
            "❌ **ඉල්ලීම අවලංගු කරන ලදී.**"
        )
        return
    
    # Get movie name
    movie_name = response.text.strip()
    await response.delete()
    
    # Ask for year
    year_text = f"""
📅 **{movie_name}** නිකුත් වූ **වර්ෂය** ටයිප් කරන්න.

━━━━━━━━━━━━━━━━━━━━━━
📝 **උදාහරණ:**
• `2023`
• `2021`
• `0` - වර්ෂය නොදන්නේ නම්

⏳ **තත්පර 60ක් ඇතුළත** පිළිතුරු දෙන්න.
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    ask_year_msg = await message.reply_text(
        year_text,
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
        await ask_year_msg.edit_text(
            "⏰ **කල් ඉකුත් විය!**\n\n"
            "කරුණාකර නැවත `/request` භාවිතා කරන්න."
        )
        return
    
    await ask_year_msg.delete()
    
    year_input = year_response.text.strip()
    await year_response.delete()
    
    # Validate year
    if year_input.isdigit():
        year = int(year_input)
        if year == 0:
            year = None
        else:
            year = year
    else:
        year = None
    
    # Check database
    await check_movie_in_db(client, message, movie_name, year)

async def check_movie_in_db(client, original_msg, movie_name, year):
    """Check if movie subtitles exist in database."""
    user_id = original_msg.from_user.id
    search_query = movie_name
    if year:
        search_query += f" {year}"
    
    # Searching message
    searching_msg = await original_msg.reply_text(
        f"🔍 **{search_query}** සඳහා දත්ත ගබඩාවේ සොයමින්...\n\n"
        f"⏳ කරුණාකර රැඳී සිටින්න..."
    )
    
    try:
        # Build regex pattern
        # Escape movie name for regex
        escaped_name = re.escape(movie_name)
        
        if year:
            # Search with both name and year
            year_pattern = str(year)
            # Case 1: filename contains both name and year
            count_with_year = await Media.count_documents({
                "file_name": {
                    "$regex": f"{escaped_name}.*{year_pattern}|{year_pattern}.*{escaped_name}",
                    "$options": "i"
                },
                "file_type": "document"
            })
            
            # Case 2: filename contains name and another file has year (optional fallback)
            count_name_only = await Media.count_documents({
                "file_name": {"$regex": escaped_name, "$options": "i"},
                "file_type": "document"
            })
            
            exists = count_with_year > 0
            # If exact year match not found, but name exists, still consider as exists? 
            # We'll stick to exact match for accuracy, but inform user if name exists without year.
            if not exists and count_name_only > 0:
                # Name exists but with different year
                await searching_msg.edit_text(
                    f"ℹ️ **{movie_name}** නමින් උපසිරැසි ඇත, නමුත් **{year}** වර්ෂයට ගැලපෙන ගොනු හමු නොවීය.\n\n"
                    f"ඔබට පහත බොත්තම ඔබා සියලුම ප්‍රතිඵල බැලිය හැක.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
                    ]])
                )
                return
        else:
            # No year provided, search by name only
            count = await Media.count_documents({
                "file_name": {"$regex": escaped_name, "$options": "i"},
                "file_type": "document"
            })
            exists = count > 0
        
        if exists:
            # Subtitles found
            await searching_msg.edit_text(
                f"✅ **{search_query}** සඳහා උපසිරැසි දැනටමත් අප සතුව ඇත!\n\n"
                f"🔍 ඔබට පහත බොත්තම ඔබා සොයා ගත හැක.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
                ]])
            )
        else:
            # No subtitles found, ask for request
            await searching_msg.edit_text(
                f"😕 **{search_query}** සඳහා උපසිරැසි දැනට නැත.\n\n"
                f"❓ ඔබට මෙය **ඉල්ලීමක්** කිරීමට අවශ්‍යද?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ඔව්, ඉල්ලන්න", callback_data=f"req_confirm|{movie_name}|{year if year else 0}")],
                    [InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")]
                ])
            )
    except Exception as e:
        logger.exception(f"Error checking database: {e}")
        await searching_msg.edit_text(
            "❌ **දෝෂයක් සිදු විය!**\n\n"
            "කරුණාකර පසුව නැවත උත්සාහ කරන්න."
        )

@Client.on_callback_query(filters.regex(r"^req_confirm\|"))
async def confirm_request_callback(client, query: CallbackQuery):
    """User confirmed to request."""
    data = query.data.split("|")
    # Format: req_confirm|movie_name|year
    movie_name = data[1]
    year_part = data[2]
    year = int(year_part) if year_part != "0" else None
    
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    await query.answer()
    
    # Save request to database
    await db.add_request(user_id, search_title, year, movie_name)
    
    # Thank user
    thank_you_text = f"""
✅ **ඔබගේ ඉල්ලීම ලැබී ඇත!**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention}
━━━━━━━━━━━━━━━━━━━━━━

⏳ කරුණාකර රැඳී සිටින්න, අපි එය ඉක්මනින් සපුරාලීමට උත්සාහ කරන්නෙමු.
"""
    await query.message.edit_text(thank_you_text)
    
    # Send to request channel with admin buttons
    if REQUEST_CHANNEL:
        request_text = f"""
#නව_ඉල්ලීම 🆕

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention}
🆔 **පරිශීලක ID:** `{user_id}`
⏰ **වේලාව:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━━━━━

**තත්වය:** ⏳ **බලා සිටී**
"""
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ සම්පූර්ණයි", callback_data=f"req_done|{user_id}|{movie_name}|{year if year else 0}"),
                InlineKeyboardButton("❌ අවලංගු", callback_data=f"req_cancel_admin|{user_id}|{movie_name}|{year if year else 0}")
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
    
    # Also send to logs if separate
    if REQUEST_LOGS and REQUEST_LOGS != REQUEST_CHANNEL:
        log_text = f"""
#RequestLog

━━━━━━━━━━━━━━━━━━━━━━
🎬 **Movie:** {movie_name}
📅 **Year:** {year if year else 'Unknown'}
👤 **User:** {user_mention}
🆔 **User ID:** {user_id}
⏰ **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━━━━━
"""
        try:
            await client.send_message(chat_id=REQUEST_LOGS, text=log_text)
        except Exception as e:
            logger.error(f"Failed to send request to logs: {e}")

@Client.on_callback_query(filters.regex(r"^req_done\|"))
async def request_done_callback(client, query: CallbackQuery):
    """Admin marks request as done."""
    data = query.data.split("|")
    user_id = int(data[1])
    movie_name = data[2]
    year_part = data[3]
    year = int(year_part) if year_part != "0" else None
    
    await query.answer("✅ ඉල්ලීම සම්පූර්ණයි ලෙස සලකුණු කරන ලදී.")
    
    # Update the channel message
    original_text = query.message.text
    new_text = original_text.replace("⏳ **බලා සිටී**", "✅ **සම්පූර්ණයි**")
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"""
✅ **ඔබගේ ඉල්ලීම සම්පූර්ණයි!**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
━━━━━━━━━━━━━━━━━━━━━━

🔍 ඔබට පහත බොත්තම ඔබා දැන් සොයා ගත හැක.
""",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
            ]])
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
        await query.message.reply_text(f"⚠️ පරිශීලකයාට දැනුම් දීමට අපොහොසත් විය.")

@Client.on_callback_query(filters.regex(r"^req_cancel_admin\|"))
async def request_admin_cancel_callback(client, query: CallbackQuery):
    """Admin cancels the request."""
    data = query.data.split("|")
    user_id = int(data[1])
    movie_name = data[2]
    year_part = data[3]
    year = int(year_part) if year_part != "0" else None
    
    await query.answer("❌ ඉල්ලීම අවලංගු කරන ලදී.")
    
    # Update the channel message
    original_text = query.message.text
    new_text = original_text.replace("⏳ **බලා සිටී**", "❌ **අවලංගු කරන ලදී**")
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"""
❌ **ඔබගේ ඉල්ලීම අවලංගු කරන ලදී.**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
━━━━━━━━━━━━━━━━━━━━━━

💬 වැඩි විස්තර සඳහා කරුණාකර පරිපාලක අමතන්න.
"""
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_request_callback(client, query: CallbackQuery):
    """Cancel the request process."""
    await query.answer()
    await query.message.edit_text(
        "❌ **ඉල්ලීම අවලංගු කරන ලදී.**\n\n"
        "නැවත ඉල්ලීමක් කිරීමට `/request` භාවිතා කරන්න."
    )

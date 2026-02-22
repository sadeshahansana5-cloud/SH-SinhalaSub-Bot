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

# Temporary storage for user request data (not strictly needed but kept for compatibility)
user_request_data = {}

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    """Start the request process."""
    if not ENABLE_REQUESTS:
        await message.reply_text(
            "**⚠️ ඉල්ලීම් කිරීමේ පහසුකම දැනට අක්‍රිය කර ඇත.**\n"
            "කරුණාකර පසුව නැවත උත්සාහ කරන්න."
        )
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Step 1: Ask for movie name
    ask_name = await message.reply_text(
        "**🌟 චිත්‍රපට ඉල්ලීම් පද්ධතිය** 🌟\n\n"
        "ඔබට අවශ්‍ය චිත්‍රපටයේ හෝ වෙබ් කතාමාලාවේ **නම** ටයිප් කරන්න.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 **උදාහරණ:**\n"
        "• `Leo`\n"
        "• `Jawan`\n"
        "• `Loki`\n"
        "• `Money Heist`\n\n"
        "⏳ **තත්පර 60ක් ඇතුළත** පිළිතුරු දෙන්න.\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="req_cancel")
        ]])
    )
    
    try:
        name_response = await client.listen(
            chat_id=chat_id,
            user_id=user_id,
            filters=filters.text & ~filters.command(["start", "help", "request"]),
            timeout=60
        )
    except ListenerTimeout:
        await ask_name.edit_text(
            "**⏰ කල් ඉකුත් විය!**\n\n"
            "කරුණාකර නැවත `/request` භාවිතා කරන්න."
        )
        return
    
    await ask_name.delete()
    
    if name_response.text.startswith("/"):
        await name_response.delete()
        await message.reply_text("**❌ ඉල්ලීම අවලංගු කරන ලදී.**")
        return
    
    movie_name = name_response.text.strip()
    await name_response.delete()
    
    # Step 2: Ask for year
    ask_year = await message.reply_text(
        f"**📅 {movie_name}** නිකුත් වූ **වර්ෂය** ටයිප් කරන්න.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 **උදාහරණ:**\n"
        "• `2023`\n"
        "• `2021`\n"
        "• `0` - වර්ෂය නොදන්නේ නම්\n\n"
        "⏳ **තත්පර 60ක් ඇතුළත** පිළිතුරු දෙන්න.\n"
        "━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="req_cancel")
        ]])
    )
    
    try:
        year_response = await client.listen(
            chat_id=chat_id,
            user_id=user_id,
            filters=filters.text & ~filters.command(["start", "help", "request"]),
            timeout=60
        )
    except ListenerTimeout:
        await ask_year.edit_text(
            "**⏰ කල් ඉකුත් විය!**\n\n"
            "කරුණාකර නැවත `/request` භාවිතා කරන්න."
        )
        return
    
    await ask_year.delete()
    
    year_text = year_response.text.strip()
    await year_response.delete()
    
    # Validate year
    if year_text.isdigit():
        year = int(year_text)
        if year == 0:
            year = None
    else:
        year = None
    
    # Step 3: Check database
    await check_movie_in_db(client, message, movie_name, year)

async def check_movie_in_db(client, original_msg, movie_name, year):
    """Check if movie subtitles exist in database."""
    user_id = original_msg.from_user.id
    chat_id = original_msg.chat.id
    
    # Construct search query for display and inline
    display_query = movie_name
    if year:
        display_query += f" {year}"
    inline_query = movie_name
    if year:
        inline_query += f" {year}"
    
    searching = await original_msg.reply_text(
        f"**🔍 {display_query} සඳහා දත්ත ගබඩාවේ සොයමින්...**\n\n"
        f"⏳ කරුණාකර රැඳී සිටින්න..."
    )
    
    try:
        # Escape movie name for regex
        escaped_name = re.escape(movie_name)
        
        if year:
            # Search for files containing both name and year
            year_pattern = str(year)
            # Match name and year in any order
            regex_pattern = f"{escaped_name}.*{year_pattern}|{year_pattern}.*{escaped_name}"
            count = await Media.count_documents({
                "file_name": {"$regex": regex_pattern, "$options": "i"},
                "file_type": "document"
            })
            exists = count > 0
        else:
            # No year provided, search by name only
            count = await Media.count_documents({
                "file_name": {"$regex": escaped_name, "$options": "i"},
                "file_type": "document"
            })
            exists = count > 0
        
        if exists:
            # Found
            await searching.edit_text(
                f"**✅ {display_query} සඳහා උපසිරැසි දැනටමත් අප සතුව ඇත!**\n\n"
                f"🔍 ඔබට පහත බොත්තම ඔබා සොයා ගත හැක.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=inline_query)
                ]])
            )
        else:
            # Not found, ask to request
            await searching.edit_text(
                f"**😕 {display_query} සඳහා උපසිරැසි දැනට නැත.**\n\n"
                f"❓ ඔබට මෙය **ඉල්ලීමක්** කිරීමට අවශ්‍යද?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ඔව්, ඉල්ලන්න", callback_data=f"req_confirm|{movie_name}|{year if year else 0}")],
                    [InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="req_cancel")]
                ])
            )
    except Exception as e:
        logger.exception(f"Error checking database: {e}")
        await searching.edit_text(
            "**❌ දෝෂයක් සිදු විය!**\n\n"
            "කරුණාකර පසුව නැවත උත්සාහ කරන්න."
        )

@Client.on_callback_query(filters.regex(r"^req_confirm\|"))
async def confirm_request_callback(client, query: CallbackQuery):
    """User confirmed to request."""
    data = query.data.split("|")
    if len(data) < 3:
        await query.answer("❌ දත්ත දෝෂයකි.", show_alert=True)
        return
    
    movie_name = data[1]
    year_part = data[2]
    year = int(year_part) if year_part != "0" else None
    
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    display_name = movie_name
    if year:
        display_name += f" {year}"
    
    await query.answer()
    
    # Save request to database (make sure db.add_request exists)
    await db.add_request(user_id, display_name, year, movie_name)
    
    # Thank user
    thank_you = f"""
**✅ ඔබගේ ඉල්ලීම ලැබී ඇත!**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention}
━━━━━━━━━━━━━━━━━━━━━━

⏳ කරුණාකර රැඳී සිටින්න, අපි එය ඉක්මනින් සපුරාලීමට උත්සාහ කරන්නෙමු.
"""
    await query.message.edit_text(thank_you)
    
    # Send to request channel
    if REQUEST_CHANNEL:
        channel_msg = f"""
#නව_ඉල්ලීම 🆕

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention}
🆔 **පරිශීලක ID:** `{user_id}`
⏰ **වේලාව:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
━━━━━━━━━━━━━━━━━━━━━━

**තත්වය:** ⏳ බලා සිටී
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
                text=channel_msg,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send request to channel: {e}")
    
    # Also send to logs if separate
    if REQUEST_LOGS and REQUEST_LOGS != REQUEST_CHANNEL:
        log_msg = f"""
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
            await client.send_message(chat_id=REQUEST_LOGS, text=log_msg)
        except Exception as e:
            logger.error(f"Failed to send request to logs: {e}")

@Client.on_callback_query(filters.regex(r"^req_done\|"))
async def request_done_callback(client, query: CallbackQuery):
    """Admin marks request as done."""
    data = query.data.split("|")
    if len(data) < 4:
        await query.answer("❌ දත්ත දෝෂයකි.", show_alert=True)
        return
    
    user_id = int(data[1])
    movie_name = data[2]
    year_part = data[3]
    year = int(year_part) if year_part != "0" else None
    
    await query.answer("✅ ඉල්ලීම සම්පූර්ණයි ලෙස සලකුණු කරන ලදී.")
    
    # Update channel message
    original = query.message.text
    updated = original.replace("⏳ බලා සිටී", "✅ **සම්පූර්ණයි**")
    await query.message.edit_text(updated, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    display = movie_name
    if year:
        display += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"""
**✅ ඔබගේ ඉල්ලීම සම්පූර්ණයි!**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
━━━━━━━━━━━━━━━━━━━━━━

🔍 ඔබට පහත බොත්තම ඔබා දැන් සොයා ගත හැක.
""",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=display)
            ]])
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
        await query.message.reply_text(f"⚠️ පරිශීලකයාට දැනුම් දීමට අපොහොසත් විය.")

@Client.on_callback_query(filters.regex(r"^req_cancel_admin\|"))
async def request_cancel_admin_callback(client, query: CallbackQuery):
    """Admin cancels the request."""
    data = query.data.split("|")
    if len(data) < 4:
        await query.answer("❌ දත්ත දෝෂයකි.", show_alert=True)
        return
    
    user_id = int(data[1])
    movie_name = data[2]
    year_part = data[3]
    year = int(year_part) if year_part != "0" else None
    
    await query.answer("❌ ඉල්ලීම අවලංගු කරන ලදී.")
    
    # Update channel message
    original = query.message.text
    updated = original.replace("⏳ බලා සිටී", "❌ **අවලංගු කරන ලදී**")
    await query.message.edit_text(updated, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify user
    display = movie_name
    if year:
        display += f" {year}"
    
    try:
        await client.send_message(
            chat_id=user_id,
            text=f"""
**❌ ඔබගේ ඉල්ලීම අවලංගු කරන ලදී.**

━━━━━━━━━━━━━━━━━━━━━━
🎬 **චිත්‍රපටය:** `{movie_name}`
📅 **වර්ෂය:** {year if year else 'නොදනී'}
━━━━━━━━━━━━━━━━━━━━━━

💬 වැඩි විස්තර සඳහා කරුණාකර පරිපාලක අමතන්න.
"""
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")

@Client.on_callback_query(filters.regex(r"^req_cancel"))
async def cancel_callback(client, query: CallbackQuery):
    """User cancels the request."""
    await query.answer()
    await query.message.edit_text(
        "**❌ ඉල්ලීම අවලංගු කරන ලදී.**\n\n"
        "නැවත ඉල්ලීමක් කිරීමට `/request` භාවිතා කරන්න."
    )

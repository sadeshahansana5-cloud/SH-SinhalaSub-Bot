import asyncio
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS
from Script import script

logger = logging.getLogger(__name__)

# Temporary storage for user request data (exported for pmfilter check)
user_request_data = {}

# State constants
STATE_NAME = 1
STATE_YEAR = 2

@Client.on_message(filters.command("request") & filters.incoming)
async def request_command(client, message):
    """Start the request process - ask for movie name."""
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
    
    # Store state: waiting for name
    user_request_data[user_id] = {
        "step": STATE_NAME,
        "chat_id": chat_id,
        "ask_msg_id": ask_msg.id,
        "original_msg_id": message.id
    }
    
    # Set timeout
    asyncio.create_task(request_timeout(client, user_id, 60))

async def request_timeout(client, user_id, timeout):
    """Handle timeout for request."""
    await asyncio.sleep(timeout)
    if user_id in user_request_data:
        try:
            data = user_request_data[user_id]
            await client.send_message(
                chat_id=data["chat_id"],
                text="⏰ **කල් ඉකුත් විය!** කරුණාකර නැවත `/request` භාවිතා කරන්න.",
                reply_to_message_id=data.get("original_msg_id")
            )
        except Exception as e:
            logger.error(f"Error sending timeout message: {e}")
        finally:
            user_request_data.pop(user_id, None)

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "request"]))
async def handle_request_input(client, message):
    """Handle user's response to request prompts."""
    user_id = message.from_user.id
    
    # Check if user is in request mode
    if user_id not in user_request_data:
        return  # Not in request mode, let other handlers process
    
    data = user_request_data[user_id]
    current_step = data.get("step")
    
    # Delete the previous ask message
    try:
        await client.delete_messages(chat_id=data["chat_id"], message_ids=data["ask_msg_id"])
    except Exception as e:
        logger.error(f"Error deleting ask message: {e}")
    
    if current_step == STATE_NAME:
        # User provided name, now ask for year
        movie_name = message.text.strip()
        data["movie_name"] = movie_name
        data["step"] = STATE_YEAR
        
        # Ask for year
        ask_msg = await message.reply_text(
            f"📅 **{movie_name}** නිකුත් වූ වර්ෂය ටයිප් කරන්න (හෝ නැතිනම් `0` ඔබන්න):\n\n"
            "උදා: `2023`, `2021`\n"
            "වර්ෂය නොදන්නේ නම් `0` ටයිප් කරන්න.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
            ]])
        )
        data["ask_msg_id"] = ask_msg.id
        
    elif current_step == STATE_YEAR:
        # User provided year, now check database
        year_text = message.text.strip()
        movie_name = data.get("movie_name", "")
        
        # Validate year
        if year_text.isdigit():
            year = int(year_text)
            if year == 0:
                year = None
        else:
            year = None
        
        # Clear state
        user_request_data.pop(user_id, None)
        
        # Search for the movie in database
        await check_movie_in_db(client, message, movie_name, year)

async def check_movie_in_db(client, response_msg, movie_name, year):
    """Check if movie subtitles exist in database."""
    user_id = response_msg.from_user.id
    chat_id = response_msg.chat.id
    
    # Construct search query
    search_query = movie_name
    if year:
        search_query += f" {year}"
    
    # Inform user we are checking
    checking_msg = await response_msg.reply_text(
        f"🔎 **{search_query}** සඳහා දත්ත ගබඩාවේ සොයමින්..."
    )
    
    # Search in database
    try:
        # Create regex pattern from movie name
        if year:
            # Search with year in filename
            year_pattern = str(year)
            count = await Media.count_documents({
                "file_name": {"$regex": re.escape(movie_name), "$options": "i"},
                "file_type": "document"
            })
            # Also count with year
            count_with_year = await Media.count_documents({
                "file_name": {"$regex": f"{re.escape(movie_name)}.*{year_pattern}", "$options": "i"},
                "file_type": "document"
            })
            exists = count_with_year > 0 or count > 0
        else:
            # Search without year
            count = await Media.count_documents({
                "file_name": {"$regex": re.escape(movie_name), "$options": "i"},
                "file_type": "document"
            })
            exists = count > 0
        
        if exists:
            # Subtitles found
            await checking_msg.edit_text(
                f"✅ **{search_query}** සඳහා උපසිරැසි දැනටමත් අප සතුව ඇත!\n\n"
                f"ඔබට සෙවීමෙන් ලබාගත හැක.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔍 සොයන්න", switch_inline_query_current_chat=movie_name)
                ]])
            )
        else:
            # No subtitles found, ask if user wants to request
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
    """User confirmed to request subtitles."""
    data = query.data.split("_")
    # Format: req_confirm_movieName_year
    # movieName could have underscores, so we need to reconstruct
    # The last part is year, everything after first two is movie name
    year_part = data[-1]
    movie_name = "_".join(data[2:-1])  # Join parts between "confirm" and year
    year = int(year_part) if year_part != "0" else None
    
    user_id = query.from_user.id
    user_mention = query.from_user.mention
    
    await query.answer()
    
    # Prepare request details
    search_title = movie_name
    if year:
        search_title += f" {year}"
    
    # Save request to database
    await db.add_request(user_id, search_title, year, movie_name)
    
    # Notify user
    await query.message.edit_text(
        f"✅ **ඔබගේ ඉල්ලීම ලැබී ඇත!**\n\n"
        f"**ඉල්ලීම:** {search_title}\n"
        f"කරුණාකර රැඳී සිටින්න, අපි එය ඉක්මනින් සපුරාලීමට උත්සාහ කරන්නෙමු."
    )
    
    # Send to request channel with admin buttons
    if REQUEST_CHANNEL:
        request_text = f"""#නව_ඉල්ලීම 🆕

🎬 **චිත්‍රපටය:** {movie_name}
📅 **වර්ෂය:** {year if year else 'නොදනී'}
👤 **ඉල්ලූවේ:** {user_mention} (ID: `{user_id}`)
⏰ **වේලාව:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

**තත්වය:** ⏳ බලා සිටී"""
        
        # Buttons for admin: Done, Cancel
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
    
    # Also send to logs if separate
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
    """Admin marks request as done."""
    data = query.data.split("_")
    # Format: req_done_userId_movieName_year
    user_id = int(data[2])
    year_part = data[-1]
    movie_name = "_".join(data[3:-1])
    year = int(year_part) if year_part != "0" else None
    
    await query.answer()
    
    # Update the request message in channel
    original_text = query.message.text
    new_text = original_text.replace("⏳ බලා සිටී", "✅ **සම්පූර්ණයි**")
    
    # Remove buttons
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify the user
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
        await query.message.reply_text(f"⚠️ පරිශීලකයාට දැනුම් දීමට අපොහොසත් විය.")

@Client.on_callback_query(filters.regex(r"^req_admin_cancel_"))
async def request_admin_cancel_callback(client, query: CallbackQuery):
    """Admin cancels the request."""
    data = query.data.split("_")
    # Format: req_admin_cancel_userId_movieName_year
    user_id = int(data[3])
    year_part = data[-1]
    movie_name = "_".join(data[4:-1])
    year = int(year_part) if year_part != "0" else None
    
    await query.answer()
    
    # Update the request message in channel
    original_text = query.message.text
    new_text = original_text.replace("⏳ බලා සිටී", "❌ **අවලංගු කරන ලදී**")
    
    # Remove buttons
    await query.message.edit_text(new_text, parse_mode=enums.ParseMode.MARKDOWN)
    
    # Notify the user
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
    """Cancel the request process."""
    user_id = query.from_user.id
    await query.answer()
    await query.message.edit_text("❌ **ඉල්ලීම අවලංගු කරන ලදී.**")
    user_request_data.pop(user_id, None)

# Export user_request_data for pmfilter check
__all__ = ['user_request_data']

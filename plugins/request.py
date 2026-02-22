import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.users_chats_db import db
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS
from Script import script

logger = logging.getLogger(__name__)

# පරිශීලකයා ඉන්නා පියවර තාවකාලිකව මතක තබා ගැනීමට
user_request_data = {}

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    """Request ක්‍රියාවලිය ආරම්භ කිරීම."""
    if not ENABLE_REQUESTS:
        await message.reply_text("⚠️ Request feature is currently disabled.")
        return
    
    user_id = message.from_user.id
    
    # පළමු පියවර: නම විමසීම
    await message.reply_text(
        "🎬 කරුණාකර ඔබ ඉල්ලීමට බලාපොරොත්තු වන චිත්‍රපටයේ හෝ කතාවේ **නම (Name)** පමණක් එවන්න.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
        ]])
    )
    
    # State එක සකස් කිරීම
    user_request_data[user_id] = {"step": "waiting_name"}

@Client.on_message(filters.text & filters.private)
async def handle_request_input(client, message):
    """නම සහ වසර ලබා ගැනීම පාලනය කිරීම."""
    user_id = message.from_user.id
    
    # පරිශීලකයා ඉල්ලීමක් සිදුකරමින් නැතිනම් ඉවත් වන්න
    if user_id not in user_request_data:
        return

    step = user_request_data[user_id].get("step")
    text = message.text.strip()

    # Commands මග හැරීම
    if text.startswith("/"):
        return

    if step == "waiting_name":
        # නම ගබඩා කර වසර විමසීම
        user_request_data[user_id]["title"] = text
        user_request_data[user_id]["step"] = "waiting_year"
        
        await message.reply_text(
            f"✅ ස්තූතියි! දැන් **'{text}'** චිත්‍රපටය නිකුත් වූ **වසර (Year)** එවන්න.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ අවලංගu කරන්න", callback_data="request_cancel")
            ]])
        )

    elif step == "waiting_year":
        # වසර ලබාගෙන අවසාන කිරීම
        title = user_request_data[user_id].get("title")
        year = text
        user_mention = message.from_user.mention
        
        # දත්ත පද්ධතියට එකතු කිරීම
        movie_full_name = f"{title} {year}".strip()
        await db.add_request(user_id, movie_full_name, year, title)
        
        # පරිශීලකයාට දැනුම් දීම
        await message.reply_text(
            f"✅ **Request සාර්ථකයි!**\n\n🎥 නම: `{title}`\n📅 වසර: `{year}`\n\nඅපගේ කණ්ඩායම ඉක්මනින් මෙය පරීක්ෂා කරනු ඇත.",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Channel හෝ Logs වලට යැවීම
        if REQUEST_CHANNEL or REQUEST_LOGS:
            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_text = (
                f"📥 **New Manual Request**\n\n"
                f"👤 User: {user_mention}\n"
                f"🆔 ID: `{user_id}`\n"
                f"🎬 Title: {title}\n"
                f"📅 Year: {year}\n"
                f"🕒 Time: {time_now}"
            )
            
            for channel in [REQUEST_CHANNEL, REQUEST_LOGS]:
                if channel:
                    try:
                        await client.send_message(chat_id=channel, text=log_text)
                    except Exception as e:
                        logger.error(f"Error sending log to {channel}: {e}")

        # වැඩේ ඉවර නිසා දත්ත මකා දැමීම
        user_request_data.pop(user_id, None)

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_request_callback(client, query: CallbackQuery):
    """ඉල්ලීම අවලංගු කිරීම."""
    user_id = query.from_user.id
    await query.answer("Request cancelled")
    await query.message.edit_text("❌ ඔබගේ ඉල්ලීම අවලංගු කරන ලදී.")
    user_request_data.pop(user_id, None)

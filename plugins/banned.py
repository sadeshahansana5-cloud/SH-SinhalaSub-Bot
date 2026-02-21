from pyrogram import Client, filters
from utils import temp
from pyrogram.types import Message
from database.users_chats_db import db
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import SUPPORT_CHAT

async def banned_users(_, client, message: Message):
    return (
        message.from_user is not None or not message.sender_chat
    ) and message.from_user.id in temp.BANNED_USERS

banned_user = filters.create(banned_users)

async def disabled_chat(_, client, message: Message):
    return message.chat.id in temp.BANNED_CHATS
disabled_group=filters.create(disabled_chat)

@Client.on_message(filters.private & banned_user & filters.incoming)
async def ban_reply(bot, message):
    ban = await db.get_ban_status(message.from_user.id)
    await message.reply(f'Sorry Dude, You are Banned to use Me. \nBan Reason : {ban["ban_reason"]}')

@Client.on_message(filters.group & disabled_group & filters.incoming)
async def grp_bd(bot, message):
    buttons = [[
        InlineKeyboardButton('Support', url=SUPPORT_CHAT)
    ]]
    reply_markup=InlineKeyboardMarkup(buttons)
    vazha = await db.get_chat(message.chat.id)
    k = await message.reply(
        text=f"CHAT NOT ALLOWED 🐞\n\nMy admins has restricted me from working here ! If you want to know more about it contact support..\nReason : <code>{vazha['reason']}</code>.",
        reply_markup=reply_markup)
    try:
        await k.pin()
    except:
        pass
    await bot.leave_chat(message.chat.id)

# ==============================================================================
# NEW ADDITIONS FOR SINHALA SUBTITLE BOT (DO NOT DELETE ANYTHING ABOVE)
# ==============================================================================

from info import ALLOWED_GROUP_IDS

async def check_group_permission(_, client, message: Message):
    """Check if group is allowed to use the bot based on ALLOWED_GROUP_IDS."""
    if not ALLOWED_GROUP_IDS:  # If list is empty, no restriction
        return False
    return message.chat.id not in ALLOWED_GROUP_IDS

# Create a filter for disallowed groups
disallowed_group = filters.create(check_group_permission)

@Client.on_message(filters.group & disallowed_group & filters.incoming)
async def disallowed_group_handler(bot, message):
    """Handle messages from disallowed groups."""
    await message.reply(
        "⚠️ This bot is not allowed to work in this group.\n\n"
        "⚠️ මෙම බොට් මෙම කණ්ඩායමේ වැඩ කිරීමට අවසර නැත."
    )
    await bot.leave_chat(message.chat.id)

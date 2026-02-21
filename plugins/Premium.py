import pytz
import datetime
from Script import script 
from info import *
from utils import get_seconds, temp
from database.users_chats_db import db 
import asyncio
from pyrogram import Client, filters 
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong
from pyrogram.types import *


@Client.on_message(filters.command("remove_premium") & filters.user(ADMINS))
async def remove_premium(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])
        user = await client.get_users(user_id)
        if await db.remove_premium_access(user_id):
            await message.reply_text("ᴜsᴇʀ ʀᴇᴍᴏᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ !")
            await client.send_message(
                chat_id=user_id,
                text=script.PREMIUM_END_TEXT.format(user.mention)
            )
        else:
            await message.reply_text("ᴜɴᴀʙʟᴇ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴜsᴇʀ !\nᴀʀᴇ ʏᴏᴜ sᴜʀᴇ, ɪᴛ ᴡᴀs ᴀ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ ?")
    else:
        await message.reply_text("ᴜsᴀɢᴇ : /remove_premium user_id") 


@Client.on_message(filters.command("myplan"))
async def myplan(client, message):
    try:
        user = message.from_user.mention
        user_id = message.from_user.id
        data = await db.get_user(user_id)

        if data and data.get("expiry_time"):
            expiry = data.get("expiry_time")
            expiry_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata"))
            expiry_str_in_ist = expiry_ist.strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")

            current_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            time_left = expiry_ist - current_time
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left_str = f"{days} days, {hours} hours, {minutes} minutes"

            caption = (
                f"⚜️ <b>ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ ᴅᴀᴛᴀ :</b>\n\n"
                f"👤 <b>ᴜsᴇʀ :</b> {user}\n"
                f"⚡ <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>\n"
                f"⏰ <b>ᴛɪᴍᴇ ʟᴇғᴛ :</b> {time_left_str}\n"
                f"⌛️ <b>ᴇxᴘɪʀʏ ᴅᴀᴛᴇ :</b> {expiry_str_in_ist}"
            )

            await message.reply_photo(
                photo=SUBSCRIPTION, 
                caption=caption,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔥 ᴇxᴛᴇɴᴅ ᴘʟᴀɴ", callback_data="premium_info")]]
                )
            )
        else:
            await message.reply_photo(
                photo="https://i.ibb.co/gMrpRQWP/photo-2025-07-09-05-21-32-7524948058832896004.jpg", 
                caption=(
                    f"<b>ʜᴇʏ {user},\n\n"
                    f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴛɪᴠᴇ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ.\n"
                    f"ʙᴜʏ ᴏᴜʀ sᴜʙsᴄʀɪᴘᴛɪᴏɴ ᴛᴏ ᴇɴᴊᴏʏ ᴘʀᴇᴍɪᴜᴍ ʙᴇɴᴇғɪᴛs.</b>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("💎 ᴄʜᴇᴄᴋ ᴏᴜᴛ ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs", callback_data='premium_info')]]
                )
            )
    except Exception as e:
        print(e)

@Client.on_message(filters.command("get_premium") & filters.user(ADMINS))
async def get_premium(client, message):
    if len(message.command) == 2:
        user_id = int(message.command[1])
        user = await client.get_users(user_id)
        data = await db.get_user(user_id)  
        if data and data.get("expiry_time"):
            expiry = data.get("expiry_time") 
            expiry_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata"))
            expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")            
            current_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            time_left = expiry_ist - current_time
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left_str = f"{days} days, {hours} hours, {minutes} minutes"
            await message.reply_text(f"⚜️ ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀ ᴅᴀᴛᴀ :\n\n👤 ᴜsᴇʀ : {user.mention}\n⚡ ᴜsᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴛɪᴍᴇ ʟᴇғᴛ : {time_left_str}\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}")
        else:
            await message.reply_text("ɴᴏ ᴀɴʏ ᴘʀᴇᴍɪᴜᴍ ᴅᴀᴛᴀ ғᴏʀ ᴛʜᴇ ᴜsᴇʀ ᴡᴀs ғᴏᴜɴᴅ !")
    else:
        await message.reply_text("ᴜsᴀɢᴇ : /get_premium user_id")

@Client.on_message(filters.command("add_premium") & filters.user(ADMINS))
async def give_premium_cmd_handler(client, message):
    if len(message.command) == 4:
        time_zone = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = time_zone.strftime("%d-%m-%Y\n⏱️ ᴊᴏɪɴɪɴɢ ᴛɪᴍᴇ : %I:%M:%S %p") 
        user_id = int(message.command[1])  
        user = await client.get_users(user_id)
        time = message.command[2]+" "+message.command[3]
        seconds = await get_seconds(time)
        if seconds > 0:
            expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            user_data = {"id": user_id, "expiry_time": expiry_time}  
            await db.update_user(user_data) 
            data = await db.get_user(user_id)
            expiry = data.get("expiry_time")   
            expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")         
            await message.reply_text(f"ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅\n\n👤 ᴜsᴇʀ : {user.mention}\n⚡ ᴜsᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ : <code>{time}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True)
            await client.send_message(
                chat_id=user_id,
                text=f"👋 ʜᴇʏ {user.mention},\nᴛʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴘᴜʀᴄʜᴀsɪɴɢ ᴘʀᴇᴍɪᴜᴍ.\nᴇɴᴊᴏʏ !! ✨🎉\n\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ : <code>{time}</code>\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True              
            )    
            await client.send_message(PREMIUM_LOGS, text=f"#Added_Premium\n\n👤 ᴜsᴇʀ : {user.mention}\n⚡ ᴜsᴇʀ ɪᴅ : <code>{user_id}</code>\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ : <code>{time}</code>\n\n⏳ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ : {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}", disable_web_page_preview=True)
                    
        else:
            await message.reply_text(
                "❌ ɪɴᴠᴀʟɪᴅ ᴛɪᴍᴇ ғᴏʀᴍᴀᴛ ⚠️\n"
                "🕒 ᴘʟᴇᴀsᴇ ᴜsᴇ: <code>1 day</code>, <code>1 hour</code>, <code>1 min</code>, <code>1 month</code>, or <code>1 year</code>"
            )
    else:
        await message.reply_text(
            "📌 ᴜsᴀɢᴇ: <code>/add_premium user_id time</code>\n"
            "📝 ᴇxᴀᴍᴘʟᴇ: <code>/add_premium 123456 1 month</code>\n"
            "🧭 ᴀʟʟᴏᴡᴇᴅ ғᴏʀᴍᴀᴛs: <code>1 day</code>, <code>1 hour</code>, <code>1 min</code>, <code>1 month</code>, <code>1 year</code>"
            )

@Client.on_message(filters.command("premium_users") & filters.user(ADMINS))
async def premium_user(client, message):
    aa = await message.reply_text("<i>ɢᴇᴛᴛɪɴɢ...</i>")
    new = f" ᴘʀᴇᴍɪᴜᴍ ᴜsᴇʀs ʟɪsᴛ :\n\n"
    user_count = 1
    users = await db.get_all_users()
    async for user in users:
        data = await db.get_user(user['id'])
        if data and data.get("expiry_time"):
            expiry = data.get("expiry_time") 
            expiry_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata"))
            expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y\n⏱️ ᴇxᴘɪʀʏ ᴛɪᴍᴇ : %I:%M:%S %p")            
            current_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            time_left = expiry_ist - current_time
            days = time_left.days
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left_str = f"{days} days, {hours} hours, {minutes} minutes"	 
            new += f"{user_count}. {(await client.get_users(user['id'])).mention}\n👤 ᴜsᴇʀ ɪᴅ : {user['id']}\n⏳ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ : {expiry_str_in_ist}\n⏰ ᴛɪᴍᴇ ʟᴇғᴛ : {time_left_str}\n"
            user_count += 1
        else:
            pass
    try:    
        await aa.edit_text(new)
    except MessageTooLong:
        with open('usersplan.txt', 'w+') as outfile:
            outfile.write(new)
        await message.reply_document('usersplan.txt', caption="Paid Users:")


@Client.on_message(filters.command("plan"))
async def plan(client, message):
    user_id = message.from_user.id
    users = message.from_user.mention
    log_message = (
        f"<b><u>🚫 ᴛʜɪs ᴜsᴇʀs ᴛʀʏ ᴛᴏ ᴄʜᴇᴄᴋ /plan</u> {temp.B_LINK}\n\n"
        f"- ɪᴅ - `{user_id}`\n- ɴᴀᴍᴇ - {users}</b>")
    btn = [[
            InlineKeyboardButton('• ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ •', callback_data='buy_info'),
        ],[
            InlineKeyboardButton('• ʀᴇғᴇʀ ғʀɪᴇɴᴅs', callback_data='reffff'),
            InlineKeyboardButton('ғʀᴇᴇ ᴛʀɪᴀʟ •', callback_data='free')
        ],[
            InlineKeyboardButton('🚫 ᴄʟᴏsᴇ 🚫', callback_data='close_data')
        ]]
    msg = await message.reply_photo(
        photo="https://graph.org/file/86da2027469565b5873d6.jpg",
        caption=script.BPREMIUM_TXT,
        reply_markup=InlineKeyboardMarkup(btn)
    )
    await client.send_message(PREMIUM_LOGS, log_message)
    await asyncio.sleep(300)
    await msg.delete()
    await message.delete()


# Telegram Star Payment Method 👇
# Credit - @BeingXAnonymous

@Client.on_callback_query(filters.regex(r"buy_\d+"))
async def premium_button(client, callback_query: CallbackQuery):
    try:
        amount = int(callback_query.data.split("_")[1])
        if amount in STAR_PREMIUM_PLANS:
            try:
                buttons = [[	
                    InlineKeyboardButton("ᴄᴀɴᴄᴇʟ 🚫", callback_data="close_data"),		    				
                ]]
                reply_markup = InlineKeyboardMarkup(buttons)
                await client.send_invoice(
                    chat_id=callback_query.message.chat.id,
                    title="Premium Subscription",
                    description=f"Pay {amount} Star And Get Premium For {STAR_PREMIUM_PLANS[amount]}",
                    payload=f"dreamxpremium_{amount}",
                    currency="XTR",
                    prices=[
                        LabeledPrice(
                            label="Premium Subscription", 
                            amount=amount
                        ) 
                    ],
                    reply_markup=reply_markup
                )
                await callback_query.answer()
            except Exception as e:
                print(f"Error sending invoice: {e}")
                await callback_query.answer("🚫 Error Processing Your Payment. Try again.", show_alert=True)
        else:
            await callback_query.answer("⚠️ Invalid Premium Package.", show_alert=True)
    except Exception as e:
        print(f"Error In buy_ - {e}")
 
@Client.on_pre_checkout_query()
async def pre_checkout_handler(client, query: PreCheckoutQuery):
    try:
        if query.payload.startswith("dreamxpremium_"):
            await query.answer(success=True)
        else:
            await query.answer(success=False, error_message="⚠️ Invalid Purchase Type.", show_alert=True)
    except Exception as e:
        print(f"Pre-checkout error: {e}")
        await query.answer(success=False, error_message="🚫 Unexpected Error Occurred." , show_alert=True)

@Client.on_message(filters.successful_payment)
async def successful_premium_payment(client, message):
    try:
        amount = int(message.successful_payment.total_amount)
        user_id = message.from_user.id
        time_zone = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        current_time = time_zone.strftime("%d-%m-%Y | %I:%M:%S %p") 
        if amount in STAR_PREMIUM_PLANS:
            time = STAR_PREMIUM_PLANS[amount]
            seconds = await get_seconds(time)
            if seconds > 0:
                expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                user_data = {"id": user_id, "expiry_time": expiry_time}
                await db.update_user(user_data)
                data = await db.get_user(user_id)
                expiry = data.get("expiry_time")
                expiry_str_in_ist = expiry.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%d-%m-%Y | %I:%M:%S %p")    
                await message.reply(text=f"Thankyou For Purchasing Premium Service Using Star ✅\n\nSubscribtion Time - {time}\nExpire In - {expiry_str_in_ist}", disable_web_page_preview=True)                
                await client.send_message(PREMIUM_LOGS, text=f"#Purchase_Premium_With_Start\n\n👤 ᴜsᴇʀ - {message.from_user.mention}\n\n⚡ ᴜsᴇʀ ɪᴅ - <code>{user_id}</code>\n\n🚫 sᴛᴀʀ ᴘᴀʏ - {amount}⭐\n\n⏰ ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ - {time}\n\n⌛️ ᴊᴏɪɴɪɴɢ ᴅᴀᴛᴇ - {current_time}\n\n⌛️ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ - {expiry_str_in_ist}", disable_web_page_preview=True)
            else:
                await message.reply("⚠️ Invalid Premium Time.")
        else:
            await message.reply("⚠️ Invalid Premium Package.")
    except Exception as e:
        print(f"Error Processing Premium Payment: {e}")
        await message.reply("✅ Thank You For Your Payment! (Error Logging Details)")

# ==============================================================================
# ADDITIONS FOR SINHALA SUBTITLE BOT (DO NOT DELETE ANYTHING ABOVE)
# ==============================================================================

# Override premium plan display to use Sinhala names if available
# The following functions are kept as is, but if you want to use PREMIUM_PLAN_NAMES from info.py,
# you can modify the plan display messages. However, we will not delete anything, so we add new
# helper functions or modify callbacks carefully. Since callbacks are already defined,
# we can add a new callback for Sinhala plan display if needed, but we'll keep the original.

# For now, we add a note that the premium plan names can be customized in info.py with PREMIUM_PLAN_NAMES.
# No code deletion, just this comment.

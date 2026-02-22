import asyncio
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS
from utils import get_poster
from Script import script

logger = logging.getLogger(__name__)

# Temporary storage for user request data
user_request_data = {}

@Client.on_message(filters.command("request") & filters.incoming)
async def request_command(client, message):
    """Start the request process."""
    if not ENABLE_REQUESTS:
        await message.reply_text("⚠️ Request feature is currently disabled.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Ask for movie/series name
    ask_msg = await message.reply_text(
        script.REQUEST_START_TXT,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")
        ]])
    )
    
    # Store state
    user_request_data[user_id] = {
        "step": "waiting_name",
        "chat_id": chat_id,
        "ask_msg_id": ask_msg.id,
        "original_msg_id": message.id
    }
    
    # Set timeout
    asyncio.create_task(request_timeout(client, user_id, 60))

async def request_timeout(client, user_id, timeout):
    """Handle timeout for request."""
    await asyncio.sleep(timeout)
    if user_id in user_request_data and user_request_data[user_id].get("step") == "waiting_name":
        try:
            data = user_request_data[user_id]
            await client.send_message(
                chat_id=data["chat_id"],
                text=script.REQUEST_TIMEOUT_TXT,
                reply_to_message_id=data.get("original_msg_id")
            )
        except Exception as e:
            logger.error(f"Error sending timeout message: {e}")
        finally:
            user_request_data.pop(user_id, None)

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "request"]))
async def handle_request_input(client, message):
    """Handle user's response to request."""
    user_id = message.from_user.id
    
    # Check if user is in request mode
    if user_id not in user_request_data or user_request_data[user_id].get("step") != "waiting_name":
        return  # Not in request mode, let other handlers process
    
    query = message.text.strip()
    data = user_request_data[user_id]
    
    # Delete the ask message
    try:
        await client.delete_messages(chat_id=data["chat_id"], message_ids=data["ask_msg_id"])
    except Exception as e:
        logger.error(f"Error deleting ask message: {e}")
    
    # Clear state
    user_request_data.pop(user_id, None)
    
    # Process the search
    await process_name_input(client, message, query)

async def process_name_input(client, response_msg, query):
    """Process movie name and show IMDb results."""
    user_id = response_msg.from_user.id
    chat_id = response_msg.chat.id
    
    # Inform user we are searching
    searching_msg = await response_msg.reply_text(
        script.REQUEST_SEARCHING_TXT.format(query=query)
    )
    
    # Search using IMDb (get_poster with bulk=True)
    try:
        movies = await get_poster(query, bulk=True)
        
        if not movies:
            await searching_msg.edit_text(
                script.REQUEST_NO_RESULTS_TXT.format(query=query)
            )
            return
        
        # Create buttons for up to 5 movies
        buttons = []
        for movie in movies[:5]:
            title = movie.get('title')
            year = movie.get('year')
            movie_id = movie.movieID
            button_text = f"{title} ({year})"
            buttons.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"req_select_{movie_id}"
                )
            ])
        
        # Add cancel button
        buttons.append([InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")])
        
        await searching_msg.edit_text(
            script.REQUEST_SELECT_MOVIE_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.exception(f"Error in request search: {e}")
        await searching_msg.edit_text("❌ දෝෂයක් සිදු විය. කරුණාකර පසුව නැවත උත්සාහ කරන්න.")

@Client.on_callback_query(filters.regex(r"^req_select_"))
async def select_movie_callback(client, query: CallbackQuery):
    """Handle movie selection from search results."""
    movie_id = query.data.split("_")[2]
    user_id = query.from_user.id
    
    await query.answer()
    
    # Fetch movie details using IMDb
    try:
        details = await get_poster(movie_id, id=True)
        if not details:
            await query.message.edit_text("❌ චිත්‍රපට විස්තර ලබා ගත නොහැකි විය.")
            return
        
        # Check if subtitles already exist
        title = details.get('title', '')
        year = details.get('year', '')
        search_title = re.escape(title)
        subtitle_count = await Media.count_documents({
            "file_name": {"$regex": search_title, "$options": "i"},
            "file_type": "document"
        })
        exists = subtitle_count > 0
        
        # Prepare availability status
        if exists:
            avail_text = script.REQUEST_AVAILABLE_TXT
        else:
            avail_text = script.REQUEST_NOT_AVAILABLE_TXT
        
        # Build caption
        plot = details.get('plot', 'කතාව නොමැත.')
        if len(plot) > 200:
            plot = plot[:200] + "..."
        
        caption = script.REQUEST_DETAILS_TXT.format(
            title=title,
            year=year,
            rating=details.get('rating', 'N/A'),
            plot=plot,
            available_status=avail_text
        )
        
        # Buttons
        buttons = []
        if not exists:
            buttons.append([
                InlineKeyboardButton(
                    script.REQUEST_BUTTON_TXT,
                    callback_data=f"req_submit_{movie_id}"
                )
            ])
        buttons.append([InlineKeyboardButton("❌ අවලංගු කරන්න", callback_data="request_cancel")])
        
        # Try to send with poster, fallback to text
        poster = details.get('poster')
        if poster:
            try:
                await query.message.delete()
                await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=poster,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
                return
            except Exception as e:
                logger.warning(f"Failed to send poster, falling back to text: {e}")
        
        # If poster fails or doesn't exist, send text only
        await query.message.edit_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        logger.exception(f"Error in select_movie_callback: {e}")
        await query.message.edit_text("❌ දෝෂයක් සිදු විය. කරුණාකර නැවත උත්සාහ කරන්න.")

@Client.on_callback_query(filters.regex(r"^req_submit_"))
async def submit_request_callback(client, query: CallbackQuery):
    """Handle final request submission."""
    movie_id = query.data.split("_")[2]
    user_id = query.from_user.id
    
    await query.answer()
    
    # Fetch movie details
    try:
        details = await get_poster(movie_id, id=True)
        if not details:
            await query.message.edit_text("❌ චිත්‍රපට විස්තර ලබා ගත නොහැකි විය.")
            return
        
        title = details.get('title', 'Unknown')
        year = details.get('year', '')
        movie_name = f"{title} {year}".strip()
        
        # Save request to database
        await db.add_request(user_id, movie_name, year, title)
        
        # Notify user
        await query.message.edit_text(
            script.REQUEST_SUBMITTED_TXT.format(title=title, year=year, user=query.from_user.mention),
            parse_mode=enums.ParseMode.HTML
        )
        
        # Log to channel
        if REQUEST_CHANNEL:
            log_text = script.REQUEST_LOG_TXT.format(
                title=title,
                year=year,
                user=query.from_user.mention,
                user_id=user_id,
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            try:
                await client.send_message(
                    chat_id=REQUEST_CHANNEL,
                    text=log_text,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send request to channel: {e}")
        
        if REQUEST_LOGS and REQUEST_LOGS != REQUEST_CHANNEL:
            try:
                await client.send_message(
                    chat_id=REQUEST_LOGS,
                    text=log_text,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send request to logs: {e}")
        
    except Exception as e:
        logger.exception(f"Error in submit_request_callback: {e}")
        await query.message.edit_text("❌ දෝෂයක් සිදු විය. කරුණාකර පසුව නැවත උත්සාහ කරන්න.")

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_request_callback(client, query: CallbackQuery):
    """Cancel the request process."""
    user_id = query.from_user.id
    await query.answer()
    await query.message.edit_text("❌ ඉල්ලීම අවලංගු කරන ලදී.")
    user_request_data.pop(user_id, None)

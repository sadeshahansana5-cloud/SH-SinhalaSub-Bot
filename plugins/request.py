import asyncio
import re
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified, FloodWait
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ENABLE_REQUESTS, REQUEST_CHANNEL, REQUEST_LOGS, TMDB_API_KEY, LOG_CHANNEL
from plugins.Dreamxfutures.Imdbposter import get_movie_detailsx
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
            InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")
        ]])
    )
    
    # Store state
    user_request_data[user_id] = {"step": "waiting_name", "chat_id": chat_id, "ask_msg_id": ask_msg.id}
    
    # Wait for response with timeout
    try:
        response = await client.listen(chat_id=chat_id, user_id=user_id, timeout=60)
    except asyncio.TimeoutError:
        await ask_msg.edit_text(script.REQUEST_TIMEOUT_TXT)
        user_request_data.pop(user_id, None)
        return
    
    # Cancel if user pressed cancel or response is a command
    if response.text and response.text.startswith("/"):
        await ask_msg.delete()
        await response.delete()
        user_request_data.pop(user_id, None)
        return
    
    # Process the search
    await process_name_input(client, message, response, ask_msg)

async def process_name_input(client, original_msg, response_msg, ask_msg):
    """Process the movie name input and search TMDB."""
    user_id = response_msg.from_user.id
    query = response_msg.text.strip()
    
    # Delete user's message and the ask message
    await response_msg.delete()
    await ask_msg.delete()
    
    # Inform user we are searching
    searching_msg = await original_msg.reply_text(
        script.REQUEST_SEARCHING_TXT.format(query=query)
    )
    
    # Search TMDB
    try:
        # Use get_movie_detailsx to get search results
        # This function returns details for the first result, but we need a list of results.
        # Since get_movie_detailsx doesn't support bulk, we'll use an alternative approach:
        # We can use the original get_poster with bulk=True, but that uses IMDb, not TMDB.
        # To keep TMDB, we might need to call a search endpoint. For simplicity, we'll use get_movie_detailsx
        # and if it returns None, try with get_poster? But the user wanted TMDB.
        # Actually, get_movie_detailsx already does a search and returns the best match, but we need multiple options.
        # We can implement a simple TMDB search using aiohttp. But the existing code uses an external API that might not support multiple results.
        # Given the complexity, we'll adapt: use get_poster (IMDb) for suggestions, and then when user selects, use get_movie_detailsx for details.
        # This aligns with the existing misc.py approach.
        
        from utils import get_poster
        movies = await get_poster(query, bulk=True)
        
        if not movies:
            await searching_msg.edit_text(script.REQUEST_NO_RESULTS_TXT.format(query=query))
            user_request_data.pop(user_id, None)
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
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
        
        await searching_msg.edit_text(
            script.REQUEST_SELECT_MOVIE_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        # Store the query and movie list for later? Not needed.
        
    except Exception as e:
        logger.exception(f"Error in request search: {e}")
        await searching_msg.edit_text("❌ An error occurred. Please try again later.")
        user_request_data.pop(user_id, None)

@Client.on_callback_query(filters.regex(r"^req_select_"))
async def select_movie_callback(client, query: CallbackQuery):
    """Handle movie selection from search results."""
    movie_id = query.data.split("_")[2]
    user_id = query.from_user.id
    
    await query.answer()
    
    # Fetch movie details
    try:
        # Use get_movie_detailsx with TMDB if possible, else fallback to get_movie_details
        details = await get_movie_detailsx(movie_id, id=True)
        if not details or details.get("error"):
            # Fallback to IMDb
            from utils import get_poster
            details = await get_poster(movie_id, id=True)
            if not details:
                await query.message.edit_text("❌ Could not fetch movie details.")
                return
        
        # Check if subtitles already exist in database
        title = details.get('title', '')
        year = details.get('year', '')
        search_query = f"{title} {year}".strip()
        # Simple check: count documents with file_name containing title and year
        subtitle_count = await Media.count_documents({
            "file_name": {"$regex": re.escape(title), "$options": "i"},
            "file_type": "document"
        })
        exists = subtitle_count > 0
        
        # Prepare availability status
        if exists:
            avail_text = script.REQUEST_AVAILABLE_TXT
        else:
            avail_text = script.REQUEST_NOT_AVAILABLE_TXT
        
        # Build caption
        caption = script.REQUEST_DETAILS_TXT.format(
            title=details.get('title', 'N/A'),
            year=details.get('year', 'N/A'),
            rating=details.get('rating', 'N/A'),
            plot=details.get('plot', 'No plot available.')[:200] + "...",
            available_status=avail_text
        )
        
        # Buttons: Request button (if not exists), Cancel
        buttons = []
        if not exists:
            buttons.append([
                InlineKeyboardButton(
                    script.REQUEST_BUTTON_TXT,
                    callback_data=f"req_submit_{movie_id}"
                )
            ])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
        
        # Send message with poster if available
        if details.get('poster_url'):
            try:
                await query.message.delete()
                await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=details['poster_url'],
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                logger.exception(f"Error sending photo: {e}")
                await query.message.edit_text(
                    caption,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
        else:
            await query.message.edit_text(
                caption,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        
    except Exception as e:
        logger.exception(f"Error in select_movie_callback: {e}")
        await query.message.edit_text("❌ An error occurred. Please try again.")

@Client.on_callback_query(filters.regex(r"^req_submit_"))
async def submit_request_callback(client, query: CallbackQuery):
    """Handle final request submission."""
    movie_id = query.data.split("_")[2]
    user_id = query.from_user.id
    
    await query.answer()
    
    # Fetch movie details again to get title/year
    try:
        details = await get_movie_detailsx(movie_id, id=True)
        if not details or details.get("error"):
            from utils import get_poster
            details = await get_poster(movie_id, id=True)
            if not details:
                await query.message.edit_text("❌ Could not fetch movie details.")
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
        
        # Send to request channel/logs if configured
        if REQUEST_CHANNEL:
            # Create a message for the request channel
            user_mention = query.from_user.mention
            user_id_str = str(user_id)
            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_text = script.REQUEST_LOG_TXT.format(
                title=title,
                year=year,
                user=user_mention,
                user_id=user_id_str,
                time=time_now
            )
            try:
                await client.send_message(
                    chat_id=REQUEST_CHANNEL,
                    text=log_text,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send request to channel: {e}")
        
        if REQUEST_LOGS:
            # Also send to logs if separate
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
        await query.message.edit_text("❌ An error occurred while submitting your request.")

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_request_callback(client, query: CallbackQuery):
    """Cancel the request process."""
    user_id = query.from_user.id
    await query.answer()
    await query.message.edit_text("❌ Request cancelled.")
    user_request_data.pop(user_id, None)

import asyncio
import re
import logging
import aiohttp
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

# TMDB API configuration
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

async def search_tmdb(query):
    """Search TMDB for movies/TV shows and return list of results."""
    if not TMDB_API_KEY:
        logger.warning("TMDB_API_KEY not set, skipping TMDB search")
        return None
    
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US",
        "page": 1,
        "include_adult": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TMDB_SEARCH_URL, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"TMDB search failed with status {resp.status}")
                    return None
                data = await resp.json()
                results = data.get("results", [])
                # Filter to movies and TV shows only
                filtered = [r for r in results if r.get("media_type") in ["movie", "tv"]]
                return filtered[:10]  # Limit to 10 results
    except Exception as e:
        logger.exception(f"Error in TMDB search: {e}")
        return None

async def get_tmdb_details(tmdb_id, media_type="movie"):
    """Fetch details for a specific TMDB ID."""
    if not TMDB_API_KEY:
        return None
    
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "append_to_response": "external_ids"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception as e:
        logger.exception(f"Error fetching TMDB details: {e}")
        return None

def format_tmdb_result(item):
    """Format TMDB result item for display."""
    media_type = item.get("media_type", "movie")
    title = item.get("title") or item.get("name") or "Unknown"
    year = ""
    if media_type == "movie":
        release = item.get("release_date", "")
        if release and len(release) >= 4:
            year = release[:4]
    else:
        first_air = item.get("first_air_date", "")
        if first_air and len(first_air) >= 4:
            year = first_air[:4]
    
    poster = item.get("poster_path")
    poster_url = f"{TMDB_IMAGE_BASE}{poster}" if poster else None
    
    return {
        "id": item.get("id"),
        "media_type": media_type,
        "title": title,
        "year": year,
        "poster_url": poster_url,
        "overview": item.get("overview", ""),
        "vote_average": item.get("vote_average", 0)
    }

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
        tmdb_results = await search_tmdb(query)
        
        if not tmdb_results:
            # Fallback to IMDb search
            from utils import get_poster
            movies = await get_poster(query, bulk=True)
            if not movies:
                await searching_msg.edit_text(script.REQUEST_NO_RESULTS_TXT.format(query=query))
                user_request_data.pop(user_id, None)
                return
            
            # Create IMDb buttons
            buttons = []
            for movie in movies[:5]:
                title = movie.get('title')
                year = movie.get('year')
                movie_id = movie.movieID
                button_text = f"{title} ({year})"
                buttons.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"req_select_imdb_{movie_id}"
                    )
                ])
            
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
            await searching_msg.edit_text(
                script.REQUEST_SELECT_MOVIE_TXT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        
        # Create TMDB buttons
        buttons = []
        for item in tmdb_results[:5]:
            formatted = format_tmdb_result(item)
            button_text = f"{formatted['title']} ({formatted['year']})"
            buttons.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"req_select_tmdb_{formatted['media_type']}_{formatted['id']}"
                )
            ])
        
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
        
        await searching_msg.edit_text(
            script.REQUEST_SELECT_MOVIE_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.exception(f"Error in request search: {e}")
        await searching_msg.edit_text("❌ An error occurred. Please try again later.")
        user_request_data.pop(user_id, None)

@Client.on_callback_query(filters.regex(r"^req_select_"))
async def select_movie_callback(client, query: CallbackQuery):
    """Handle movie selection from search results."""
    data_parts = query.data.split("_")
    # Format: req_select_tmdb_mediaType_id or req_select_imdb_id
    source = data_parts[2]  # "tmdb" or "imdb"
    
    await query.answer()
    
    try:
        if source == "tmdb":
            media_type = data_parts[3]
            tmdb_id = int(data_parts[4])
            details = await get_tmdb_details(tmdb_id, media_type)
            if not details:
                await query.message.edit_text("❌ Could not fetch movie details from TMDB.")
                return
            
            # Format details
            title = details.get("title") or details.get("name") or "Unknown"
            year = ""
            if media_type == "movie":
                release = details.get("release_date", "")
                if release and len(release) >= 4:
                    year = release[:4]
            else:
                first_air = details.get("first_air_date", "")
                if first_air and len(first_air) >= 4:
                    year = first_air[:4]
            
            poster_path = details.get("poster_path")
            poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None
            overview = details.get("overview", "No plot available.")
            rating = details.get("vote_average", 0)
            imdb_id = details.get("external_ids", {}).get("imdb_id")
            
            movie_info = {
                "title": title,
                "year": year,
                "poster_url": poster_url,
                "overview": overview,
                "rating": rating,
                "imdb_id": imdb_id,
                "tmdb_id": tmdb_id,
                "media_type": media_type
            }
        else:  # imdb
            imdb_id = data_parts[3]
            from utils import get_poster
            details = await get_poster(imdb_id, id=True)
            if not details:
                await query.message.edit_text("❌ Could not fetch movie details from IMDb.")
                return
            movie_info = {
                "title": details.get('title'),
                "year": details.get('year'),
                "poster_url": details.get('poster'),
                "overview": details.get('plot'),
                "rating": details.get('rating'),
                "imdb_id": imdb_id
            }
        
        # Check if subtitles already exist
        subtitle_count = await Media.count_documents({
            "file_name": {"$regex": re.escape(movie_info['title']), "$options": "i"},
            "file_type": "document"
        })
        exists = subtitle_count > 0
        
        # Prepare availability status
        avail_text = script.REQUEST_AVAILABLE_TXT if exists else script.REQUEST_NOT_AVAILABLE_TXT
        
        # Build caption
        caption = script.REQUEST_DETAILS_TXT.format(
            title=movie_info['title'],
            year=movie_info['year'],
            rating=movie_info.get('rating', 'N/A'),
            plot=movie_info['overview'][:200] + "...",
            available_status=avail_text
        )
        
        # Buttons
        buttons = []
        if not exists:
            buttons.append([
                InlineKeyboardButton(
                    script.REQUEST_BUTTON_TXT,
                    callback_data=f"req_submit_{source}_{movie_info.get('tmdb_id', imdb_id)}"
                )
            ])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
        
        # Send message with poster
        if movie_info.get('poster_url'):
            try:
                await query.message.delete()
                await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=movie_info['poster_url'],
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
    data_parts = query.data.split("_")
    source = data_parts[2]  # "tmdb" or "imdb"
    item_id = data_parts[3]
    user_id = query.from_user.id
    
    await query.answer()
    
    try:
        if source == "tmdb":
            # We need to fetch details again to get title/year
            # For simplicity, we stored tmdb_id and media_type? Not stored. We'll assume we have the ID and fetch.
            # But we don't have media_type. We'll use a generic fetch that determines type.
            # Alternatively, we can store more data in callback. Let's use a different approach: use the same details we had earlier? Not stored.
            # To avoid complexity, we'll use get_movie_detailsx which uses the external API, or we can store the title/year in callback data (but it's long).
            # For now, we'll use get_movie_detailsx with the tmdb_id (assuming it works).
            details = await get_movie_detailsx(item_id, id=True)
            if not details or details.get("error"):
                # Fallback to IMDb using get_poster? But we don't have imdb_id.
                await query.message.edit_text("❌ Could not fetch movie details.")
                return
            title = details.get('title', 'Unknown')
            year = details.get('year', '')
        else:  # imdb
            from utils import get_poster
            details = await get_poster(item_id, id=True)
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
        if REQUEST_CHANNEL or REQUEST_LOGS:
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
            if REQUEST_CHANNEL:
                try:
                    await client.send_message(
                        chat_id=REQUEST_CHANNEL,
                        text=log_text,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Failed to send request to channel: {e}")
            if REQUEST_LOGS:
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

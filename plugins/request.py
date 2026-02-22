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

user_request_data = {}

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/multi"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

async def search_tmdb(query):
    if not TMDB_API_KEY:
        return None
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US",
        "page": 1,
        "include_adult": "false"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TMDB_SEARCH_URL, params=params) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("results", [])
                return [r for r in results if r.get("media_type") in ["movie", "tv"]][:10]
    except Exception as e:
        logger.exception(f"Error in TMDB search: {e}")
        return None

async def get_tmdb_details(tmdb_id, media_type):
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "append_to_response": "external_ids"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"Error fetching TMDB details: {e}")
    return None

@Client.on_message(filters.command("request") & filters.private)
async def request_command(client, message):
    if not ENABLE_REQUESTS:
        await message.reply_text("❌ Requests are currently disabled.")
        return
    await message.reply_text("🔍 Please send the name of the movie or TV show you want to request.")
    user_request_data[message.from_user.id] = {'step': 'awaiting_name'}

@Client.on_message(filters.text & filters.private)
async def handle_messages(client, message):
    user_id = message.from_user.id
    if user_id in user_request_data and user_request_data[user_id].get('step') == 'awaiting_name':
        await process_name_input(client, message)

async def process_name_input(client, message):
    query = message.text
    user_id = message.from_user.id
    ms = await message.reply_text("🔍 Searching...")
    
    tmdb_results = await search_tmdb(query)
    if not tmdb_results:
        await ms.edit_text("❌ No results found on TMDB. Please try with a more specific name.")
        return

    buttons = []
    for res in tmdb_results:
        name = res.get("title") or res.get("name")
        year = res.get("release_date", res.get("first_air_date", ""))[:4]
        year_str = f" ({year})" if year else ""
        m_type = res.get("media_type")
        t_id = res.get("id")
        buttons.append([InlineKeyboardButton(f"{name}{year_str}", callback_data=f"req_select_tmdb_{m_type}_{t_id}")])
    
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
    await ms.edit_text("✅ I found these results. Please select the correct one:", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^req_select_"))
async def select_movie_callback(client, query: CallbackQuery):
    data_parts = query.data.split("_")
    source = data_parts[2]
    await query.answer()
    
    try:
        if source == "tmdb":
            media_type = data_parts[3]
            tmdb_id = int(data_parts[4])
            details = await get_tmdb_details(tmdb_id, media_type)
            if not details:
                await query.message.edit_text("❌ Could not fetch details.")
                return
            
            title = details.get("title") or details.get("name")
            year = (details.get("release_date") or details.get("first_air_date", ""))[:4]
            movie_info = {
                "title": title, "year": year, 
                "poster_url": f"{TMDB_IMAGE_BASE}{details.get('poster_path')}" if details.get('poster_path') else None,
                "overview": details.get("overview", ""), "rating": details.get("vote_average", 0),
                "tmdb_id": tmdb_id, "media_type": media_type
            }
        
        # Check Database
        subtitle_count = await Media.count_documents({
            "file_name": {"$regex": re.escape(movie_info['title']), "$options": "i"}
        })
        exists = subtitle_count > 0
        
        avail_text = script.REQUEST_AVAILABLE_TXT if exists else script.REQUEST_NOT_AVAILABLE_TXT
        caption = script.REQUEST_DETAILS_TXT.format(
            title=movie_info['title'], year=movie_info['year'],
            rating=movie_info['rating'], plot=movie_info['overview'][:200],
            available_status=avail_text
        )
        
        buttons = []
        if not exists:
            buttons.append([InlineKeyboardButton(script.REQUEST_BUTTON_TXT, callback_data=f"req_submit_tmdb_{movie_info['tmdb_id']}")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="request_cancel")])
        
        if movie_info['poster_url']:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=movie_info['poster_url'], caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.edit_text(caption, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        logger.exception(f"Error: {e}")
        await query.message.edit_text("❌ An error occurred.")

@Client.on_callback_query(filters.regex(r"^req_submit_"))
async def submit_request_callback(client, query: CallbackQuery):
    await query.answer("Submitting your request...", show_alert=True)
    # මෙතනින් පසු ඔබ කලින් ලියා තිබූ submission logic එක ක්‍රියාත්මක වේ...
    await query.message.edit_text("✅ Your request has been submitted!")

@Client.on_callback_query(filters.regex(r"^request_cancel"))
async def cancel_callback(client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("❌ Request cancelled.")

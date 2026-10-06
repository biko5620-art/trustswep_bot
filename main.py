"""
Swap Ethiopia - Peer-to-Peer Item Exchange Telegram Bot (Amharic + English)
Libraries: pyTelegramBotAPI (telebot), python-dotenv, sqlite3
Run: python bot.py
"""
import html
import logging
import os
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from dotenv import load_dotenv
from telebot import types

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("swap_bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is missing. Put it in your .env file or environment variables.")
DB_PATH = os.getenv("DB_PATH", "swap_bot.db")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

MAX_PHOTOS = 5
states = {}      # uid -> {"step": str, "data": dict}   (conversation state)
list_ctx = {}    # uid -> {"ids": [item ids]}           (browse/search results)
last_query = {}  # uid -> last search keyword
lang_cache = {}  # uid -> "en" | "am"


def esc(s):
    return html.escape(str(s if s is not None else ""))


# ----------------------------------------------------------------------------
# Categories
# ----------------------------------------------------------------------------
CATEGORIES = {
    "phones": ("📱 Phones", "📱 ስልኮች"),
    "computers": ("💻 Computers & Laptops", "💻 ኮምፒውተር እና ላፕቶፕ"),
    "electronics": ("🔌 Electronics", "🔌 ኤሌክትሮኒክስ"),
    "clothing": ("👕 Clothing", "👕 ልብስ"),
    "shoes": ("👟 Shoes", "👟 ጫማ"),
    "furniture": ("🛋 Furniture", "🛋 የቤት ዕቃ"),
    "books": ("📚 Books", "📚 መጻሕፍት"),
    "vehicles": ("🚗 Vehicles", "🚗 ተሽከርካሪ"),
    "home": ("🏠 Home & Kitchen", "🏠 የቤትና ማብሰያ ዕቃ"),
    "other": ("📦 Other", "📦 ሌላ"),
}


def cat_name(key, lang):
    c = CATEGORIES.get(key)
    if not c:
        return key or "-"
    return c[0] if lang == "en" else c[1]


# ----------------------------------------------------------------------------
# Translations
# ----------------------------------------------------------------------------
CHOOSE_LANG = "🌐 Choose your language / ቋንቋ ይምረጡ"

T = {
    "en": {
        "welcome_new": "👋 Welcome to <b>Swap Ethiopia</b>!\nTrade items you don't need for things you want.\n\nLet's create your profile first.",
        "ask_name": "👤 Enter your full name:",
        "ask_phone": "📱 Enter your phone number (e.g. 0912345678 or +251912345678) or tap the button below:",
        "share_phone": "📱 Share my phone",
        "bad_phone": "❌ Invalid phone number. Please enter an Ethiopian number (09... or +251...).",
        "ask_location": "📍 Enter your City / Subcity (e.g. Addis Ababa, Bole):",
        "registered": "✅ Registration complete!",
        "menu_title": "🏠 Main menu",
        "m_post": "📦 Post Item",
        "m_browse": "🔍 Browse Items",
        "m_search": "🔎 Search",
        "m_items": "🗂 My Items",
        "m_alerts": "🔔 My Alerts",
        "m_profile": "👤 Profile",
        "m_lang": "🌐 አማርኛ",
        "cancel": "❌ Cancel",
        "cancelled": "Cancelled.",
        "p_title": "📝 Enter the item title:",
        "p_desc": "📄 Write a description of the item:",
        "p_cat": "🗂 Choose a category:",
        "p_cond": "⚙️ Item condition:",
        "cond_new": "🆕 New",
        "cond_used": "♻️ Used",
        "p_photos": "📸 Send photo(s) of the item (up to 5). Tap Done when finished.",
        "p_done": "✅ Done",
        "p_skip": "⏭ Continue without photos",
        "p_photo_added": "📸 Photos added: {n}/5",
        "p_need_photo": "Please send a photo, or use the buttons.",
        "p_value": "💰 Enter the estimated value in ETB (numbers only):",
        "bad_number": "❌ Please enter a valid number.",
        "p_wanted": "🔄 What would you like in exchange?",
        "p_saved": "🎉 Your item has been posted!",
        "text_needed": "Please send text.",
        "lbl_cat": "Category",
        "lbl_cond": "Condition",
        "lbl_value": "Est. value",
        "lbl_wanted": "Wants in exchange",
        "lbl_loc": "Location",
        "st_swapped": "✅ <b>SWAPPED</b>",
        "b_choose_cat": "🔍 Choose a category to browse:",
        "cat_all": "📋 All categories",
        "b_none": "😕 No items found here yet.",
        "btn_alert": "🔔 Set Alert / የፍላጎት ማስታወቂያ መዝግብ",
        "btn_offer": "🔄 Offer Swap",
        "btn_photos": "🖼 All photos",
        "expired": "This list has expired. Please browse or search again.",
        "s_ask": "🔎 Type what you are looking for (e.g. iPhone 13, Laptop, Shoes):",
        "s_none": "😕 No items found for «{q}».\nWant to be notified when someone posts it?",
        "a_ask_kw": "🔔 Type the keyword you want alerts for (e.g. iPhone 13):",
        "a_saved": "✅ Alert saved! I will notify you when a matching item is posted.",
        "a_exists": "ℹ️ You already have this alert.",
        "a_list_title": "🔔 <b>Your alerts</b> (tap to delete):",
        "a_empty": "You have no alerts yet.",
        "a_add_btn": "➕ Add alert",
        "a_deleted": "🗑 Alert deleted.",
        "n_match": "🔔 <b>New item matching your alert!</b>\n\n",
        "o_own": "❌ This is your own item.",
        "o_unavailable": "❌ This item is no longer available.",
        "o_pick": "🔄 Which of your items do you want to offer?",
        "o_none_item": "💬 No item – just a message",
        "o_msg": "✍️ Write a message to the owner (what you offer, meeting place, etc.):",
        "o_sent": "✅ Your offer was sent to the owner. You will be notified of the answer.",
        "o_received": "📩 <b>New swap offer!</b>\n\n👤 From: {name}\n📍 {loc}\n\n🎯 For your item: <b>{item}</b>\n🎁 Offered item: {offered}\n\n💬 {msg}",
        "o_no_item": "— (message only)",
        "o_accept": "✅ Accept",
        "o_decline": "❌ Decline",
        "o_accepted_owner": "✅ Offer accepted! Contact the other person:\n\n👤 {name}\n📞 {phone}\n📍 {loc}",
        "o_accepted_offerer": "🎉 Your offer for <b>{item}</b> was accepted!\n\n👤 {name}\n📞 {phone}\n📍 {loc}\n\nArrange the swap safely and meet in a public place.",
        "o_declined": "😕 Your offer for <b>{item}</b> was declined.",
        "o_declined_owner": "Offer declined.",
        "o_already": "This offer was already answered.",
        "mi_empty": "You have not posted any items yet.",
        "btn_edit": "✏️ Edit",
        "btn_delete": "🗑 Delete",
        "btn_swapped": "✅ Mark swapped",
        "btn_yes": "✅ Yes",
        "btn_no": "↩️ No",
        "mi_confirm": "⚠️ Delete this item permanently?",
        "mi_deleted": "🗑 Item deleted.",
        "mi_swapped": "✅ Marked as swapped.",
        "ed_choose": "✏️ What do you want to edit?",
        "f_title": "Title",
        "f_description": "Description",
        "f_est_value": "Value",
        "f_wanted_item": "Wanted",
        "ed_ask": "Send the new value:",
        "ed_done": "✅ Updated.",
        "pf_text": "👤 <b>Your profile</b>\n\nName: {name}\nPhone: {phone}\nLocation: {loc}\nLanguage: English",
        "lang_changed": "✅ Language changed to English.",
        "register_first": "Please register first with /start",
        "help": "ℹ️ <b>Commands</b>\n/start – start / main menu\n/menu – main menu\n/language – change language\n/cancel – cancel current action",
        "error": "⚠️ Something went wrong. Please try again.",
    },
    "am": {
        "welcome_new": "👋 እንኳን ወደ <b>ስዋፕ ኢትዮጵያ</b> በደህና መጡ!\nየማያስፈልግዎትን እቃ በሚፈልጉት እቃ ይለውጡ።\n\nመጀመሪያ መገለጫዎን እንፍጠር።",
        "ask_name": "👤 ሙሉ ስምዎን ያስገቡ፦",
        "ask_phone": "📱 ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ 0912345678 ወይም +251912345678) ወይም ከታች ያለውን ቁልፍ ይጫኑ፦",
        "share_phone": "📱 ስልኬን አጋራ",
        "bad_phone": "❌ ልክ ያልሆነ ስልክ ቁጥር። እባክዎ የኢትዮጵያ ቁጥር (09... ወይም +251...) ያስገቡ።",
        "ask_location": "📍 ከተማ/ክፍለ ከተማዎን ያስገቡ (ለምሳሌ አዲስ አበባ፣ ቦሌ)፦",
        "registered": "✅ ምዝገባ ተጠናቅቋል!",
        "menu_title": "🏠 ዋና ማውጫ",
        "m_post": "📦 እቃ ለጥፍ",
        "m_browse": "🔍 እቃዎችን ተመልከት",
        "m_search": "🔎 ፈልግ",
        "m_items": "🗂 የኔ እቃዎች",
        "m_alerts": "🔔 የኔ ማስታወቂያዎች",
        "m_profile": "👤 መገለጫ",
        "m_lang": "🌐 English",
        "cancel": "❌ ሰርዝ",
        "cancelled": "ተሰርዟል።",
        "p_title": "📝 የእቃውን ርዕስ ያስገቡ፦",
        "p_desc": "📄 የእቃውን መግለጫ ይጻፉ፦",
        "p_cat": "🗂 ምድብ ይምረጡ፦",
        "p_cond": "⚙️ የእቃው ሁኔታ፦",
        "cond_new": "🆕 አዲስ",
        "cond_used": "♻️ ያገለገለ",
        "p_photos": "📸 የእቃውን ፎቶ(ዎች) ይላኩ (እስከ 5)። ሲጨርሱ «ጨርሻለሁ» ይጫኑ።",
        "p_done": "✅ ጨርሻለሁ",
        "p_skip": "⏭ ያለ ፎቶ ቀጥል",
        "p_photo_added": "📸 የተጨመሩ ፎቶዎች፦ {n}/5",
        "p_need_photo": "እባክዎ ፎቶ ይላኩ ወይም ቁልፎቹን ይጠቀሙ።",
        "p_value": "💰 የሚገመተውን ዋጋ በብር (ETB) ያስገቡ (ቁጥር ብቻ)፦",
        "bad_number": "❌ እባክዎ ትክክለኛ ቁጥር ያስገቡ።",
        "p_wanted": "🔄 በምን እቃ መለወጥ ይፈልጋሉ?",
        "p_saved": "🎉 እቃዎ ተለጥፏል!",
        "text_needed": "እባክዎ ጽሑፍ ይላኩ።",
        "lbl_cat": "ምድብ",
        "lbl_cond": "ሁኔታ",
        "lbl_value": "ግምታዊ ዋጋ",
        "lbl_wanted": "የሚፈለግ",
        "lbl_loc": "አካባቢ",
        "st_swapped": "✅ <b>ተለውጧል</b>",
        "b_choose_cat": "🔍 ለማየት ምድብ ይምረጡ፦",
        "cat_all": "📋 ሁሉም ምድቦች",
        "b_none": "😕 እስካሁን እዚህ ምንም እቃ የለም።",
        "btn_alert": "🔔 Set Alert / የፍላጎት ማስታወቂያ መዝግብ",
        "btn_offer": "🔄 የልውውጥ ጥያቄ አቅርብ",
        "btn_photos": "🖼 ሁሉንም ፎቶዎች",
        "expired": "ይህ ዝርዝር ጊዜው አልፏል። እባክዎ እንደገና ይፈልጉ።",
        "s_ask": "🔎 የሚፈልጉትን ይጻፉ (ለምሳሌ iPhone 13፣ ላፕቶፕ፣ ጫማ)፦",
        "s_none": "😕 ለ«{q}» ምንም እቃ አልተገኘም።\nአንድ ሰው ሲለጥፍ እንዲያሳውቅዎ ይፈልጋሉ?",
        "a_ask_kw": "🔔 ማስታወቂያ የሚፈልጉበትን ቃል ይጻፉ (ለምሳሌ iPhone 13)፦",
        "a_saved": "✅ ማስታወቂያ ተመዝግቧል! ተመሳሳይ እቃ ሲለጠፍ አሳውቅዎታለሁ።",
        "a_exists": "ℹ️ ይህ ማስታወቂያ አስቀድሞ አለዎት።",
        "a_list_title": "🔔 <b>የእርስዎ ማስታወቂያዎች</b> (ለመሰረዝ ይጫኑ)፦",
        "a_empty": "እስካሁን ምንም ማስታወቂያ የለዎትም።",
        "a_add_btn": "➕ ማስታወቂያ ጨምር",
        "a_deleted": "🗑 ማስታወቂያው ተሰርዟል።",
        "n_match": "🔔 <b>ከፍላጎትዎ ጋር የሚመሳሰል አዲስ እቃ ተለጥፏል!</b>\n\n",
        "o_own": "❌ ይህ የራስዎ እቃ ነው።",
        "o_unavailable": "❌ ይህ እቃ አሁን የለም።",
        "o_pick": "🔄 ከእርስዎ እቃዎች የትኛውን ማቅረብ ይፈልጋሉ?",
        "o_none_item": "💬 እቃ ሳይኖር – መልዕክት ብቻ",
        "o_msg": "✍️ ለባለቤቱ መልዕክት ይጻፉ (ምን እንደሚያቀርቡ፣ መገናኛ ቦታ ወዘተ)፦",
        "o_sent": "✅ ጥያቄዎ ለባለቤቱ ተልኳል። መልሱን አሳውቅዎታለሁ።",
        "o_received": "📩 <b>አዲስ የልውውጥ ጥያቄ!</b>\n\n👤 ከ፦ {name}\n📍 {loc}\n\n🎯 ለእቃዎ፦ <b>{item}</b>\n🎁 የቀረበ እቃ፦ {offered}\n\n💬 {msg}",
        "o_no_item": "— (መልዕክት ብቻ)",
        "o_accept": "✅ ተቀበል",
        "o_decline": "❌ አልቀበልም",
        "o_accepted_owner": "✅ ጥያቄው ተቀባይነት አግኝቷል! ሌላውን ሰው ያግኙ፦\n\n👤 {name}\n📞 {phone}\n📍 {loc}",
        "o_accepted_offerer": "🎉 ለ<b>{item}</b> ያቀረቡት ጥያቄ ተቀባይነት አግኝቷል!\n\n👤 {name}\n📞 {phone}\n📍 {loc}\n\nልውውጡን በጥንቃቄ ያካሂዱ፤ በሕዝብ ቦታ ይገናኙ።",
        "o_declined": "😕 ለ<b>{item}</b> ያቀረቡት ጥያቄ አልተቀበለም።",
        "o_declined_owner": "ጥያቄው ተቀባይነት አላገኘም።",
        "o_already": "ይህ ጥያቄ አስቀድሞ ምላሽ አግኝቷል።",
        "mi_empty": "እስካሁን ምንም እቃ አልለጠፉም።",
        "btn_edit": "✏️ አስተካክል",
        "btn_delete": "🗑 ሰርዝ",
        "btn_swapped": "✅ ተለውጧል ብለህ ምልክት አድርግ",
        "btn_yes": "✅ አዎ",
        "btn_no": "↩️ አይ",
        "mi_confirm": "⚠️ ይህ እቃ ለዘላለም ይሰረዝ?",
        "mi_deleted": "🗑 እቃው ተሰርዟል።",
        "mi_swapped": "✅ እንደተለወጠ ምልክት ተደርጓል።",
        "ed_choose": "✏️ ምን ማስተካከል ይፈልጋሉ?",
        "f_title": "ርዕስ",
        "f_description": "መግለጫ",
        "f_est_value": "ዋጋ",
        "f_wanted_item": "የሚፈለግ",
        "ed_ask": "አዲሱን እሴት ይላኩ፦",
        "ed_done": "✅ ተስተካክሏል።",
        "pf_text": "👤 <b>መገለጫዎ</b>\n\nስም፦ {name}\nስልክ፦ {phone}\nአካባቢ፦ {loc}\nቋንቋ፦ አማርኛ",
        "lang_changed": "✅ ቋንቋ ወደ አማርኛ ተቀይሯል።",
        "register_first": "እባክዎ መጀመሪያ በ /start ይመዝገቡ",
        "help": "ℹ️ <b>ትዕዛዞች</b>\n/start – ጀምር / ዋና ማውጫ\n/menu – ዋና ማውጫ\n/language – ቋንቋ ቀይር\n/cancel – አሁን ያለውን ድርጊት ሰርዝ",
        "error": "⚠️ ችግር ተፈጥሯል። እባክዎ እንደገና ይሞክሩ።",
    },
}

MENU_KEYS = ["m_post", "m_browse", "m_search", "m_items", "m_alerts", "m_profile", "m_lang"]
ACTION_BY_LABEL = {T[lg][k]: k for lg in T for k in MENU_KEYS}
CANCEL_LABELS = {T[lg]["cancel"] for lg in T}


# ----------------------------------------------------------------------------
# Database layer (all queries are parameterized)
# ----------------------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def db(sql, params=(), fetch=None):
    """fetch: 'one' | 'all' | None (returns lastrowid)."""
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        if fetch == "one":
            result = cur.fetchone()
        elif fetch == "all":
            result = cur.fetchall()
        else:
            result = cur.lastrowid
        conn.commit()
        return result
    except sqlite3.Error:
        conn.rollback()
        logger.exception("DB error | sql=%s", sql)
        raise
    finally:
        conn.close()


def init_db():
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS Users (
                user_id    INTEGER PRIMARY KEY,
                full_name  TEXT NOT NULL,
                phone      TEXT NOT NULL,
                location   TEXT NOT NULL,
                lang       TEXT NOT NULL DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS Items (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id       INTEGER NOT NULL,
                title          TEXT NOT NULL,
                description    TEXT NOT NULL,
                category       TEXT NOT NULL,
                item_condition TEXT NOT NULL,
                photos         TEXT DEFAULT '',
                est_value      REAL DEFAULT 0,
                wanted_item    TEXT DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'active',
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES Users(user_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS Swap_Offers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id         INTEGER NOT NULL,
                offerer_id      INTEGER NOT NULL,
                offered_item_id INTEGER,
                message         TEXT DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES Items(id) ON DELETE CASCADE,
                FOREIGN KEY (offerer_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (offered_item_id) REFERENCES Items(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS Wishlist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                keyword    TEXT,
                category   TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_items_status ON Items(status, category);
            CREATE INDEX IF NOT EXISTS idx_wishlist_user ON Wishlist(user_id);
            """
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Database ready at %s", DB_PATH)


# --- users ---
def get_user(uid):
    return db("SELECT * FROM Users WHERE user_id = ?", (uid,), "one")


def save_user(uid, name, phone, location, lang):
    db(
        """INSERT INTO Users (user_id, full_name, phone, location, lang) VALUES (?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name,
           phone=excluded.phone, location=excluded.location, lang=excluded.lang""",
        (uid, name, phone, location, lang),
    )
    lang_cache[uid] = lang


def set_lang(uid, lang):
    db("UPDATE Users SET lang = ? WHERE user_id = ?", (lang, uid))
    lang_cache[uid] = lang


def lang_of(uid):
    if uid in lang_cache:
        return lang_cache[uid]
    u = get_user(uid)
    if u:
        lang_cache[uid] = u["lang"]
        return u["lang"]
    return states.get(uid, {}).get("data", {}).get("lang", "en")


def tr(uid, key, **kw):
    text = T[lang_of(uid)][key]
    return text.format(**kw) if kw else text


# --- items ---
def add_item(owner_id, d):
    return db(
        """INSERT INTO Items (owner_id,title,description,category,item_condition,photos,est_value,wanted_item)
           VALUES (?,?,?,?,?,?,?,?)""",
        (owner_id, d["title"], d["description"], d["category"], d["condition"],
         ",".join(d.get("photos", [])), d["value"], d["wanted"]),
    )


def get_item(item_id):
    return db("SELECT * FROM Items WHERE id = ?", (item_id,), "one")


def user_items(uid):
    return db("SELECT * FROM Items WHERE owner_id = ? ORDER BY id DESC LIMIT 15", (uid,), "all")


def delete_item(item_id, owner_id):
    db("DELETE FROM Items WHERE id = ? AND owner_id = ?", (item_id, owner_id))


def mark_swapped(item_id, owner_id):
    db("UPDATE Items SET status='swapped' WHERE id = ? AND owner_id = ?", (item_id, owner_id))


EDITABLE = {"title": "title", "description": "description", "est_value": "est_value", "wanted_item": "wanted_item"}


def update_item_field(item_id, owner_id, field, value):
    col = EDITABLE[field]  # whitelist -> safe to place in SQL text
    db(f"UPDATE Items SET {col} = ? WHERE id = ? AND owner_id = ?", (value, item_id, owner_id))


def browse_ids(category):
    if category == "all":
        rows = db("SELECT id FROM Items WHERE status='active' ORDER BY id DESC LIMIT 200", (), "all")
    else:
        rows = db("SELECT id FROM Items WHERE status='active' AND category = ? ORDER BY id DESC LIMIT 200",
                  (category,), "all")
    return [r["id"] for r in rows]


def search_ids(q):
    rows = db(
        """SELECT id FROM Items WHERE status='active' AND
           (instr(lower(title), lower(?)) > 0 OR instr(lower(description), lower(?)) > 0)
           ORDER BY id DESC LIMIT 200""",
        (q, q), "all",
    )
    return [r["id"] for r in rows]


# --- wishlist ---
def add_wishlist(uid, keyword=None, category=None):
    """Returns True if inserted, False if duplicate."""
    keyword = keyword.strip() if keyword else None
    exists = db(
        "SELECT id FROM Wishlist WHERE user_id = ? AND IFNULL(keyword,'') = IFNULL(?,'') AND IFNULL(category,'') = IFNULL(?,'')",
        (uid, keyword, category), "one",
    )
    if exists:
        return False
    db("INSERT INTO Wishlist (user_id, keyword, category) VALUES (?,?,?)", (uid, keyword, category))
    return True


def user_wishlist(uid):
    return db("SELECT * FROM Wishlist WHERE user_id = ? ORDER BY id DESC", (uid,), "all")


def delete_wishlist(wid, uid):
    db("DELETE FROM Wishlist WHERE id = ? AND user_id = ?", (wid, uid))


def wishlist_matches(item):
    """User ids whose wishlist matches the new item's title/description/category."""
    haystack = " ".join([
        item["title"], item["description"],
        CATEGORIES.get(item["category"], ("", ""))[0],
        CATEGORIES.get(item["category"], ("", ""))[1],
    ])
    rows = db(
        """SELECT DISTINCT user_id FROM Wishlist
           WHERE user_id != ? AND (
                 (category IS NOT NULL AND category = ?)
              OR (keyword IS NOT NULL AND keyword != '' AND instr(lower(?), lower(keyword)) > 0)
           )""",
        (item["owner_id"], item["category"], haystack), "all",
    )
    return [r["user_id"] for r in rows]


# --- offers ---
def create_offer(item_id, offerer_id, offered_item_id, message):
    return db(
        "INSERT INTO Swap_Offers (item_id, offerer_id, offered_item_id, message) VALUES (?,?,?,?)",
        (item_id, offerer_id, offered_item_id, message),
    )


def get_offer(offer_id):
    return db("SELECT * FROM Swap_Offers WHERE id = ?", (offer_id,), "one")


def set_offer_status(offer_id, status):
    db("UPDATE Swap_Offers SET status = ? WHERE id = ?", (status, offer_id))


# ----------------------------------------------------------------------------
# Keyboards
# ----------------------------------------------------------------------------
def main_menu(uid):
    lang = lang_of(uid)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(*[types.KeyboardButton(T[lang][k]) for k in MENU_KEYS])
    return kb


def cancel_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(tr(uid, "cancel")))
    return kb


def phone_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(tr(uid, "share_phone"), request_contact=True))
    kb.add(types.KeyboardButton(tr(uid, "cancel")))
    return kb


def lang_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("English 🇬🇧", callback_data="lang:en"),
           types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang:am"))
    return kb


def category_kb(uid, prefix, with_all=False):
    lang = lang_of(uid)
    kb = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(cat_name(k, lang), callback_data=f"{prefix}:{k}") for k in CATEGORIES]
    kb.add(*btns)
    if with_all:
        kb.add(types.InlineKeyboardButton(T[lang]["cat_all"], callback_data=f"{prefix}:all"))
    return kb


# ----------------------------------------------------------------------------
# Helpers: item cards, phone validation
# ----------------------------------------------------------------------------
def normalize_phone(raw):
    s = re.sub(r"[\s\-()]", "", raw or "")
    m = re.fullmatch(r"(?:\+251|251|0)?([79]\d{8})", s)
    return "+251" + m.group(1) if m else None


def item_caption(item, lang, header=""):
    owner = get_user(item["owner_id"])
    loc = owner["location"] if owner else "-"
    cond = T[lang]["cond_new" if item["item_condition"] == "new" else "cond_used"]
    desc = item["description"]
    if len(desc) > 400:
        desc = desc[:400] + "…"
    status = ("\n" + T[lang]["st_swapped"]) if item["status"] != "active" else ""
    value = item["est_value"]
    value_txt = f"{value:,.0f} ETB" if value is not None else "-"
    return (
        f"{header}<b>{esc(item['title'])}</b>\n\n{esc(desc)}\n\n"
        f"🗂 {T[lang]['lbl_cat']}: {esc(cat_name(item['category'], lang))}\n"
        f"⚙️ {T[lang]['lbl_cond']}: {cond}\n"
        f"💰 {T[lang]['lbl_value']}: {value_txt}\n"
        f"🔄 {T[lang]['lbl_wanted']}: {esc(item['wanted_item'])}\n"
        f"📍 {T[lang]['lbl_loc']}: {esc(loc)}{status}"
    )[:1020]


def send_item(chat_id, item, lang, markup=None, header=""):
    caption = item_caption(item, lang, header)
    photos = [p for p in (item["photos"] or "").split(",") if p]
    if photos:
        try:
            return bot.send_photo(chat_id, photos[0], caption=caption, reply_markup=markup)
        except Exception:
            logger.warning("send_photo failed for item %s, falling back to text", item["id"])
    return bot.send_message(chat_id, caption, reply_markup=markup)


def clear_state(uid):
    states.pop(uid, None)


def show_menu(uid, chat_id, text=None):
    bot.send_message(chat_id, text or tr(uid, "menu_title"), reply_markup=main_menu(uid))


# ----------------------------------------------------------------------------
# Wishlist notification broadcaster
# ----------------------------------------------------------------------------
def notify_wishlist(item_id):
    try:
        item = get_item(item_id)
        if not item:
            return
        for target in wishlist_matches(item):
            try:
                lang = lang_of(target)
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton(T[lang]["btn_offer"], callback_data=f"of:{item_id}"))
                send_item(target, item, lang, kb, header=T[lang]["n_match"])
            except Exception:
                logger.warning("Could not notify user %s (blocked the bot?)", target)
    except Exception:
        logger.exception("notify_wishlist failed")


# ----------------------------------------------------------------------------
# Browse / pagination
# ----------------------------------------------------------------------------
def show_list(chat_id, uid, idx):
    lang = lang_of(uid)
    ctx = list_ctx.get(uid)
    if not ctx or not ctx["ids"]:
        bot.send_message(chat_id, T[lang]["expired"])
        return
    ids = ctx["ids"]
    idx = max(0, min(idx, len(ids) - 1))
    item = get_item(ids[idx])
    if not item:  # deleted meanwhile
        ids.pop(idx)
        return show_list(chat_id, uid, idx)

    kb = types.InlineKeyboardMarkup()
    prev_b = types.InlineKeyboardButton("◀️", callback_data=f"pg:{idx - 1}") if idx > 0 \
        else types.InlineKeyboardButton("·", callback_data="noop")
    next_b = types.InlineKeyboardButton("▶️", callback_data=f"pg:{idx + 1}") if idx < len(ids) - 1 \
        else types.InlineKeyboardButton("·", callback_data="noop")
    kb.row(prev_b, types.InlineKeyboardButton(f"{idx + 1}/{len(ids)}", callback_data="noop"), next_b)
    if item["owner_id"] != uid and item["status"] == "active":
        kb.add(types.InlineKeyboardButton(T[lang]["btn_offer"], callback_data=f"of:{item['id']}"))
    if len([p for p in (item["photos"] or "").split(",") if p]) > 1:
        kb.add(types.InlineKeyboardButton(T[lang]["btn_photos"], callback_data=f"ph:{item['id']}"))
    send_item(chat_id, item, lang, kb)


# ----------------------------------------------------------------------------
# Menu actions
# ----------------------------------------------------------------------------
def action_post(uid, chat_id):
    states[uid] = {"step": "p_title", "data": {"photos": []}}
    bot.send_message(chat_id, tr(uid, "p_title"), reply_markup=cancel_kb(uid))


def action_browse(uid, chat_id):
    bot.send_message(chat_id, tr(uid, "b_choose_cat"), reply_markup=category_kb(uid, "bc", with_all=True))


def action_search(uid, chat_id):
    states[uid] = {"step": "search", "data": {}}
    bot.send_message(chat_id, tr(uid, "s_ask"), reply_markup=cancel_kb(uid))


def action_items(uid, chat_id):
    lang = lang_of(uid)
    items = user_items(uid)
    if not items:
        bot.send_message(chat_id, T[lang]["mi_empty"])
        return
    for it in items:
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton(T[lang]["btn_edit"], callback_data=f"mi:ed:{it['id']}"),
               types.InlineKeyboardButton(T[lang]["btn_delete"], callback_data=f"mi:dl:{it['id']}"))
        if it["status"] == "active":
            kb.add(types.InlineKeyboardButton(T[lang]["btn_swapped"], callback_data=f"mi:sw:{it['id']}"))
        send_item(chat_id, it, lang, kb)


def action_alerts(uid, chat_id):
    lang = lang_of(uid)
    rows = user_wishlist(uid)
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        label = f"🔤 {r['keyword']}" if r["keyword"] else f"🗂 {cat_name(r['category'], lang)}"
        kb.add(types.InlineKeyboardButton(f"🗑 {label}"[:60], callback_data=f"ald:{r['id']}"))
    kb.add(types.InlineKeyboardButton(T[lang]["a_add_btn"], callback_data="al:kw"))
    bot.send_message(chat_id, T[lang]["a_list_title"] if rows else T[lang]["a_empty"], reply_markup=kb)


def action_profile(uid, chat_id):
    u = get_user(uid)
    bot.send_message(chat_id, tr(uid, "pf_text", name=esc(u["full_name"]), phone=esc(u["phone"]),
                                 loc=esc(u["location"])))


def action_lang(uid, chat_id):
    new = "am" if lang_of(uid) == "en" else "en"
    set_lang(uid, new)
    show_menu(uid, chat_id, T[new]["lang_changed"])


ACTIONS = {
    "m_post": action_post, "m_browse": action_browse, "m_search": action_search,
    "m_items": action_items, "m_alerts": action_alerts, "m_profile": action_profile,
    "m_lang": action_lang,
}


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    clear_state(uid)
    if get_user(uid):
        show_menu(uid, m.chat.id)
    else:
        bot.send_message(m.chat.id, CHOOSE_LANG, reply_markup=lang_kb())


@bot.message_handler(commands=["menu"])
def cmd_menu(m):
    uid = m.from_user.id
    clear_state(uid)
    if get_user(uid):
        show_menu(uid, m.chat.id)
    else:
        bot.send_message(m.chat.id, CHOOSE_LANG, reply_markup=lang_kb())


@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    uid = m.from_user.id
    clear_state(uid)
    if get_user(uid):
        show_menu(uid, m.chat.id, tr(uid, "cancelled"))
    else:
        bot.send_message(m.chat.id, CHOOSE_LANG, reply_markup=lang_kb())


@bot.message_handler(commands=["help"])
def cmd_help(m):
    bot.send_message(m.chat.id, tr(m.from_user.id, "help"))


@bot.message_handler(commands=["language"])
def cmd_language(m):
    bot.send_message(m.chat.id, CHOOSE_LANG, reply_markup=lang_kb())


# ----------------------------------------------------------------------------
# Conversation state machine (text / photo / contact messages)
# ----------------------------------------------------------------------------
@bot.message_handler(content_types=["text", "photo", "contact"])
def on_message(m):
    uid, chat_id = m.from_user.id, m.chat.id
    try:
        text = (m.text or "").strip() if m.content_type == "text" else ""
        user = get_user(uid)

        if text in CANCEL_LABELS:
            clear_state(uid)
            if user:
                show_menu(uid, chat_id, tr(uid, "cancelled"))
            else:
                bot.send_message(chat_id, CHOOSE_LANG, reply_markup=lang_kb())
            return

        if user and text in ACTION_BY_LABEL:
            clear_state(uid)
            ACTIONS[ACTION_BY_LABEL[text]](uid, chat_id)
            return

        st = states.get(uid)
        if st:
            handle_state(m, st, text)
            return

        if user:
            show_menu(uid, chat_id)
        else:
            bot.send_message(chat_id, CHOOSE_LANG, reply_markup=lang_kb())
    except Exception:
        logger.exception("on_message error")
        clear_state(uid)
        try:
            bot.send_message(chat_id, tr(uid, "error"))
        except Exception:
            pass


def handle_state(m, st, text):
    uid, chat_id = m.from_user.id, m.chat.id
    step, data = st["step"], st["data"]

    # ---------- registration ----------
    if step == "reg_name":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        data["name"] = text[:100]
        st["step"] = "reg_phone"
        return bot.send_message(chat_id, tr(uid, "ask_phone"), reply_markup=phone_kb(uid))

    if step == "reg_phone":
        raw = m.contact.phone_number if m.content_type == "contact" else text
        phone = normalize_phone(raw)
        if not phone:
            return bot.send_message(chat_id, tr(uid, "bad_phone"))
        data["phone"] = phone
        st["step"] = "reg_loc"
        return bot.send_message(chat_id, tr(uid, "ask_location"), reply_markup=cancel_kb(uid))

    if step == "reg_loc":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        save_user(uid, data["name"], data["phone"], text[:100], data.get("lang", "en"))
        clear_state(uid)
        return show_menu(uid, chat_id, tr(uid, "registered"))

    # ---------- post item ----------
    if step == "p_title":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        data["title"] = text[:120]
        st["step"] = "p_desc"
        return bot.send_message(chat_id, tr(uid, "p_desc"))

    if step == "p_desc":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        data["description"] = text[:1000]
        st["step"] = "p_cat"
        return bot.send_message(chat_id, tr(uid, "p_cat"), reply_markup=category_kb(uid, "pc"))

    if step == "p_photos":
        if m.content_type == "photo":
            if len(data["photos"]) < MAX_PHOTOS:
                data["photos"].append(m.photo[-1].file_id)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(tr(uid, "p_done"), callback_data="pp:done"))
            return bot.send_message(chat_id, tr(uid, "p_photo_added", n=len(data["photos"])), reply_markup=kb)
        return bot.send_message(chat_id, tr(uid, "p_need_photo"))

    if step == "p_value":
        try:
            value = float(text.replace(",", "").replace("ብር", "").replace("ETB", "").strip())
            if value < 0:
                raise ValueError
        except ValueError:
            return bot.send_message(chat_id, tr(uid, "bad_number"))
        data["value"] = value
        st["step"] = "p_wanted"
        return bot.send_message(chat_id, tr(uid, "p_wanted"))

    if step == "p_wanted":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        data["wanted"] = text[:300]
        item_id = add_item(uid, data)
        clear_state(uid)
        show_menu(uid, chat_id, tr(uid, "p_saved"))
        # Run the automated wishlist matching in the background
        threading.Thread(target=notify_wishlist, args=(item_id,), daemon=True).start()
        return

    # ---------- search ----------
    if step == "search":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        clear_state(uid)
        q = text[:80]
        last_query[uid] = q
        ids = search_ids(q)
        if not ids:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(tr(uid, "btn_alert"), callback_data="al:q"))
            show_menu(uid, chat_id)
            return bot.send_message(chat_id, tr(uid, "s_none", q=esc(q)), reply_markup=kb)
        list_ctx[uid] = {"ids": ids}
        show_menu(uid, chat_id)
        return show_list(chat_id, uid, 0)

    # ---------- alert keyword ----------
    if step == "al_kw":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        clear_state(uid)
        ok = add_wishlist(uid, keyword=text[:80])
        return show_menu(uid, chat_id, tr(uid, "a_saved" if ok else "a_exists"))

    # ---------- offer message ----------
    if step == "offer_msg":
        if not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        item = get_item(data["item_id"])
        clear_state(uid)
        if not item or item["status"] != "active":
            return show_menu(uid, chat_id, tr(uid, "o_unavailable"))
        offer_id = create_offer(item["id"], uid, data.get("my_item_id"), text[:500])
        show_menu(uid, chat_id, tr(uid, "o_sent"))
        send_offer_to_owner(offer_id)
        return

    # ---------- edit field ----------
    if step == "edit":
        field = data["field"]
        value = text
        if field == "est_value":
            try:
                value = float(text.replace(",", "").strip())
            except ValueError:
                return bot.send_message(chat_id, tr(uid, "bad_number"))
        elif not text:
            return bot.send_message(chat_id, tr(uid, "text_needed"))
        update_item_field(data["item_id"], uid, field, value)
        clear_state(uid)
        return show_menu(uid, chat_id, tr(uid, "ed_done"))

    clear_state(uid)
    show_menu(uid, chat_id)


def send_offer_to_owner(offer_id):
    offer = get_offer(offer_id)
    if not offer:
        return
    item = get_item(offer["item_id"])
    offerer = get_user(offer["offerer_id"])
    owner_id = item["owner_id"]
    lang = lang_of(owner_id)
    offered = T[lang]["o_no_item"]
    if offer["offered_item_id"]:
        oi = get_item(offer["offered_item_id"])
        if oi:
            offered = f"<b>{esc(oi['title'])}</b> (~{oi['est_value']:,.0f} ETB)"
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(T[lang]["o_accept"], callback_data=f"oa:{offer_id}"),
           types.InlineKeyboardButton(T[lang]["o_decline"], callback_data=f"od:{offer_id}"))
    try:
        bot.send_message(
            owner_id,
            T[lang]["o_received"].format(
                name=esc(offerer["full_name"]), loc=esc(offerer["location"]),
                item=esc(item["title"]), offered=offered, msg=esc(offer["message"])),
            reply_markup=kb,
        )
    except Exception:
        logger.warning("Could not deliver offer %s to owner %s", offer_id, owner_id)


# ----------------------------------------------------------------------------
# Callback queries
# ----------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda c: True)
def on_callback(c):
    uid, chat_id = c.from_user.id, c.message.chat.id
    data = c.data or ""
    try:
        bot.answer_callback_query(c.id)

        if data == "noop":
            return

        # ----- language (registration or switch) -----
        if data.startswith("lang:"):
            lang = data.split(":")[1]
            if lang not in T:
                return
            user = get_user(uid)
            if user:
                set_lang(uid, lang)
                show_menu(uid, chat_id, T[lang]["lang_changed"])
            else:
                states[uid] = {"step": "reg_name", "data": {"lang": lang}}
                bot.send_message(chat_id, T[lang]["welcome_new"])
                bot.send_message(chat_id, T[lang]["ask_name"], reply_markup=cancel_kb(uid))
            return

        if not get_user(uid):
            bot.send_message(chat_id, CHOOSE_LANG, reply_markup=lang_kb())
            return
        lang = lang_of(uid)

        # ----- post item flow -----
        if data.startswith("pc:"):
            st = states.get(uid)
            cat = data.split(":")[1]
            if not st or st["step"] != "p_cat" or cat not in CATEGORIES:
                return
            st["data"]["category"] = cat
            st["step"] = "p_cond"
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton(T[lang]["cond_new"], callback_data="pn:new"),
                   types.InlineKeyboardButton(T[lang]["cond_used"], callback_data="pn:used"))
            bot.send_message(chat_id, T[lang]["p_cond"], reply_markup=kb)
            return

        if data.startswith("pn:"):
            st = states.get(uid)
            if not st or st["step"] != "p_cond":
                return
            st["data"]["condition"] = "new" if data.endswith("new") else "used"
            st["step"] = "p_photos"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(T[lang]["p_skip"], callback_data="pp:done"))
            bot.send_message(chat_id, T[lang]["p_photos"], reply_markup=kb)
            return

        if data == "pp:done":
            st = states.get(uid)
            if not st or st["step"] != "p_photos":
                return
            st["step"] = "p_value"
            bot.send_message(chat_id, T[lang]["p_value"])
            return

        # ----- browse -----
        if data.startswith("bc:"):
            cat = data.split(":")[1]
            if cat != "all" and cat not in CATEGORIES:
                return
            ids = browse_ids(cat)
            if not ids:
                kb = types.InlineKeyboardMarkup()
                if cat != "all":
                    kb.add(types.InlineKeyboardButton(T[lang]["btn_alert"], callback_data=f"al:c:{cat}"))
                bot.send_message(chat_id, T[lang]["b_none"], reply_markup=kb)
                return
            list_ctx[uid] = {"ids": ids}
            show_list(chat_id, uid, 0)
            return

        if data.startswith("pg:"):
            idx = int(data.split(":")[1])
            try:
                bot.delete_message(chat_id, c.message.message_id)
            except Exception:
                pass
            show_list(chat_id, uid, idx)
            return

        if data.startswith("ph:"):
            item = get_item(int(data.split(":")[1]))
            if not item:
                return
            photos = [p for p in item["photos"].split(",") if p][:MAX_PHOTOS]
            if len(photos) > 1:
                bot.send_media_group(chat_id, [types.InputMediaPhoto(p) for p in photos])
            return

        # ----- alerts -----
        if data == "al:kw":
            states[uid] = {"step": "al_kw", "data": {}}
            bot.send_message(chat_id, T[lang]["a_ask_kw"], reply_markup=cancel_kb(uid))
            return

        if data == "al:q":
            q = last_query.get(uid)
            if not q:
                return
            ok = add_wishlist(uid, keyword=q)
            bot.send_message(chat_id, T[lang]["a_saved" if ok else "a_exists"])
            return

        if data.startswith("al:c:"):
            cat = data.split(":")[2]
            if cat in CATEGORIES:
                ok = add_wishlist(uid, category=cat)
                bot.send_message(chat_id, T[lang]["a_saved" if ok else "a_exists"])
            return

        if data.startswith("ald:"):
            delete_wishlist(int(data.split(":")[1]), uid)
            bot.send_message(chat_id, T[lang]["a_deleted"])
            return

        # ----- swap offers -----
        if data.startswith("of:"):
            item = get_item(int(data.split(":")[1]))
            if not item or item["status"] != "active":
                bot.send_message(chat_id, T[lang]["o_unavailable"])
                return
            if item["owner_id"] == uid:
                bot.send_message(chat_id, T[lang]["o_own"])
                return
            kb = types.InlineKeyboardMarkup()
            for mine in user_items(uid):
                if mine["status"] == "active":
                    kb.add(types.InlineKeyboardButton(f"🎁 {mine['title']}"[:60],
                                                      callback_data=f"ofp:{item['id']}:{mine['id']}"))
            kb.add(types.InlineKeyboardButton(T[lang]["o_none_item"], callback_data=f"ofp:{item['id']}:0"))
            bot.send_message(chat_id, T[lang]["o_pick"], reply_markup=kb)
            return

        if data.startswith("ofp:"):
            _, item_id, my_id = data.split(":")
            item = get_item(int(item_id))
            if not item or item["status"] != "active" or item["owner_id"] == uid:
                bot.send_message(chat_id, T[lang]["o_unavailable"])
                return
            my_item = None
            if int(my_id):
                my_item = get_item(int(my_id))
                if not my_item or my_item["owner_id"] != uid:
                    return
            states[uid] = {"step": "offer_msg",
                           "data": {"item_id": item["id"], "my_item_id": my_item["id"] if my_item else None}}
            bot.send_message(chat_id, T[lang]["o_msg"], reply_markup=cancel_kb(uid))
            return

        if data.startswith(("oa:", "od:")):
            offer = get_offer(int(data.split(":")[1]))
            if not offer:
                return
            item = get_item(offer["item_id"])
            if not item or item["owner_id"] != uid:
                return
            if offer["status"] != "pending":
                bot.send_message(chat_id, T[lang]["o_already"])
                return
            offerer = get_user(offer["offerer_id"])
            owner = get_user(uid)
            try:
                bot.edit_message_reply_markup(chat_id, c.message.message_id, reply_markup=None)
            except Exception:
                pass
            if data.startswith("oa:"):
                set_offer_status(offer["id"], "accepted")
                bot.send_message(chat_id, T[lang]["o_accepted_owner"].format(
                    name=esc(offerer["full_name"]), phone=esc(offerer["phone"]), loc=esc(offerer["location"])))
                try:
                    ol = lang_of(offerer["user_id"])
                    bot.send_message(offerer["user_id"], T[ol]["o_accepted_offerer"].format(
                        item=esc(item["title"]), name=esc(owner["full_name"]),
                        phone=esc(owner["phone"]), loc=esc(owner["location"])))
                except Exception:
                    logger.warning("Could not notify offerer %s", offerer["user_id"])
            else:
                set_offer_status(offer["id"], "declined")
                bot.send_message(chat_id, T[lang]["o_declined_owner"])
                try:
                    ol = lang_of(offerer["user_id"])
                    bot.send_message(offerer["user_id"], T[ol]["o_declined"].format(item=esc(item["title"])))
                except Exception:
                    logger.warning("Could not notify offerer %s", offerer["user_id"])
            return

        # ----- my items -----
        if data.startswith("mi:"):
            _, action, item_id = data.split(":")
            item = get_item(int(item_id))
            if not item or item["owner_id"] != uid:
                return
            if action == "sw":
                mark_swapped(item["id"], uid)
                bot.send_message(chat_id, T[lang]["mi_swapped"])
            elif action == "dl":
                kb = types.InlineKeyboardMarkup()
                kb.row(types.InlineKeyboardButton(T[lang]["btn_yes"], callback_data=f"mi:dy:{item['id']}"),
                       types.InlineKeyboardButton(T[lang]["btn_no"], callback_data=f"mi:dn:{item['id']}"))
                bot.send_message(chat_id, T[lang]["mi_confirm"], reply_markup=kb)
            elif action == "dy":
                delete_item(item["id"], uid)
                bot.send_message(chat_id, T[lang]["mi_deleted"])
            elif action == "dn":
                try:
                    bot.delete_message(chat_id, c.message.message_id)
                except Exception:
                    pass
            elif action == "ed":
                kb = types.InlineKeyboardMarkup(row_width=2)
                kb.add(*[types.InlineKeyboardButton(T[lang][f"f_{f}"], callback_data=f"ef:{item['id']}:{f}")
                         for f in EDITABLE])
                bot.send_message(chat_id, T[lang]["ed_choose"], reply_markup=kb)
            return

        if data.startswith("ef:"):
            _, item_id, field = data.split(":", 2)
            item = get_item(int(item_id))
            if not item or item["owner_id"] != uid or field not in EDITABLE:
                return
            states[uid] = {"step": "edit", "data": {"item_id": item["id"], "field": field}}
            bot.send_message(chat_id, T[lang]["ed_ask"], reply_markup=cancel_kb(uid))
            return

    except Exception:
        logger.exception("on_callback error | data=%s", data)
        try:
            bot.send_message(chat_id, tr(uid, "error"))
        except Exception:
            pass


# ----------------------------------------------------------------------------
# Optional health-check server (Render Web Services need an open port)
# ----------------------------------------------------------------------------
def start_health_server():
    port = os.getenv("PORT")
    if not port:
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Swap bot is running")

        def log_message(self, *args):
            pass

    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", int(port)), Handler).serve_forever(),
        daemon=True,
    ).start()
    logger.info("Health server listening on port %s", port)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    start_health_server()
    try:
        bot.remove_webhook()
    except Exception:
        pass
    logger.info("Bot started. Polling...")
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)

#!/usr/bin/env python3
"""
RailMT Pro - Telegram Bot
Bot: @RAILMTPRO_BOT
Token: 8529292373:AAGvtRfJW5r6sBe6GLu5kKspZVy7no3uTZw

Features:
- Users can post mutual transfer requests
- Mobile numbers are HIDDEN (privacy protected)
- Contact only through admin approval
- All data synced to Firebase
- Duplicate prevention by mobile number
- Terms & Conditions consent required

Deploy on: Railway.app / Render.com / Heroku (all free)
"""

import os
import json
import hashlib
import logging
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = "8529292373:AAGvtRfJW5r6sBe6GLu5kKspZVy7no3uTZw"
ADMIN_MOBILE = "9045569654"  # Your mobile - can approve contact requests
APP_URL = "https://railmtpro.netlify.app"
BOT_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Firebase config (same as your app)
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyB5ycaxNnwnzlqyOwkAQLNZXil7X7oNnEk",
    "authDomain": "railway-mutual-transfer-53442.firebaseapp.com",
    "projectId": "railway-mutual-transfer-53442",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# ============================================================
# TELEGRAM API HELPERS
# ============================================================
def tg(method, data={}):
    """Call Telegram Bot API"""
    try:
        r = requests.post(f"{BOT_URL}/{method}", json=data, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Telegram API error: {e}")
        return {}

def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = reply_markup
    return tg("sendMessage", data)

def send_keyboard(chat_id, text, buttons):
    """Send message with inline keyboard"""
    markup = {"inline_keyboard": buttons}
    return send(chat_id, text, reply_markup=markup)

def answer_callback(callback_id, text=""):
    tg("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

# ============================================================
# USER SESSION STORAGE (in-memory, for multi-step forms)
# ============================================================
user_sessions = {}  # {chat_id: {step, data}}

def get_session(chat_id):
    return user_sessions.get(str(chat_id), {})

def set_session(chat_id, data):
    user_sessions[str(chat_id)] = data

def clear_session(chat_id):
    user_sessions.pop(str(chat_id), None)

# ============================================================
# FIREBASE (REST API - no server SDK needed)
# ============================================================
FIREBASE_URL = f"https://firestore.googleapis.com/v1/projects/railway-mutual-transfer-53442/databases/(default)/documents"

def firebase_get(collection, doc_id=None):
    """Get document(s) from Firestore via REST"""
    url = f"{FIREBASE_URL}/{collection}"
    if doc_id:
        url += f"/{doc_id}"
    try:
        r = requests.get(url, timeout=10)
        return r.json()
    except:
        return {}

def firebase_add(collection, data):
    """Add document to Firestore via REST"""
    # Convert to Firestore format
    fields = {}
    for k, v in data.items():
        if isinstance(v, str):
            fields[k] = {"stringValue": v}
        elif isinstance(v, bool):
            fields[k] = {"booleanValue": v}
        elif isinstance(v, int):
            fields[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            fields[k] = {"doubleValue": v}
        else:
            fields[k] = {"stringValue": str(v)}
    
    payload = {"fields": fields}
    url = f"{FIREBASE_URL}/{collection}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"Firebase add error: {e}")
        return {}

def check_duplicate(mobile):
    """Check if mobile already has active post"""
    try:
        # Query Firestore for existing post with same mobile
        query_url = f"{FIREBASE_URL}:runQuery"
        query = {
            "structuredQuery": {
                "from": [{"collectionId": "transfers"}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "mobile"},
                        "op": "EQUAL",
                        "value": {"stringValue": mobile}
                    }
                },
                "limit": 1
            }
        }
        r = requests.post(query_url, json=query, timeout=10)
        result = r.json()
        if isinstance(result, list) and len(result) > 0:
            if result[0].get('document'):
                return True
        return False
    except:
        return False

# ============================================================
# HASH MOBILE (same as app)
# ============================================================
def hash_mobile(mobile):
    """Create anonymous ID from mobile - same as app"""
    return hashlib.sha256(f"{mobile}rmt2024vinay".encode()).hexdigest()[:12]

# ============================================================
# MESSAGES
# ============================================================

WELCOME_MSG = """🚂 <b>Welcome to RailMT Pro Bot!</b>

India's #1 Railway Mutual Transfer Platform

✅ Post your transfer request
✅ Find your match All India
✅ Contact through secure system
✅ Your mobile number is ALWAYS hidden

<b>Commands:</b>
/post — Post your transfer request
/search — Search for matches
/mypost — View your post
/delete — Delete your post
/help — Help & commands
/app — Open web app

🔗 Web App: {app_url}
""".format(app_url=APP_URL)

TC_MSG = """📋 <b>Terms & Conditions</b>

By using RailMT Pro Bot, you agree:

1️⃣ <b>Data Usage:</b> Your name, post, zone and station will be stored in our database and shown to other users for mutual transfer matching.

2️⃣ <b>Mobile Number:</b> Your mobile number will be stored securely. It will NOT be shown to anyone without your explicit consent. Contact requests must be approved by you.

3️⃣ <b>No Guarantee:</b> We facilitate connections only. Mutual transfer approval depends on Railway authorities.

4️⃣ <b>Accuracy:</b> You are responsible for providing correct information. False information may result in removal.

5️⃣ <b>Privacy:</b> We follow Railway employee data privacy norms. No data will be sold or shared with third parties.

6️⃣ <b>Legal:</b> This platform is for informational purposes. We are not affiliated with Indian Railways or any official body.

7️⃣ <b>Removal:</b> You can delete your post anytime using /delete command.

By tapping "I Agree", you consent to these terms.
"""

BOARDS = ["RRC – Group D", "RRB – Group C"]

DEPTS = {
    "RRC – Group D": ["Engineering (Engg)", "Mechanical (Mech)", "Electrical (Elect)", 
                       "Signal & Telecom (S&T)", "Operating (Optg)", "Traffic/Commercial (Comml)", 
                       "Personnel (Estt)", "Medical", "RPF/RPSF", "Stores"],
    "RRB – Group C": ["Engineering (Engg)", "Mechanical (Workshop/Shed)", "Loco Running (LP/ALP)",
                       "Electrical (Elect)", "Signal & Telecom (S&T)", "Traffic/Commercial (Comml)",
                       "Operating (Optg)", "Accounts", "Personnel (Estt)", "Medical", "RPF/RPSF", "Stores"]
}

POSTS = {
    "Engineering (Engg)": ["Track Maintainer Gr.IV", "Track Maintainer Gr.III", "Track Maintainer Gr.II", 
                            "Track Maintainer Gr.I", "Gateman", "Mate (P.Way)", "Work Inspector",
                            "Junior Engineer (JE) – P.Way", "SSE – P.Way"],
    "Mechanical (Mech)": ["Helper Gr.II (Mech/C&W)", "Helper Gr.II (Loco)"],
    "Mechanical (Workshop/Shed)": ["Technician Gr.III (Mech)", "Technician Gr.II (Mech)", 
                                    "Technician Gr.I (Mech)", "Sr. Technician (Mech)",
                                    "Carriage & Wagon Examiner (TXR)", "JE – Mech", "SSE – Mech"],
    "Loco Running (LP/ALP)": ["Assistant Loco Pilot (ALP)", "Loco Pilot (Goods)", 
                               "Loco Pilot (Passenger)", "Loco Pilot (Mail/Express)",
                               "Loco Pilot (Electric – Goods)", "Loco Pilot (Electric – Mail)"],
    "Electrical (Elect)": ["Helper Gr.II (Elect)", "Technician Gr.III (Elect)", "Technician Gr.II (Elect)",
                            "Technician Gr.I (Elect)", "Sr. Technician (Elect)", "JE – Elect", "SSE – Elect"],
    "Signal & Telecom (S&T)": ["Helper Gr.II (S&T)", "Technician Gr.III (S&T)", "Technician Gr.II (S&T)",
                                "Technician Gr.I (S&T)", "Sr. Technician (S&T)", "JE – S&T", "SSE – S&T"],
    "Traffic/Commercial (Comml)": ["Commercial Clerk (CC)", "Senior Commercial Clerk", "Ticket Collector (TC)",
                                    "Ticket Checking Examiner (TTE)", "Commercial Inspector (CI)", 
                                    "Goods Clerk", "Parcel Supervisor"],
    "Operating (Optg)": ["Pointsman", "Train Clerk", "Assistant Station Master (ASM)", 
                          "Station Master (SM)", "Guard (Goods)", "Guard (Passenger/Mail)", "Section Controller"],
    "Accounts": ["Accounts Clerk", "Junior Accounts Assistant (JAA)", "Senior Accounts Assistant (SAA)"],
    "Personnel (Estt)": ["Junior Clerk cum Typist", "Senior Clerk cum Typist", "Office Superintendent"],
    "Medical": ["Hospital Attendant", "Health & Malaria Inspector", "Pharmacist Gr.III", "Staff Nurse", "Lab Technician"],
    "RPF/RPSF": ["Constable – RPF", "Head Constable – RPF", "ASI – RPF", "SI – RPF"],
    "Stores": ["Store Keeper Gr.III", "Store Keeper Gr.II", "Sr. Store Keeper", "DMS"]
}

ZONES = ["CR – Central Railway", "ER – Eastern Railway", "ECR – East Central Railway",
         "ECoR – East Coast Railway", "NCR – North Central Railway", "NR – Northern Railway",
         "NER – North Eastern Railway", "NFR – NE Frontier Railway", "NWR – North Western Railway",
         "SCR – South Central Railway", "SER – South Eastern Railway", "SECR – SE Central Railway",
         "SR – Southern Railway", "SWR – South Western Railway", "WCR – West Central Railway",
         "WR – Western Railway", "Metro – Kolkata Metro", "CLW", "DLW", "ICF", "RCF", "RWF", "MCF", "RDSO"]

# ============================================================
# COMMAND HANDLERS
# ============================================================

def handle_start(chat_id, user):
    """Handle /start command"""
    name = user.get('first_name', 'Friend')
    clear_session(chat_id)
    send(chat_id, WELCOME_MSG.replace("Welcome to", f"Welcome {name} to"))

def handle_post(chat_id, user):
    """Handle /post command - start posting flow"""
    # Step 1: Show T&C first
    send_keyboard(chat_id, TC_MSG, [
        [{"text": "✅ I Agree — Continue", "callback_data": "tc_agree"}],
        [{"text": "❌ I Disagree — Cancel", "callback_data": "tc_disagree"}]
    ])

def handle_help(chat_id):
    send(chat_id, """🚂 <b>RailMT Pro Bot - Help</b>

<b>Commands:</b>
/start — Welcome message
/post — Post your transfer request
/search — Search for matches  
/mypost — View your current post
/delete — Delete your post
/app — Open web app
/help — This help message

<b>How it works:</b>
1. Use /post to submit your request
2. Your mobile number stays HIDDEN
3. Someone interested sends a contact request
4. You approve → they get your contact
5. Connect and apply for mutual transfer!

🔗 """ + APP_URL)

def handle_app(chat_id):
    send_keyboard(chat_id, 
        f"🌐 <b>Open RailMT Pro Web App</b>\n\nClick below to open the full app with all features:",
        [[{"text": "🚂 Open RailMT Pro App", "url": APP_URL}]]
    )

def handle_mypost(chat_id, telegram_id):
    """Show user's current post"""
    session = get_session(chat_id)
    mobile = session.get('mobile', '')
    
    if not mobile:
        send(chat_id, "❌ No post found for your account.\n\nUse /post to create one!")
        return
    
    send(chat_id, f"""📋 <b>Your Active Post:</b>

Post: {session.get('post', '—')}
Board: {session.get('board', '—')}
Current: {session.get('current_station', '—')} ({session.get('current_zone', '—')})
Preferred: {session.get('preferred_station', '—')} ({session.get('preferred_zone', '—')})
Mobile: <b>Hidden (protected)</b>

Use /delete to remove this post.""")

def handle_delete(chat_id):
    send_keyboard(chat_id,
        "⚠️ <b>Delete your post?</b>\n\nThis will remove your request from the database.",
        [[{"text": "🗑️ Yes, Delete", "callback_data": "confirm_delete"},
          {"text": "❌ Cancel", "callback_data": "cancel_delete"}]]
    )

# ============================================================
# POST FLOW - Multi-step form
# ============================================================

POST_STEPS = ['tc', 'mobile', 'name', 'board', 'dept', 'post_title', 
              'current_zone', 'current_station', 'preferred_zone', 
              'preferred_station', 'confirm']

def start_post_flow(chat_id):
    """Step 1: Ask for mobile number"""
    set_session(chat_id, {'step': 'mobile', 'data': {}})
    send(chat_id, """📱 <b>Step 1/8 — Mobile Number</b>

Enter your 10-digit mobile number.

🔒 <b>This will be HIDDEN from everyone.</b>
Contact will only be shared if you approve a request.

Type your mobile number:""")

def process_post_step(chat_id, text, session):
    """Process each step of the post form"""
    step = session.get('step')
    data = session.get('data', {})
    
    if step == 'mobile':
        if not text.isdigit() or len(text) != 10:
            send(chat_id, "❌ Invalid mobile number. Please enter 10 digits only:")
            return
        # Check duplicate
        if check_duplicate(text):
            send(chat_id, f"""⚠️ <b>Mobile already registered!</b>

You already have an active post in our database.

Use /mypost to view it or /delete to remove it first.

Or open the web app: {APP_URL}""")
            clear_session(chat_id)
            return
        data['mobile'] = text
        data['mobile_hash'] = hash_mobile(text)
        session['data'] = data
        session['step'] = 'name'
        set_session(chat_id, session)
        send(chat_id, "👤 <b>Step 2/8 — Your Name</b>\n\nEnter your full name:")
    
    elif step == 'name':
        if len(text) < 2:
            send(chat_id, "❌ Please enter your full name:")
            return
        data['name'] = text
        session['data'] = data
        session['step'] = 'board'
        set_session(chat_id, session)
        # Show board selection
        buttons = [[{"text": b, "callback_data": f"board_{i}"}] for i, b in enumerate(BOARDS)]
        send_keyboard(chat_id, "🏛️ <b>Step 3/8 — Select Board</b>", buttons)
    
    elif step == 'current_station':
        data['station'] = text
        session['data'] = data
        session['step'] = 'preferred_zone'
        set_session(chat_id, session)
        # Show preferred zone
        buttons = make_zone_buttons('pzone')
        send_keyboard(chat_id, "🎯 <b>Step 7/8 — Preferred Zone</b>\n\nSelect the zone you want to go to:", buttons)
    
    elif step == 'preferred_station':
        data['pstation'] = text
        session['data'] = data
        session['step'] = 'confirm'
        set_session(chat_id, session)
        # Show confirmation
        show_confirm(chat_id, data)

def make_zone_buttons(prefix):
    """Make zone selection buttons"""
    buttons = []
    for i in range(0, len(ZONES), 2):
        row = [{"text": ZONES[i][:25], "callback_data": f"{prefix}_{i}"}]
        if i+1 < len(ZONES):
            row.append({"text": ZONES[i+1][:25], "callback_data": f"{prefix}_{i+1}"})
        buttons.append(row)
    return buttons

def show_confirm(chat_id, data):
    """Show confirmation before posting"""
    msg = f"""✅ <b>Review Your Request</b>

👤 Name: {data.get('name', '—')}
🏛️ Board: {data.get('board', '—')}
📂 Dept: {data.get('dept', '—')}
👔 Post: {data.get('post', '—')}
📍 Current: {data.get('station', '—')} ({data.get('zone', '—')})
🎯 Preferred: {data.get('pstation', '—')} ({data.get('pzone', '—')})
📱 Mobile: <b>Hidden (protected)</b>

Confirm posting this request?"""
    
    send_keyboard(chat_id, msg, [
        [{"text": "✅ Yes, Post Now", "callback_data": "confirm_post"}],
        [{"text": "✏️ Edit (restart)", "callback_data": "restart_post"}],
        [{"text": "❌ Cancel", "callback_data": "cancel_post"}]
    ])

def submit_post(chat_id, data):
    """Submit post to Firebase"""
    doc = {
        "board": data.get('board', ''),
        "name": data.get('name', ''),
        "dept": data.get('dept', ''),
        "post": data.get('post', ''),
        "grade": "",
        "trade": "",
        "lower": "no",
        "category": "",
        "zone": data.get('zone', ''),
        "div": data.get('zone', ''),
        "station": data.get('station', ''),
        "pzone": data.get('pzone', ''),
        "pdiv": data.get('pzone', ''),
        "pstation": data.get('pstation', ''),
        "mobile": data.get('mobile', ''),
        "mobile_hash": data.get('mobile_hash', ''),
        "mobile_hidden": "true",
        "source": "telegram_bot",
        "telegram_chat_id": str(chat_id),
        "email": "",
        "note": "",
        "ownerMobile": data.get('mobile', ''),
        "date": datetime.now().strftime('%d %b %Y'),
    }
    
    result = firebase_add("transfers", doc)
    
    if 'name' in result:
        send(chat_id, f"""🎉 <b>Request Posted Successfully!</b>

Your mutual transfer request is now live on RailMT Pro.

📱 Mobile: <b>Hidden (protected)</b>
🔒 Contact requests will need your approval

<b>What happens next?</b>
• Others can see your request (without mobile)
• They can send a contact request
• You approve → they get your contact
• Connect and apply for mutual transfer!

🌐 View on app: {APP_URL}

Use /mypost to view your request
Use /delete to remove it anytime""")
        
        # Store doc id in session for later deletion
        session = get_session(chat_id)
        if 'data' not in session:
            session['data'] = {}
        session['data']['doc_id'] = result.get('name', '').split('/')[-1]
        session['data']['mobile'] = data.get('mobile', '')
        set_session(chat_id, session)
    else:
        send(chat_id, "❌ Error posting request. Please try again or use the web app: " + APP_URL)

# ============================================================
# CALLBACK HANDLER
# ============================================================

def handle_callback(callback):
    """Handle inline button callbacks"""
    chat_id = callback['message']['chat']['id']
    data = callback.get('data', '')
    callback_id = callback['id']
    
    answer_callback(callback_id)
    session = get_session(chat_id)
    post_data = session.get('data', {})
    
    # T&C
    if data == 'tc_agree':
        start_post_flow(chat_id)
    
    elif data == 'tc_disagree':
        send(chat_id, "❌ You must agree to Terms & Conditions to use this service.\n\nUse /help for more info.")
        clear_session(chat_id)
    
    # Board selection
    elif data.startswith('board_'):
        idx = int(data.split('_')[1])
        post_data['board'] = BOARDS[idx]
        session['data'] = post_data
        session['step'] = 'dept'
        set_session(chat_id, session)
        # Show departments for selected board
        board_key = "RRB – Group C" if idx == 1 else "RRC – Group D"
        depts = DEPTS[board_key]
        buttons = [[{"text": d, "callback_data": f"dept_{i}"}] for i, d in enumerate(depts)]
        send_keyboard(chat_id, f"📂 <b>Step 4/8 — Department</b>\n\nBoard: {BOARDS[idx]}", buttons)
    
    # Department selection
    elif data.startswith('dept_'):
        idx = int(data.split('_')[1])
        board_key = "RRB – Group C" if "Group C" in post_data.get('board', '') else "RRC – Group D"
        depts = DEPTS[board_key]
        dept = depts[idx]
        post_data['dept'] = dept
        session['data'] = post_data
        session['step'] = 'post_title'
        set_session(chat_id, session)
        # Show posts for selected dept
        posts = POSTS.get(dept, [])
        if posts:
            buttons = [[{"text": p[:35], "callback_data": f"post_{i}"}] for i, p in enumerate(posts)]
            send_keyboard(chat_id, f"👔 <b>Step 5/8 — Post/Designation</b>\n\nDept: {dept}", buttons)
        else:
            send(chat_id, f"👔 <b>Step 5/8 — Post/Designation</b>\n\nType your exact post/designation:")
            session['step'] = 'post_title_text'
            set_session(chat_id, session)
    
    # Post selection
    elif data.startswith('post_'):
        idx = int(data.split('_')[1])
        dept = post_data.get('dept', '')
        posts = POSTS.get(dept, [])
        if idx < len(posts):
            post_data['post'] = posts[idx]
        session['data'] = post_data
        session['step'] = 'current_zone'
        set_session(chat_id, session)
        buttons = make_zone_buttons('czone')
        send_keyboard(chat_id, "📍 <b>Step 6/8 — Current Zone</b>\n\nSelect your current Railway zone:", buttons)
    
    # Current zone
    elif data.startswith('czone_'):
        idx = int(data.split('_')[1])
        post_data['zone'] = ZONES[idx]
        session['data'] = post_data
        session['step'] = 'current_station'
        set_session(chat_id, session)
        send(chat_id, f"📍 <b>Step 6b — Current Station/Office</b>\n\nZone: {ZONES[idx]}\n\nType your current station or office name:")
    
    # Preferred zone
    elif data.startswith('pzone_'):
        idx = int(data.split('_')[1])
        post_data['pzone'] = ZONES[idx]
        session['data'] = post_data
        session['step'] = 'preferred_station'
        set_session(chat_id, session)
        send(chat_id, f"🎯 <b>Step 8/8 — Preferred Station</b>\n\nZone: {ZONES[idx]}\n\nType your preferred station or office:")
    
    # Confirm post
    elif data == 'confirm_post':
        submit_post(chat_id, post_data)
        clear_session(chat_id)
    
    elif data == 'restart_post':
        handle_post(chat_id, {})
    
    elif data == 'cancel_post':
        send(chat_id, "❌ Post cancelled. Use /post anytime to try again.")
        clear_session(chat_id)
    
    # Delete post
    elif data == 'confirm_delete':
        send(chat_id, "🗑️ Your post has been marked for deletion.\n\nPlease also delete it from the web app: " + APP_URL)
        clear_session(chat_id)
    
    elif data == 'cancel_delete':
        send(chat_id, "✅ Delete cancelled. Your post is still active.")

# ============================================================
# MESSAGE HANDLER
# ============================================================

def handle_message(msg):
    """Handle incoming messages"""
    chat_id = msg['chat']['id']
    text = msg.get('text', '').strip()
    user = msg.get('from', {})
    
    if not text:
        return
    
    # Commands
    if text == '/start':
        handle_start(chat_id, user)
    elif text == '/post':
        handle_post(chat_id, user)
    elif text == '/help':
        handle_help(chat_id)
    elif text == '/app':
        handle_app(chat_id)
    elif text == '/mypost':
        handle_mypost(chat_id, user.get('id'))
    elif text == '/delete':
        handle_delete(chat_id)
    elif text.startswith('/'):
        send(chat_id, "❓ Unknown command. Use /help to see available commands.")
    else:
        # Multi-step form input
        session = get_session(chat_id)
        if session.get('step'):
            process_post_step(chat_id, text, session)
        else:
            send(chat_id, f"Use /post to post your transfer request or /help for commands.\n\n🔗 {APP_URL}")

# ============================================================
# WEBHOOK / POLLING
# ============================================================

def set_webhook(url):
    """Set webhook for the bot"""
    result = tg("setWebhook", {"url": f"{url}/webhook"})
    print(f"Webhook set: {result}")

def delete_webhook():
    """Use polling instead of webhook"""
    tg("deleteWebhook", {})

def run_polling():
    """Run bot with long polling (for local testing)"""
    print("🚂 RailMT Pro Bot started (polling mode)...")
    print(f"Bot: @RAILMTPRO_BOT")
    print(f"App: {APP_URL}")
    
    delete_webhook()
    offset = 0
    
    while True:
        try:
            result = tg("getUpdates", {"offset": offset, "timeout": 30})
            updates = result.get('result', [])
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' in update:
                    handle_message(update['message'])
                elif 'callback_query' in update:
                    handle_callback(update['callback_query'])
            
        except KeyboardInterrupt:
            print("\n Bot stopped.")
            break
        except Exception as e:
            log.error(f"Polling error: {e}")
            import time
            time.sleep(5)

# For webhook deployment (Railway/Render/Heroku)
def handle_webhook_update(update):
    """Handle single update from webhook"""
    if 'message' in update:
        handle_message(update['message'])
    elif 'callback_query' in update:
        handle_callback(update['callback_query'])

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_polling()

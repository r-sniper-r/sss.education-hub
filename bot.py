import os
import logging
import sqlite3
import random
import threading
import json
import asyncio
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(title="R-Sniper Enterprise API", version="5.1")

# Ensure static and upload directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Database path
DB_PATH = os.getenv("DB_PATH", os.path.join("static", "r_sniper.db"))

# Gmail SMTP configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-gmail-app-password")

def send_email(to_email: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Email delivery error: {e}")
        return False

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    
    # Users Table with profile and privacy settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            contact TEXT UNIQUE,
            phone TEXT,
            password TEXT,
            role TEXT,
            grade TEXT,
            school TEXT,
            wallet REAL DEFAULT 0.00,
            followers TEXT DEFAULT '[]',
            following TEXT DEFAULT '[]',
            friends TEXT DEFAULT '[]',
            bio TEXT DEFAULT '',
            privacy TEXT DEFAULT 'public',
            profile_pic TEXT DEFAULT ''
        )
    """)
    
    # Posts Table with comments support
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            type TEXT,
            content TEXT,
            media_url TEXT,
            likes TEXT DEFAULT '[]',
            favs TEXT DEFAULT '[]',
            shares INTEGER DEFAULT 0,
            comments TEXT DEFAULT '[]'
        )
    """)

    # Password Resets Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            email TEXT,
            token TEXT
        )
    """)

    # Live Stream Join Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_username TEXT,
            username TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    
    # Default Owner Admin
    cursor.execute("SELECT * FROM users WHERE username = 'rsniper'")
    if not cursor.fetchone():
        hashed_pw = pwd_context.hash("admin123")
        cursor.execute("""
            INSERT INTO users (username, name, contact, phone, password, role, grade, school, wallet, bio, privacy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("rsniper", "Owner Admin", "owner@rsniper.com", "0946253528", hashed_pw, "manager", "Grade 12", "R-Sniper Academy", 0.00, "Official R-Sniper Admin", "public"))
    
    conn.commit()
    conn.close()

init_db()
OTP_STORE = {}

# Pydantic Models
class OTPRequest(BaseModel):
    contact: str

class RegisterModel(BaseModel):
    name: str
    username: str
    gmail: str
    phone: str
    password: str
    gender: str
    age: int
    grade: str
    school: str
    code: str

class LoginModel(BaseModel):
    contact: str
    password: str

class SocialModel(BaseModel):
    username: str
    target_username: str

class CommentModel(BaseModel):
    postId: int
    username: str
    text: str

class ForgotPasswordModel(BaseModel):
    email: str

class ResetPasswordModel(BaseModel):
    token: str
    new_password: str

class UpdateProfileModel(BaseModel):
    username: str
    bio: str
    privacy: str
    profile_pic: Optional[str] = ""

class LiveRequestModel(BaseModel):
    host_username: str
    username: str

# Keep-Alive endpoint
@app.get("/ping")
async def ping():
    return {"status": "alive", "message": "R-Sniper server is active 24/7."}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open(os.path.join("static", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/send-code")
async def send_code(data: OTPRequest):
    code = str(random.randint(100000, 999999))
    OTP_STORE[data.contact] = code
    
    # Send via Gmail SMTP
    email_body = f"Your R-Sniper Hub 6-digit verification code is: {code}\n\nDo not share this code with anyone."
    send_email(data.contact, "R-Sniper Verification Code", email_body)
    
    logger.info(f"🔒 OTP CODE dispatched to {data.contact}: {code}")
    return {"status": "success", "message": "Verification code sent directly to your Gmail."}

@app.post("/api/forgot-password")
async def forgot_password(data: ForgotPasswordModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE contact = ?", (data.email,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Email address not registered.")
    
    token = secrets.token_hex(16)
    cursor.execute("INSERT INTO password_resets (email, token) VALUES (?, ?)", (data.email, token))
    conn.commit()
    conn.close()
    
    web_url = os.getenv("WEB_APP_URL", "https://sss-education-hub.onrender.com")
    reset_link = f"{web_url}/reset-password?token={token}"
    body = f"Hello,\n\nYou requested a password reset for your R-Sniper account.\nClick the link below to reset your password:\n\n{reset_link}\n\nIf you did not request this, please ignore this email."
    send_email(data.email, "Password Reset - R-Sniper Hub", body)
    return {"status": "success", "message": "Password reset link sent to your Gmail."}

@app.post("/api/reset-password")
async def reset_password(data: ResetPasswordModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM password_resets WHERE token = ?", (data.token,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    
    email = row[0]
    hashed_password = pwd_context.hash(data.new_password)
    cursor.execute("UPDATE users SET password = ? WHERE contact = ?", (hashed_password, email))
    cursor.execute("DELETE FROM password_resets WHERE token = ?", (data.token,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Password successfully updated."}

@app.post("/api/register")
async def register(user: RegisterModel):
    expected_code = OTP_STORE.get(user.gmail) or OTP_STORE.get(user.phone)
    if not expected_code or expected_code != user.code:
        raise HTTPException(status_code=400, detail="Invalid or unverified 6-digit verification code.")
    
    hashed_password = pwd_context.hash(user.password)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, name, contact, phone, password, role, grade, school, wallet, bio, privacy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.00, '', 'public')
        """, (user.username, user.name, user.gmail, user.phone, hashed_password, "user", user.grade, user.school))
        conn.commit()
        return {"status": "success", "message": "Registered successfully."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username or Email already registered.")
    finally:
        conn.close()

@app.post("/api/login")
async def login(creds: LoginModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE contact = ? OR username = ?", (creds.contact, creds.contact))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(creds.password, row[5]):
        raise HTTPException(status_code=401, detail="Wrong password or account not found.")
    
    user_obj = {
        "id": row[0], "username": row[1], "name": row[2], "contact": row[3],
        "phone": row[4], "role": row[6], "grade": row[7], "school": row[8],
        "wallet": row[9], "followers": json.loads(row[10]), "following": json.loads(row[11]),
        "friends": json.loads(row[12]), "bio": row[13], "privacy": row[14], "profile_pic": row[15]
    }
    return {"status": "success", "user": user_obj}

@app.get("/api/search-users")
async def search_users(query: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, bio, profile_pic, followers, privacy FROM users WHERE username LIKE ? LIMIT 20", (f"%{query}%",))
    rows = cursor.fetchall()
    conn.close()
    
    users = []
    for r in rows:
        users.append({
            "username": r[0], "name": r[1], "bio": r[2], "profile_pic": r[3],
            "followers_count": len(json.loads(r[4])), "privacy": r[5]
        })
    return {"users": users}

@app.post("/api/user/update-profile")
async def update_profile(data: UpdateProfileModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bio = ?, privacy = ?, profile_pic = ? WHERE username = ?", 
                   (data.bio, data.privacy, data.profile_pic, data.username))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Profile updated successfully."}

@app.get("/api/posts")
async def get_posts():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, title, type, content, media_url, likes, favs, shares, comments FROM posts ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    posts = []
    for r in rows:
        posts.append({
            "id": r[0], "username": r[1], "title": r[2], "type": r[3],
            "content": r[4], "mediaUrl": r[5], "likes": json.loads(r[6]),
            "favs": json.loads(r[7]), "shares": r[8], "comments": json.loads(r[9])
        })
    return {"posts": posts}

@app.post("/api/posts")
async def create_post(
    username: str = Form(...),
    title: str = Form(...),
    type: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = None
):
    media_url = None
    if file:
        file_path = os.path.join("uploads", file.filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        media_url = f"/uploads/{file.filename}"

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO posts (username, title, type, content, media_url, likes, favs, shares, comments)
        VALUES (?, ?, ?, ?, ?, '[]', '[]', 0, '[]')
    """, (username, title, type, content, media_url))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Post published online successfully."}

@app.post("/api/posts/like")
async def like_post(data: dict):
    post_id = data.get("postId")
    username = data.get("username")
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT likes FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    
    likes = json.loads(row[0])
    if username in likes:
        likes.remove(username)
    else:
        likes.append(username)
        
    cursor.execute("UPDATE posts SET likes = ? WHERE id = ?", (json.dumps(likes), post_id))
    conn.commit()
    conn.close()
    return {"status": "success", "likes": len(likes)}

@app.post("/api/posts/comment")
async def comment_post(data: CommentModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT comments FROM posts WHERE id = ?", (data.postId,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    
    comments = json.loads(row[0])
    new_comment = {"username": data.username, "text": data.text}
    comments.append(new_comment)
    
    cursor.execute("UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), data.postId))
    conn.commit()
    conn.close()
    return {"status": "success", "comments": comments}

@app.post("/api/social/follow")
async def toggle_follow(data: SocialModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT followers, following FROM users WHERE username = ?", (data.username,))
    u_row = cursor.fetchone()
    cursor.execute("SELECT followers, following FROM users WHERE username = ?", (data.target_username,))
    t_row = cursor.fetchone()
    
    if not u_row or not t_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
        
    u_following = json.loads(u_row[1])
    t_followers = json.loads(t_row[0])
    
    if data.target_username in u_following:
        u_following.remove(data.target_username)
        if data.username in t_followers: t_followers.remove(data.username)
        action = "unfollowed"
    else:
        u_following.append(data.target_username)
        if data.username not in t_followers: t_followers.append(data.username)
        action = "followed"
        
    cursor.execute("UPDATE users SET following = ? WHERE username = ?", (json.dumps(u_following), data.username))
    cursor.execute("UPDATE users SET followers = ? WHERE username = ?", (json.dumps(t_followers), data.target_username))
    conn.commit()
    conn.close()
    return {"status": "success", "action": action, "followers_count": len(t_followers)}

# Live Stream Join Requests Endpoints
@app.post("/api/live/request-join")
async def live_request_join(data: LiveRequestModel):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO live_requests (host_username, username, status) VALUES (?, ?, 'pending')", 
                   (data.host_username, data.username))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Join request sent to host."}

@app.get("/api/live/requests/{host_username}")
async def get_live_requests(host_username: str):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, status FROM live_requests WHERE host_username = ? AND status = 'pending'", (host_username,))
    rows = cursor.fetchall()
    conn.close()
    
    requests = [{"id": r[0], "username": r[1], "status": r[2]} for r in rows]
    return {"requests": requests}

@app.post("/api/live/approve-join")
async def approve_live_request(data: dict):
    req_id = data.get("request_id")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE live_requests SET status = 'approved' WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "User approved to join live."}

# Telegram Bot Setup
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    web_app_url = os.getenv("WEB_APP_URL", "https://sss-education-hub.onrender.com")
    keyboard = [[InlineKeyboardButton("🚀 Launch R-Sniper Hub", web_app=WebAppInfo(url=web_app_url))]]
    await update.message.reply_text("🌟 **R-Sniper Secure Hub** 🌟", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

def run_telegram_bot():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN environment variable is missing! Telegram bot cannot start.")
        return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        bot_app = ApplicationBuilder().token(token).build()
        bot_app.add_handler(CommandHandler("start", start))
        logger.info("Starting Telegram bot polling...")
        bot_app.run_polling()
    except Exception as e:
        logger.warning(f"Telegram bot could not connect (network timeout/restricted region): {e}")
        logger.info("FastAPI web server is still running normally at http://localhost:7860")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 7860))
    uvicorn.run("bot:app", host="0.0.0.0", port=port)
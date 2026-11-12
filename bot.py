import os
import sqlite3
import random
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads", check_dir=True), name="uploads")

# --- SMTP EMAIL CONFIGURATION ---
# Replace these with your real Gmail credentials or app password for production
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "rsniper.education@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "your_gmail_app_password")

def send_smtp_email(to_email: str, subject: str, body: str):
    """Dispatches a real email via Gmail SMTP servers."""
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
        print(f"SMTP Error: {e}")
        return False

def init_db():
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT UNIQUE,
            gmail TEXT UNIQUE,
            phone TEXT DEFAULT '',
            password TEXT,
            gender TEXT,
            age INTEGER,
            grade TEXT,
            school TEXT,
            bio TEXT DEFAULT '',
            privacy TEXT DEFAULT 'public',
            wallet REAL DEFAULT 0.0,
            followers TEXT DEFAULT '[]',
            following TEXT DEFAULT '[]'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            title TEXT,
            type TEXT,
            content TEXT,
            mediaUrl TEXT,
            likes TEXT DEFAULT '[]',
            comments TEXT DEFAULT '[]'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_username TEXT,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class LoginRequest(BaseModel):
    contact: str
    password: str

class CodeRequest(BaseModel):
    contact: str

class RegisterRequest(BaseModel):
    name: str
    username: str
    gmail: str
    phone: Optional[str] = ""
    password: str
    gender: str
    age: int
    grade: str
    school: str
    code: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

class LikeRequest(BaseModel):
    postId: int
    username: str

class CommentRequest(BaseModel):
    postId: int
    username: str
    text: str

class FollowRequest(BaseModel):
    username: str
    target_username: str

class ProfileUpdate(BaseModel):
    username: str
    bio: str
    privacy: str

class LiveJoinRequest(BaseModel):
    host_username: str
    username: str

class ApproveRequest(BaseModel):
    request_id: int

# In-memory stores for active OTP verification sessions & password resets
otp_store = {}
reset_store = {}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    path = os.path.join("static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Index.html not found in static folder</h1>"

@app.post("/api/send-code")
async def send_code(req: CodeRequest):
    code = str(random.randint(100000, 999999))
    otp_store[req.contact] = code
    
    # Attempt real email dispatch if input looks like an email
    if "@" in req.contact:
        subject = "R-Sniper Hub Verification Code"
        body = f"Hello,\n\nYour verification code for R-Sniper Educational Hub is: {code}\n\nEnter this code in your app to complete your registration."
        email_sent = send_smtp_email(req.contact, subject, body)
        if not email_sent:
            # Fallback for development/testing if SMTP credentials are unconfigured
            print(f"[Dev Fallback] OTP for {req.contact}: {code}")
    
    return {"status": "success", "message": "Verification code dispatched to your Gmail inbox.", "code": code}

@app.post("/api/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE gmail = ?", (req.email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="No account registered with this Gmail address.")

    reset_code = str(random.randint(100000, 999999))
    reset_store[req.email] = reset_code

    subject = "R-Sniper Hub Password Reset Code"
    body = f"Hello,\n\nYour password reset code is: {reset_code}\n\nEnter this code to reset your password."
    send_smtp_email(req.email, subject, body)

    return {"status": "success", "message": "Password reset code sent to your Gmail inbox.", "code": reset_code}

@app.post("/api/reset-password")
async def reset_password(req: ResetPasswordRequest):
    if req.email not in reset_store or reset_store[req.email] != req.code:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE gmail = ?", (req.new_password, req.email))
    conn.commit()
    conn.close()

    del reset_store[req.email]
    return {"status": "success", "message": "Password successfully reset! You can now login with your new password."}

@app.post("/api/register")
async def register(req: RegisterRequest):
    # Verify OTP
    if req.gmail not in otp_store or otp_store[req.gmail] != req.code:
        raise HTTPException(status_code=400, detail="Invalid or missing verification code.")

    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (name, username, gmail, phone, password, gender, age, grade, school)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.name, req.username, req.gmail, req.phone or "", req.password, req.gender, req.age, req.grade, req.school))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username or Gmail already registered.")
    conn.close()
    
    del otp_store[req.gmail]
    return {"status": "success", "message": "Registration successful"}

@app.post("/api/login")
async def login(req: LoginRequest):
    conn = sqlite3.connect("r_sniper.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE gmail = ? OR username = ? OR phone = ?", (req.contact, req.contact, req.contact))
    user = cursor.fetchone()
    conn.close()
    
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=400, detail="Invalid login credentials or password.")
    
    import json
    user_dict = dict(user)
    user_dict["followers"] = json.loads(user_dict["followers"])
    user_dict["following"] = json.loads(user_dict["following"])
    return {"status": "success", "user": user_dict}

@app.get("/api/posts")
async def get_posts():
    import json
    conn = sqlite3.connect("r_sniper.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts ORDER BY id DESC")
    posts = []
    for row in cursor.fetchall():
        p = dict(row)
        p["likes"] = json.loads(p["likes"])
        p["comments"] = json.loads(p["comments"])
        posts.append(p)
    conn.close()
    return {"posts": posts}

@app.post("/api/posts")
async def create_post(
    username: str = Form(...),
    title: str = Form(...),
    type: str = Form(...),
    content: str = Form(...),
    file: UploadFile = File(None)
):
    media_url = None
    if file:
        file_path = os.path.join("uploads", file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        media_url = f"/uploads/{file.filename}"

    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO posts (username, title, type, content, mediaUrl, likes, comments)
        VALUES (?, ?, ?, ?, ?, '[]', '[]')
    """, (username, title, type, content, media_url))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/posts/like")
async def like_post(req: LikeRequest):
    import json
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT likes FROM posts WHERE id = ?", (req.postId,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    likes = json.loads(row[0])
    if req.username in likes:
        likes.remove(req.username)
    else:
        likes.append(req.username)
    cursor.execute("UPDATE posts SET likes = ? WHERE id = ?", (json.dumps(likes), req.postId))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/posts/comment")
async def comment_post(req: CommentRequest):
    import json
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT comments FROM posts WHERE id = ?", (req.postId,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Post not found")
    comments = json.loads(row[0])
    comments.append({"username": req.username, "text": req.text})
    cursor.execute("UPDATE posts SET comments = ? WHERE id = ?", (json.dumps(comments), req.postId))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/social/follow")
async def follow_user(req: FollowRequest):
    import json
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("SELECT following FROM users WHERE username = ?", (req.username,))
    row1 = cursor.fetchone()
    cursor.execute("SELECT followers FROM users WHERE username = ?", (req.target_username,))
    row2 = cursor.fetchone()
    if not row1 or not row2:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    following = json.loads(row1[0])
    followers = json.loads(row2[0])
    action = "followed"
    if req.target_username in following:
        following.remove(req.target_username)
        if req.username in followers:
            followers.remove(req.username)
        action = "unfollowed"
    else:
        following.append(req.target_username)
        followers.append(req.username)
    
    cursor.execute("UPDATE users SET following = ? WHERE username = ?", (json.dumps(following), req.username))
    cursor.execute("UPDATE users SET followers = ? WHERE username = ?", (json.dumps(followers), req.target_username))
    conn.commit()
    conn.close()
    return {"status": "success", "action": action}

@app.get("/api/search-users")
async def search_users(query: str):
    conn = sqlite3.connect("r_sniper.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, followers FROM users WHERE username LIKE ? OR name LIKE ?", (f"%{query}%", f"%{query}%"))
    users = []
    import json
    for r in cursor.fetchall():
        users.append({
            "username": r["username"],
            "name": r["name"],
            "followers_count": len(json.loads(r["followers"]))
        })
    conn.close()
    return {"users": users}

@app.post("/api/user/update-profile")
async def update_profile(req: ProfileUpdate):
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bio = ?, privacy = ? WHERE username = ?", (req.bio, req.privacy, req.username))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/live/request-join")
async def request_live_join(req: LiveJoinRequest):
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO live_requests (host_username, username) VALUES (?, ?)", (req.host_username, req.username))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/live/requests/{host_username}")
async def get_live_requests(host_username: str):
    conn = sqlite3.connect("r_sniper.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM live_requests WHERE host_username = ?", (host_username,))
    reqs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"requests": reqs}

@app.post("/api/live/approve-join")
async def approve_live_join(req: ApproveRequest):
    conn = sqlite3.connect("r_sniper.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM live_requests WHERE id = ?", (req.request_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
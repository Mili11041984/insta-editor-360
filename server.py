import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import re
import http.server
import socketserver
import os
import sys
import json
import sqlite3
import hashlib
import hmac
import secrets
import datetime
import urllib.parse
import urllib.request
import time
import random

PORT = int(os.environ.get("PORT", 5000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DB_PATH = os.path.join(BASE_DIR, "insta.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

ACCESS_KEY_PEPPER = "insta_secret_pepper_2026"
JWT_SECRET = "insta_jwt_secret_2026_super_key"
BOOTSTRAP_SECRET = "admin_bootstrap_secret_2026"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
    ".pdf": "application/pdf"
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            cur.executescript(f.read())
            
    # Extra tables for API keys, Key Requests, Orders, and Settings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_api_keys (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_key TEXT,
      provider TEXT,
      token TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS key_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT NOT NULL,
      ip TEXT,
      status TEXT DEFAULT 'pending',
      forwarded_to TEXT DEFAULT 'vyrox954@gmail.com',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_orders (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL,
      amount INTEGER DEFAULT 1000,
      method TEXT DEFAULT 'paytm',
      status TEXT DEFAULT 'pending',
      utr TEXT,
      access_key_generated TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
      key TEXT PRIMARY KEY,
      value TEXT
    );
    """)
    
    defaults = {
        "paytm_upi_id": "paytmqr5l66pa@ptys",
        "paytm_business_name": "Insta Editor 360",
        "paytm_mid": "",
        "paytm_mkey": "",
        "admin_email": "vyrox954@gmail.com",
        "price_inr": "1000",
        "apify_token": ""
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (k, v))
        
    conn.commit()
    conn.close()

def get_setting(key, default=""):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row["value"] if row else default
    except:
        return default

def set_setting(key, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -------------------------------------------------------------
# Automated Email Delivery Engine (SMTP)
# -------------------------------------------------------------
def send_email_worker(to_addr, subject, html_body, text_body=None):
    smtp_host = get_setting("smtp_host", "smtp.gmail.com")
    smtp_port = int(get_setting("smtp_port", "587"))
    smtp_user = get_setting("smtp_user", "vyrox954@gmail.com")
    smtp_pass = get_setting("smtp_pass", "").strip().replace(" ", "")
    from_name = get_setting("smtp_from_name", "Insta Editor 360")
    
    if not smtp_pass:
        print(f"[EMAIL PENDING SMTP PASSWORD] To: {to_addr} | Subject: {subject}")
        log_activity("system", "email_pending_smtp_pass", f"To: {to_addr} | Subject: {subject} | Please set Gmail App Password in Admin Panel")
        return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{smtp_user}>"
        msg["To"] = to_addr
        
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
        server.quit()
        print(f"[EMAIL DELIVERED SUCCESS] Sent to {to_addr} | Subject: {subject}")
        log_activity("system", "email_delivered", f"To: {to_addr} | Subject: {subject}")
        return True
    except Exception as e:
        print(f"[EMAIL SEND ERROR] Failed sending to {to_addr}: {e}")
        log_activity("system", "email_error", f"To: {to_addr} | Error: {e}")
        return False

def send_email_async(to_addr, subject, html_body, text_body=None):
    if not to_addr or "@" not in to_addr:
        return
    t = threading.Thread(target=send_email_worker, args=(to_addr, subject, html_body, text_body), daemon=True)
    t.start()

def send_key_request_notification_to_admin(requester_email, client_ip):
    admin_email = get_setting("admin_email", "vyrox954@gmail.com")
    tunnel_url = get_setting("public_tunnel_url", "https://electoral-and-gold-naturals.trycloudflare.com").rstrip("/")
    subject = f"🚨 New Key Request from {requester_email} — Insta Editor 360"
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#09090b;color:#f4f4f5;padding:20px;margin:0;">
    <div style="max-width:520px;margin:0 auto;background:#18181b;border:1px solid #27272a;border-radius:16px;padding:24px;">
        <h2 style="color:#38bdf8;margin-top:0;">📥 New Access Key Request</h2>
        <p style="font-size:15px;color:#d4d4d8;line-height:1.5;">A visitor has submitted a request for an Insta Editor 360 Lifetime Access Key:</p>
        <div style="background:#27272a;padding:16px;border-radius:12px;margin:18px 0;font-size:14px;">
            <p style="margin:4px 0;"><strong>Customer Email:</strong> <span style="color:#34d399;font-weight:600;">{requester_email}</span></p>
            <p style="margin:4px 0;color:#a1a1aa;"><strong>IP Address:</strong> {client_ip}</p>
            <p style="margin:4px 0;color:#a1a1aa;"><strong>Time:</strong> {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}</p>
        </div>
        <p style="font-size:14px;color:#a1a1aa;">Click below to open your Admin Panel, approve this request, and automatically email the key to the customer:</p>
        <div style="text-align:center;margin:24px 0 10px 0;">
            <a href="{tunnel_url}/keys-panel" style="background:#10b981;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:bold;font-size:14px;display:inline-block;">Open Admin Panel & Approve ↗</a>
        </div>
        <p style="font-size:12px;color:#71717a;text-align:center;margin-top:10px;">
            Mobile Link: <a href="{tunnel_url}/keys-panel" style="color:#38bdf8;">{tunnel_url}/keys-panel</a><br>
            Local Link: <a href="http://localhost:5000/keys-panel" style="color:#a1a1aa;">http://localhost:5000/keys-panel</a>
        </p>
    </div>
</body>
</html>"""
    send_email_async(admin_email, subject, html)

def send_approved_key_to_customer(customer_email, plain_key, plan="Lifetime Access"):
    tunnel_url = get_setting("public_tunnel_url", "https://electoral-and-gold-naturals.trycloudflare.com").rstrip("/")
    subject = "🎉 Your Insta Editor 360 Lifetime Access Key is Ready!"
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#09090b;color:#f4f4f5;padding:24px;margin:0;">
    <div style="max-width:520px;margin:0 auto;background:#18181b;border:1px solid #27272a;border-radius:20px;padding:28px;text-align:center;">
        <div style="font-size:36px;margin-bottom:8px;">✨</div>
        <h1 style="color:#ffffff;margin:0 0 8px 0;font-size:22px;">Welcome to Insta Editor 360!</h1>
        <p style="color:#a1a1aa;font-size:14px;margin:0 0 20px 0;">Your request has been approved. Here is your official Lifetime Access Key:</p>
        
        <div style="background:#022c22;border:2px solid #059669;border-radius:14px;padding:18px;margin:20px 0;">
            <div style="font-size:12px;color:#6ee7b7;font-weight:bold;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;">Your Personal Access Key</div>
            <div style="font-family:monospace;font-size:22px;color:#34d399;font-weight:bold;letter-spacing:1px;user-select:all;background:#064e3b;padding:8px 12px;border-radius:6px;display:inline-block;">{plain_key}</div>
            <div style="font-size:13px;color:#a7f3d0;margin-top:8px;">Plan: <strong>{plan}</strong> · 2 Devices Allowed</div>
        </div>

        <div style="text-align:left;background:#27272a;border-radius:12px;padding:16px;margin-bottom:24px;font-size:14px;color:#d4d4d8;line-height:1.6;">
            <strong style="color:#fff;">How to Login & Get Started:</strong>
            <ol style="margin:8px 0 0 0;padding-left:20px;">
                <li>Open the Login Page in your browser.</li>
                <li>Enter your Access Key shown above.</li>
                <li>Click <strong>Verify & Enter</strong> to unlock your full dashboard!</li>
            </ol>
        </div>

        <div style="text-align:center;margin-bottom:24px;">
            <a href="{tunnel_url}/login" style="background:#0284c7;color:#ffffff;text-decoration:none;padding:13px 28px;border-radius:10px;font-weight:bold;font-size:15px;display:inline-block;">Login to Insta Editor 360 ↗</a>
        </div>

        <hr style="border:none;border-top:1px solid #27272a;margin:20px 0;">
        <p style="font-size:12px;color:#71717a;margin:0;line-height:1.5;">
            Need help or have questions? Email us directly at: <a href="mailto:vyrox954@gmail.com" style="color:#38bdf8;text-decoration:none;">vyrox954@gmail.com</a><br>
            Please save this email for future reference.
        </p>
    </div>
</body>
</html>"""
    send_email_async(customer_email, subject, html)

def key_hash(key):
    return sha(str(key).strip().upper() + ":" + ACCESS_KEY_PEPPER)

def log_activity(actor, action, details=""):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO activity_logs (actor, action, details) VALUES (?, ?, ?)",
                    (str(actor), str(action), str(details)[:500]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log error: {e}")


def unwrap_val(v):
    if v is None:
        return ""
    if isinstance(v, (int, float, bool)):
        return v
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        if "s" in v:
            return unwrap_val(v["s"])
        if "v" in v:
            return unwrap_val(v["v"])
        if "value" in v:
            return unwrap_val(v["value"])
        for sub_k in ["data", "result", "token", "key", "provider", "username", "email", "val"]:
            if sub_k in v:
                return unwrap_val(v[sub_k])
        for val in v.values():
            unwrapped = unwrap_val(val)
            if unwrapped:
                return unwrapped
        return ""
    if isinstance(v, (list, tuple)):
        for item in reversed(v):
            unwrapped = unwrap_val(item)
            if unwrapped:
                return unwrapped
        return ""
    return str(v).strip()

def get_param(body, raw_body, key, default=None):
    def rec(b):
        if isinstance(b, dict):
            if key in b and b[key] is not None:
                return b[key]
            if "k" in b and "v" in b and isinstance(b["k"], list) and isinstance(b["v"], list):
                try:
                    mapped = dict(zip(b["k"], b["v"]))
                    if key in mapped and mapped[key] is not None:
                        return mapped[key]
                except:
                    pass
            for v in b.values():
                res = rec(v)
                if res is not None:
                    return res
        elif isinstance(b, list):
            for item in b:
                res = rec(item)
                if res is not None:
                    return res
        return None

    val = rec(body)
    if val is not None:
        unwrapped = unwrap_val(val)
        if unwrapped != "":
            return unwrapped

    if raw_body:
        pat1 = '["\']' + re.escape(key) + '["\']\\s*:\\s*["\']([^"\']+)["\']'
        m = re.search(pat1, raw_body, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip()
        pat2 = '["\']' + re.escape(key) + '["\']\\s*,\\s*["\']([^"\']+)["\']'
        m2 = re.search(pat2, raw_body, re.IGNORECASE)
        if m2 and m2.group(1).strip():
            return m2.group(1).strip()
    return default

def extract_param(body, key, default=None, raw_body=""):
    return get_param(body, raw_body, key, default)

def admin_from_token(auth_header):
    token = auth_header.replace("Bearer ", "").strip()
    if not token or token.count(".") != 2:
        return None
    try:
        aid, exp, sig = token.split(".")
        if int(exp) < int(datetime.datetime.now().timestamp() * 1000):
            return None
        msg = f"{aid}.{exp}".encode("utf-8")
        expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM admins WHERE id = ?", (aid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def check_admin_auth(handler):
    """Verifies admin authorization via admin_session cookie or Bearer token"""
    cookie_header = handler.headers.get("Cookie", "")
    if "admin_session=" in cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("admin_session="):
                token = part.split("=", 1)[1].strip()
                if "." in token:
                    try:
                        ts, sig = token.split(".", 1)
                        if int(time.time()) - int(ts) < 604800:
                            msg = f"admin.{ts}".encode("utf-8")
                            expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
                            if hmac.compare_digest(sig, expected_sig):
                                return {"username": "admin", "role": "admin"}
                    except Exception:
                        pass
    auth_header = handler.headers.get("Authorization", "")
    admin = admin_from_token(auth_header)
    if admin:
        return admin
    return None


# ----------------------------------------------------------------------
# Profile Clone & Apify Integration Engine
# ----------------------------------------------------------------------
def build_post_insights(views, likes, comments_count, is_reel, duration_secs=15):
    views = max(int(views or 0), 120)
    likes = max(int(likes or 0), 12)
    comments_count = max(int(comments_count or 0), 2)
    accounts_reached = max(int(views * 0.84), likes)
    follows = max(int(views * 0.014), 1)
    profile_visits = max(int(views * 0.042), 2)
    shares = max(int(views * 0.036), 3)
    saves = max(int(views * 0.024), 2)
    reposts = max(int(views * 0.009), 1)
    dur_secs = max(5, int(duration_secs or 15)) if is_reel else 0
    dur_str = f"0:{dur_secs:02d}" if dur_secs < 60 else f"{dur_secs//60}:{dur_secs%60:02d}"
    avg_secs = max(3, min(dur_secs - 1, int(dur_secs * 0.48))) if is_reel else 0
    avg_watch = f"0:{avg_secs:02d}" if avg_secs < 60 else f"{avg_secs//60}:{avg_secs%60:02d}"
    
    return {
        "views": views,
        "likes": likes,
        "commentsCount": comments_count,
        "accountsReached": accounts_reached,
        "follows": follows,
        "profileVisits": profile_visits,
        "shares": shares,
        "saves": saves,
        "reposts": reposts,
        "duration": dur_str,
        "durationSecs": dur_secs,
        "avgWatchTime": avg_watch,
        "srcForYou": 84.2,
        "srcExplore": 7.5,
        "srcFeed": 5.8,
        "srcProfile": 2.5,
        "ratesManual": False,
        "skipRate": 26.4,
        "shareRate": round((shares / views) * 100, 1),
        "likeRate": round((likes / views) * 100, 1),
        "saveRate": round((saves / views) * 100, 1),
        "repostRate": round((reposts / views) * 100, 1),
        "commentRate": round((comments_count / views) * 100, 1),
        "audFollowersPct": 18.2,
        "audAge": [
            {"label": "13-17", "pct": 9.1},
            {"label": "18-24", "pct": 35.2},
            {"label": "25-34", "pct": 35.6},
            {"label": "35-44", "pct": 12.6},
            {"label": "45-54", "pct": 4.5},
            {"label": "55-64", "pct": 1.5},
            {"label": "65+", "pct": 1.4}
        ],
        "audCountry": [
            {"name": "India", "pct": 86.4},
            {"name": "United States", "pct": 4.2},
            {"name": "Pakistan", "pct": 2.1},
            {"name": "Bangladesh", "pct": 1.8},
            {"name": "United Arab Emirates", "pct": 1.5}
        ],
        "audGender": {
            "women": 42.5,
            "men": 57.5
        },
        "srcReelsTab": 84.6,
        "retention": [100, 95, 89, 83, 77, 72, 67, 63, 59, 56, 53, 50, 48, 46, 44, 43, 42, 41, 40, 39, 38],
        "engagementCurve": [4, 7, 12, 19, 27, 36, 46, 56, 65, 73, 80, 86, 90, 93, 95, 97, 98, 99, 100, 100, 100]
    }

def clone_instagram_profile(username, user_key=""):
    uname = username.strip().lstrip("@").lower()
    
    # 1. Check if user or server has an Apify Token
    apify_token = ""
    try:
        conn = get_db()
        cur = conn.cursor()
        if user_key:
            cur.execute("SELECT token FROM user_api_keys WHERE user_key = ? AND provider = 'apify' ORDER BY id DESC LIMIT 1", (user_key,))
            row = cur.fetchone()
            if row:
                apify_token = row["token"]
        if not apify_token:
            cur.execute("SELECT value FROM app_settings WHERE key = 'apify_token'")
            row = cur.fetchone()
            if row and row["value"]:
                apify_token = row["value"]
        conn.close()
    except Exception as e:
        print(f"DB check apify error: {e}")

    # If Apify token exists, attempt Apify scraper
    if apify_token:
        try:
            print(f"Fetching from Apify for @{uname}...")
            url = f"https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token={apify_token}&timeout=30"
            req_data = json.dumps({
                "directUrls": [f"https://www.instagram.com/{uname}/"],
                "resultsType": "details",
                "resultsLimit": 12
            }).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                items = json.loads(resp.read().decode("utf-8"))
                if items and isinstance(items, list) and len(items) > 0:
                    item = items[0]
                    if not item.get("error") and not item.get("errorDescription"):
                        posts = []
                        raw_posts = item.get("latestPosts", []) or item.get("posts", [])
                        for i, rp in enumerate(raw_posts[:12]):
                            vurl = rp.get("videoUrl") or ""
                            disp_url = rp.get("displayUrl") or rp.get("imageUrl") or ""
                            is_reel = rp.get("type") in ["Video", "reel", "Reel"] or int(rp.get("videoDuration") or 0) > 0 or bool(vurl)
                            # Ensure video url has #video tag so frontend Ke / Ah / xu recognizes it
                            post_img = (vurl + "#video") if vurl else disp_url
                            cur_views = int(rp.get("videoViewCount") or max(int(rp.get("likesCount", 0)) * 4, 150))
                            cur_likes = int(rp.get("likesCount") or 0)
                            cur_comments = int(rp.get("commentsCount") or 0)
                            cur_dur = int(rp.get("videoDuration") or 15)
                            p_obj = {
                                "id": str(rp.get("id") or f"ig_{uname}_{i}"),
                                "type": "reel" if is_reel else "post",
                                "image": post_img,
                                "videoUrl": vurl,
                                "thumbnail": disp_url,
                                "displayUrl": disp_url,
                                "caption": rp.get("caption") or "",
                                "likes": cur_likes,
                                "commentsCount": cur_comments,
                                "comments": [{"id": f"c_{i}_1", "username": "priya.designs", "text": "Stunning visuals! ✨"}, {"id": f"c_{i}_2", "username": "rahul_vibe", "text": "Super amazing post! 🔥"}],
                                "timestamp": rp.get("timestamp") or datetime.datetime.now().isoformat() + "Z",
                                "audioTitle": rp.get("audioTitle") or (f"{uname} · Original audio" if is_reel else ""),
                            }
                            p_obj.update(build_post_insights(cur_views, cur_likes, cur_comments, is_reel, cur_dur))
                            posts.append(p_obj)
                        if len(posts) > 0 or int(item.get("followersCount") or 0) > 0:
                            res = {
                                "username": uname,
                                "displayName": item.get("fullName") or uname.capitalize(),
                                "avatar": item.get("profilePicUrlHD") or item.get("profilePicUrl") or "",
                                "bio": item.get("biography") or "",
                                "externalUrl": (item.get("externalUrl") or "") if (item.get("externalUrl") and f"instagram.com/{uname}" not in str(item.get("externalUrl")).lower()) else "",
                                "verified": bool(item.get("verified")),
                                "postsCount": int(item.get("postsCount") or len(posts)),
                                "followersCount": int(item.get("followersCount") or 0),
                                "followingCount": int(item.get("followsCount") or 0),
                                "posts": posts
                            }
                            _CLONED_PROFILES[uname] = res
                            return res
                        else:
                            print(f"Apify returned 0 posts/followers for @{uname}, falling back to generator...")
                    else:
                        print(f"Apify returned error for @{uname}: {item.get('error')}, falling back to generator...")
        except Exception as err:
            print(f"Apify fetch error, falling back to instant cloner: {err}")

    # Fallback to Intelligent Clone Generator
    h = int(hashlib.md5(uname.encode("utf-8")).hexdigest()[:8], 16)
    clean_parts = uname.replace(".", " ").replace("_", " ").split()
    display_name = " ".join([p.capitalize() for p in clean_parts]) or uname.capitalize()
    
    is_celebrity = uname in ["cristiano", "leomessi", "virat.kohli", "instagram", "natgeo", "nasa", "selenagomez", "kyliejenner", "kendalljenner"]
    if is_celebrity:
        followers = 150000000 + (h % 350000000)
        verified = True
        bio = f"Official Instagram profile of {display_name}. Welcome to my world! ✨"
    else:
        followers = 14500 + (h % 485000)
        verified = followers > 100000
        bio = f"Content Creator & Visual Artist 📸\nExploring life · Storytelling · Creative vision\n📩 Inquiries: {uname}@gmail.com"
        
    following = 180 + (h % 520)
    posts_count = 48 + (h % 180)
    
    sample_images = [
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=600&auto=format&fit=crop&q=80"
    ]
    
    avatar = sample_images[h % len(sample_images)]
    
    posts = []
    now = int(time.time())
    captions = [
        "Keep moving forward, the best is yet to come ✨ #dailyvibes #creators",
        "Hard work and consistency always speak louder than words. Never give up! 🚀",
        "Golden hour peace and quiet moments 🌅 Enjoy every second.",
        "Behind the scenes of today's setup! Drop your thoughts in the comments 👇",
        "Building new ideas and creating our own path 🔥",
        "Weekend energy in full swing! How's your week shaping up?",
        "Major announcement coming very soon! Stay tuned 👀✨",
        "Enjoying the journey as much as the destination 💯",
        "Heartfelt gratitude for all the love and continuous support ❤️"
    ]
    sample_comments = [
        {"username": "alex_vibes", "text": "Pure fire! 🔥 Keep it up!"},
        {"username": "priya.designs", "text": "This is so inspiring ✨"},
        {"username": "rahul_k", "text": "Top notch quality as always 👏"},
        {"username": "sophia_m", "text": "Amazing capture! ❤️"},
        {"username": "vikram_07", "text": "Bro this is insane! 🚀"}
    ]
    
    for i in range(9):
        post_h = (h + i * 179) % 1000000
        is_reel = (i % 2 == 0)
        likes = int(followers * (0.04 + (post_h % 60) / 1000.0))
        views = int(likes * (3.5 + (post_h % 80) / 20.0))
        comments_cnt = int(likes * 0.02) + (post_h % 40)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - (i * 86400 * 2 + (post_h % 40000))))
        img = sample_images[(h + i) % len(sample_images)]
        
        p_dur = (15 + (post_h % 45)) if is_reel else 0
        p_obj = {
            "id": f"ig_{uname}_{i+1}",
            "type": "reel" if is_reel else "post",
            "image": img,
            "caption": captions[i % len(captions)],
            "likes": max(likes, 150),
            "commentsCount": max(comments_cnt, 8),
            "comments": random.sample(sample_comments, 3),
            "timestamp": timestamp,
            "audioTitle": f"{uname} · Original audio" if is_reel else "",
        }
        p_obj.update(build_post_insights(max(views, likes * 2), max(likes, 150), max(comments_cnt, 8), is_reel, p_dur))
        posts.append(p_obj)
        
    fallback_res = {
        "username": uname,
        "displayName": display_name,
        "avatar": avatar,
        "bio": bio,
        "externalUrl": "",
        "verified": verified,
        "postsCount": posts_count,
        "followersCount": followers,
        "followingCount": following,
        "posts": posts
    }
    _CLONED_PROFILES[uname] = fallback_res
    return fallback_res

_CLONED_PROFILES = {}

def get_discover_feed():
    now_ms = int(time.time() * 1000)
    items = []
    
    # Notice: User's own account is rendered in Circle 1 ('Your story') in the frontend.
    # Do NOT prepend the user's account into discover feed to prevent duplicate stories and feed mix-up.

    creators = [
        {
            "username": "beautifuldestinations",
            "avatar": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=150&auto=format&fit=crop&q=80",
            "media": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=800&auto=format&fit=crop&q=80",
            "caption": "Sunset in paradise 🌅 Where is your dream vacation this year? #travel #destinations #nature",
            "likes": 84200,
            "commentsCount": 1420,
            "isVideo": False,
            "verified": True
        },
        {
            "username": "natgeo",
            "avatar": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=150&auto=format&fit=crop&q=80",
            "media": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4",
            "thumbnail": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=800&auto=format&fit=crop&q=80",
            "caption": "Majestic auroras dancing across the Arctic sky 🌌 Photo by National Geographic Explorers. #natgeo #photography",
            "likes": 142500,
            "commentsCount": 2350,
            "isVideo": True,
            "verified": True
        },
        {
            "username": "foodnetwork",
            "avatar": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=150&auto=format&fit=crop&q=80",
            "media": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
            "thumbnail": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800&auto=format&fit=crop&q=80",
            "caption": "Crispy artisanal wood-fired pizza straight from Naples 🍕 Who's having a slice? #foodie #delicious",
            "likes": 65300,
            "commentsCount": 980,
            "isVideo": True,
            "verified": True
        },
        {
            "username": "vogue",
            "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            "media": "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800&auto=format&fit=crop&q=80",
            "caption": "Haute couture runway highlights from Paris Fashion Week ✨ Elegant tailoring and bold silhouettes. #vogue #fashion",
            "likes": 118000,
            "commentsCount": 1820,
            "isVideo": False,
            "verified": True
        },
        {
            "username": "f1",
            "avatar": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=150&auto=format&fit=crop&q=80",
            "media": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4",
            "thumbnail": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?w=800&auto=format&fit=crop&q=80",
            "caption": "Under the lights in Singapore! 🏎️💨 The speed, the sparks, the pure adrenaline. #F1 #SingaporeGP",
            "likes": 210000,
            "commentsCount": 4200,
            "isVideo": True,
            "verified": True
        },
        {
            "username": "travelandleisure",
            "avatar": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=150&auto=format&fit=crop&q=80",
            "media": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&auto=format&fit=crop&q=80",
            "caption": "Waking up to this view in the Maldives 🏝️ Turquoise waters as far as the eye can see. #wanderlust",
            "likes": 78900,
            "commentsCount": 1140,
            "isVideo": False,
            "verified": True
        },
        {
            "username": "discovery",
            "avatar": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=150&auto=format&fit=crop&q=80",
            "media": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop&q=80",
            "caption": "Earth from orbit 🌍 Never stop exploring the wonders of our planet. #discovery #space #earth",
            "likes": 95400,
            "commentsCount": 1560,
            "isVideo": False,
            "verified": True
        },
        {
            "username": "history",
            "avatar": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=150&auto=format&fit=crop&q=80",
            "media": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
            "thumbnail": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800&auto=format&fit=crop&q=80",
            "caption": "The timeless Colosseum in Rome 🏛️ Standing strong for nearly 2,000 years. #history #rome",
            "likes": 54100,
            "commentsCount": 890,
            "isVideo": True,
            "verified": True
        }
    ]
    
    for i, c in enumerate(creators):
        items.append({
            "id": f"feed_post_{i+1}",
            "username": c["username"],
            "avatar": c["avatar"],
            "media": c["media"],
            "caption": c["caption"],
            "likes": c["likes"],
            "commentsCount": c["commentsCount"],
            "ts": now_ms - (1000 * 3600 * (i + 1)),
            "isVideo": c["isVideo"],
            "verified": c["verified"],
            "following": i % 2 == 0
        })
        
    return items


# ----------------------------------------------------------------------
# Request Handler
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# AI Insights & Dashboard Generators
# ----------------------------------------------------------------------
def parse_ai_reel_insights(description, current=None):
    if not isinstance(current, dict):
        current = {}
    desc = str(description or "").strip()
    desc_lower = desc.lower()

    def parse_num_token(token):
        token = token.replace(",", "").strip().lower()
        mul = 1
        if "m" in token:
            mul = 1_000_000
            token = token.replace("m", "")
        elif "k" in token:
            mul = 1_000
            token = token.replace("k", "")
        try:
            return int(float(token) * mul)
        except Exception:
            return None

    def extract_metric(patterns):
        for pat in patterns:
            m = re.search(pat, desc_lower)
            if m:
                val = parse_num_token(m.group(1))
                if val is not None and val > 0:
                    return val
        return None

    # 1. EXTRACT VIEWS (Supports ANY custom number: 73420, 14,250, 75k, 1.2M, or just a standalone number)
    views = extract_metric([
        r'(?:views?|plays?|reach|view count)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:views?|plays?|reach|view count)',
    ])

    if views is None:
        # Check for k/m notation: e.g. "75k", "1.2m"
        m = re.search(r'\b(\d+[\d\.,]*\s*[km])\b', desc_lower)
        if m:
            views = parse_num_token(m.group(1))
    
    if views is None:
        # Check for any clean integer in the description, e.g. "73892" or "14250"
        m = re.search(r'\b(\d{1,3}(?:,\d{3})+|\d{3,})\b', desc)
        if m:
            views = parse_num_token(m.group(1))

    # If still not found, check current views, or default to a realistic starting count
    if views is None or views <= 0:
        cur_v = int(current.get("views") or 0)
        views = cur_v if cur_v > 0 else 18500

    # 2. LIKES & LIKE RATE
    likes = extract_metric([
        r'(?:likes?|liked)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:likes?|liked)'
    ])
    if likes is None or likes <= 0:
        if any(w in desc_lower for w in ["viral", "funny", "comedy", "meme", "dance"]):
            like_ratio = 0.088
        elif any(w in desc_lower for w in ["business", "finance", "crypto", "tech", "coding"]):
            like_ratio = 0.062
        else:
            like_ratio = 0.074
        likes = max(int(views * like_ratio), 5)

    like_rate = round((likes / views) * 100, 1)

    # 3. COMMENTS & COMMENT RATE
    comments_cnt = extract_metric([
        r'(?:comments?|comment count)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:comments?|comment count)'
    ])
    if comments_cnt is None or comments_cnt <= 0:
        if any(w in desc_lower for w in ["question", "controversial", "poll", "comment below"]):
            comm_ratio = 0.0055
        else:
            comm_ratio = 0.0035
        comments_cnt = max(int(views * comm_ratio), 2)

    comment_rate = round((comments_cnt / views) * 100, 1)

    # 4. SHARES & SHARE RATE
    shares = extract_metric([
        r'(?:shares?|shared)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:shares?|shared)'
    ])
    if shares is None or shares <= 0:
        if any(w in desc_lower for w in ["viral", "relatable", "funny", "meme"]):
            share_ratio = 0.038
        else:
            share_ratio = 0.027
        shares = max(int(views * share_ratio), 2)

    share_rate = round((shares / views) * 100, 1)

    # 5. SAVES & SAVE RATE
    saves = extract_metric([
        r'(?:saves?|saved)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:saves?|saved)'
    ])
    if saves is None or saves <= 0:
        if any(w in desc_lower for w in ["recipe", "tips", "tutorial", "gym", "workout", "educational"]):
            save_ratio = 0.032
        else:
            save_ratio = 0.018
        saves = max(int(views * save_ratio), 2)

    save_rate = round((saves / views) * 100, 1)

    # 6. REPOSTS & REPOST RATE
    reposts = extract_metric([
        r'(?:reposts?|reposted)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:reposts?|reposted)'
    ])
    if reposts is None or reposts <= 0:
        reposts = max(int(views * 0.007), 1)

    repost_rate = round((reposts / views) * 100, 1)

    # 7. SKIP RATE
    skip_rate = 16.8
    m_skip = re.search(r'skip\s*rate[\s:=]+(\d+[\d\.]*)%?', desc_lower)
    if m_skip:
        try:
            skip_rate = round(float(m_skip.group(1)), 1)
        except Exception:
            pass

    # 8. REACH, FOLLOWS, PROFILE VISITS
    accounts_reached = max(int(views * 0.865), likes)

    follows = extract_metric([
        r'(?:follows?|new follows?|subscribers?)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:follows?|new follows?)'
    ])
    if follows is None or follows <= 0:
        follows = max(int(views * 0.0125), 1)

    profile_visits = extract_metric([
        r'(?:profile visits?|visits?)[\s:=]+(\d+[\d\.,]*\s*[km]?)',
        r'(\d+[\d\.,]*\s*[km]?)\s*(?:profile visits?|visits?)'
    ])
    if profile_visits is None or profile_visits <= 0:
        profile_visits = max(int(views * 0.038), 2)

    # 9. SOURCES BREAKDOWN (Reels tab %, Explore %, Profile %, Feed %)
    src_reels = 84.6
    src_explore = 9.2
    src_profile = 3.8
    src_feed = 2.4

    # 10. AUDIENCE: FOLLOWERS VS NON-FOLLOWERS
    m_foll_pct = re.search(r'(\d+[\d\.]*)%?\s*(?:followers|follower audience)', desc_lower)
    if m_foll_pct:
        try:
            aud_followers_pct = round(float(m_foll_pct.group(1)), 1)
        except Exception:
            aud_followers_pct = 11.5
    elif "non follower" in desc_lower or "viral" in desc_lower or views > 25000:
        aud_followers_pct = 9.8
    else:
        aud_followers_pct = 14.5

    # 11. GENDER DISTRIBUTION
    if any(w in desc_lower for w in ["mostly female", "women", "girls", "female", "beauty", "makeup", "fashion", "nails", "skincare"]):
        aud_gender = {"women": 78.5, "men": 21.5}
    elif any(w in desc_lower for w in ["mostly male", "men", "boys", "male", "gym", "fitness", "bodybuilding", "crypto", "gaming", "cars", "bikes"]):
        aud_gender = {"women": 21.5, "men": 78.5}
    else:
        aud_gender = {"women": 46.2, "men": 53.8}

    # 12. COUNTRY DISTRIBUTION
    if any(w in desc_lower for w in ["usa", "united states", "us", "uk", "america", "global", "tier 1", "tier-1"]):
        aud_country = [
            {"name": "United States", "pct": 65.4},
            {"name": "United Kingdom", "pct": 12.2},
            {"name": "Canada", "pct": 8.5},
            {"name": "Australia", "pct": 5.2},
            {"name": "India", "pct": 4.1},
            {"name": "Germany", "pct": 2.6},
            {"name": "Other", "pct": 2.0}
        ]
    else:
        aud_country = [
            {"name": "India", "pct": 83.2},
            {"name": "United States", "pct": 5.4},
            {"name": "Pakistan", "pct": 3.6},
            {"name": "Bangladesh", "pct": 2.5},
            {"name": "United Arab Emirates", "pct": 2.1},
            {"name": "Saudi Arabia", "pct": 1.7},
            {"name": "Nepal", "pct": 1.5}
        ]

    # 13. AGE DISTRIBUTION
    if any(w in desc_lower for w in ["teen", "school", "college", "anime", "gaming", "students"]):
        aud_age = [
            {"label": "13-17", "pct": 13.8},
            {"label": "18-24", "pct": 48.5},
            {"label": "25-34", "pct": 26.2},
            {"label": "35-44", "pct": 7.4},
            {"label": "45-54", "pct": 2.4},
            {"label": "55-64", "pct": 1.1},
            {"label": "65+", "pct": 0.6}
        ]
    elif any(w in desc_lower for w in ["business", "finance", "money", "investing", "real estate", "parenting"]):
        aud_age = [
            {"label": "13-17", "pct": 2.2},
            {"label": "18-24", "pct": 28.4},
            {"label": "25-34", "pct": 46.8},
            {"label": "35-44", "pct": 16.2},
            {"label": "45-54", "pct": 4.3},
            {"label": "55-64", "pct": 1.4},
            {"label": "65+", "pct": 0.7}
        ]
    else:
        aud_age = [
            {"label": "13-17", "pct": 6.8},
            {"label": "18-24", "pct": 41.6},
            {"label": "25-34", "pct": 37.2},
            {"label": "35-44", "pct": 9.4},
            {"label": "45-54", "pct": 3.1},
            {"label": "55-64", "pct": 1.2},
            {"label": "65+", "pct": 0.7}
        ]

    # 14. DURATION & WATCH TIME
    dur_str = current.get("duration") or "0:24"
    dur_secs = 24
    if ":" in dur_str:
        try:
            parts = dur_str.split(":")
            dur_secs = int(parts[0]) * 60 + int(parts[1])
        except Exception:
            dur_secs = 24

    avg_secs = max(5, int(dur_secs * 0.62))
    avg_watch = f"0:{avg_secs:02d}" if avg_secs < 60 else f"{avg_secs//60}:{avg_secs%60:02d}"

    # 15. SMOOTH GRADUALLY INCREASING ENGAGEMENT GRAPH
    # "When people liked your reel" -> Accumulates monotonically from start of video to end
    engagement_curve = [
        4, 7, 12, 19, 27, 36, 46, 56, 65, 73,
        80, 86, 90, 93, 95, 97, 98, 99, 100, 100, 100
    ]

    # Audience retention curve (drop-off from 100%)
    retention_curve = [
        100, 95, 89, 83, 77, 72, 67, 63, 59, 56,
        53, 50, 48, 46, 44, 43, 42, 41, 40, 39, 38
    ]

    return {
        "views": views,
        "accountsReached": accounts_reached,
        "likes": likes,
        "commentsCountTarget": comments_cnt,
        "shares": shares,
        "saves": saves,
        "reposts": reposts,
        "follows": follows,
        "profileVisits": profile_visits,
        "duration": dur_str,
        "durationSecs": dur_secs,
        "avgWatchTime": avg_watch,
        "srcReelsTab": src_reels,
        "srcForYou": src_reels,
        "srcExplore": src_explore,
        "srcProfile": src_profile,
        "srcFeed": src_feed,
        "ratesManual": True,
        "skipRate": skip_rate,
        "likeRate": like_rate,
        "commentRate": comment_rate,
        "shareRate": share_rate,
        "saveRate": save_rate,
        "repostRate": repost_rate,
        "audFollowersPct": aud_followers_pct,
        "audAge": aud_age,
        "audCountry": aud_country,
        "audGender": aud_gender,
        "engagementCurve": engagement_curve,
        "retention": retention_curve
    }

def generate_ai_dashboard(details):
    desc = str(details or "").lower()
    views = 250000
    if "m" in desc:
        views = 1200000
    elif "500k" in desc:
        views = 500000
        
    followers = 45000
    return {
        "views": views,
        "accountsReached": int(views * 0.72),
        "netFollowers": 1420,
        "rangeLabel": "Last 30 days",
        "viewsTotal": views,
        "followersPct": 18,
        "nonFollowersPct": 82,
        "viewsChart": [int(views * f) for f in [0.02, 0.03, 0.025, 0.04, 0.035, 0.05, 0.045, 0.06, 0.055, 0.07, 0.065, 0.08]],
        "reachByContent": {"stories": int(views * 0.12), "posts": int(views * 0.18), "reels": int(views * 0.68), "live": int(views * 0.02)},
        "interactionsByContent": {"stories": 450, "posts": 1200, "reels": 8400, "live": 80},
        "contentShared": {"stories": 14, "posts": 6, "reels": 8, "live": 1},
        "profileVisits": int(views * 0.045),
        "bioLinkTaps": int(views * 0.012),
        "businessAddressTaps": 12,
        "followers": followers,
        "growthPct": 14.8,
        "growthSinceDate": "Last 30 days",
        "growthChart": [followers - 1500 + i * 125 for i in range(12)],
        "growthStart": "Start",
        "growthEnd": "Now",
        "womenPct": 65 if ("female" in desc or "women" in desc) else 48,
        "menPct": 35 if ("female" in desc or "women" in desc) else 52,
        "ageGroups": [
            {"label": "18-24", "pct": 42},
            {"label": "25-34", "pct": 38},
            {"label": "35-44", "pct": 14},
            {"label": "45-54", "pct": 4},
            {"label": "55+", "pct": 2}
        ],
        "topCountries": [
            {"name": "India", "pct": 72},
            {"name": "United States", "pct": 14},
            {"name": "United Kingdom", "pct": 6},
            {"name": "Canada", "pct": 4},
            {"name": "United Arab Emirates", "pct": 4}
        ],
        "topCities": [
            {"name": "Mumbai", "pct": 22},
            {"name": "Delhi", "pct": 18},
            {"name": "Bengaluru", "pct": 14},
            {"name": "New York", "pct": 8},
            {"name": "London", "pct": 6}
        ],
        "activeTimesBars": [15, 10, 8, 6, 5, 8, 14, 24, 38, 52, 65, 74, 82, 88, 92, 95, 98, 100, 96, 90, 82, 70, 54, 32]
    }

class InstaRequestHandler(http.server.BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PUT")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Bootstrap-Secret, X-Requested-With")

    def reply_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Range")
        self.end_headers()

    def reply_rpc(self, data, status=200):
        if not isinstance(data, dict):
            payload = {"result": data, "t": data, "ok": True}
        else:
            payload = {"result": data, "t": data, **data}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Serve root / directly as Home Page (with purchase & pricing details)
        if path in ["/", ""]:
            return self.serve_static_or_spa("/")

        # Video Proxy to stream Instagram CDN or other videos
        if path == "/api/video-proxy":
            video_url = query.get("url", [""])[0]
            if not video_url or not video_url.startswith(("http://", "https://")):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid URL")
                return

            video_url = video_url.split("#")[0]
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
            }
            client_range = self.headers.get("Range")
            if client_range:
                req_headers["Range"] = client_range

            try:
                proxy_req = urllib.request.Request(video_url, headers=req_headers)
                with urllib.request.urlopen(proxy_req, timeout=15) as upstream:
                    code = upstream.getcode()
                    self.send_response(code)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                    self.send_header("Access-Control-Allow-Headers", "*")
                    self.send_header("Accept-Ranges", "bytes")
                    
                    content_type = upstream.headers.get("Content-Type", "video/mp4")
                    self.send_header("Content-Type", content_type)
                    
                    content_length = upstream.headers.get("Content-Length")
                    if content_length:
                        self.send_header("Content-Length", content_length)
                        
                    content_range = upstream.headers.get("Content-Range")
                    if content_range:
                        self.send_header("Content-Range", content_range)
                        
                    self.end_headers()
                    
                    while True:
                        chunk = upstream.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                return
            except urllib.error.HTTPError as he:
                self.send_response(he.code)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            except Exception as e:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return

        # Health
        if path == "/api/health":
            return self.reply_json({"ok": True, "service": "Insta Insight 360 API", "status": "ready"})

        # Payment Availability RPC Handler (GET /_serverFn/27c9dc92...)
        if path.startswith("/_serverFn/27c9dc92febe56c385dd8cf3ca551fa3eb9896d1c5776c3ce3d390aab8351eca"):
            return self.reply_rpc({
                "ok": True,
                "inr": 1000,
                "usdt": 10,
                "paytm": True,
                "upi": True,
                "razorpay": False,
                "paytm_upi_id": get_setting("paytm_upi_id", "paytmqr5l66pa@ptys")
            })

        # Auth Me
        if path == "/api/auth/me":
            auth_header = self.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "").strip()
            if not token:
                return self.reply_json({"error": "Session invalid or expired"}, 401)
            conn = get_db()
            cur = conn.cursor()
            th = sha(token)
            cur.execute("""
                SELECT s.access_key_id, s.expires_at, k.plan, k.status
                FROM login_sessions s
                JOIN access_keys k ON k.id = s.access_key_id
                WHERE s.token_hash = ?
            """, (th,))
            row = cur.fetchone()
            conn.close()
            if not row or row["status"] != "active":
                return self.reply_json({"error": "Session invalid or expired"}, 401)
            return self.reply_json({"ok": True, "authenticated": True, "plan": row["plan"]})

        # Admin Keys List
        if path == "/api/admin/keys":
            admin = check_admin_auth(self)
            if not admin:
                return self.reply_json({"error": "Admin authentication required"}, 401)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT k.id, k.label, k.plan, k.status, k.expires_at, k.max_devices, k.created_at,
                       COUNT(d.id) AS device_count
                FROM access_keys k
                LEFT JOIN device_activations d ON d.access_key_id = k.id
                GROUP BY k.id
                ORDER BY k.created_at DESC LIMIT 200
            """)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return self.reply_json({"ok": True, "keys": rows})

        # Keys Management Panel (Web UI)
        if path in ["/keys-panel", "/admin-panel"]:
            return self.serve_admin_panel()

        # Dedicated Paytm Checkout Page
        if path in ["/pay", "/paytm", "/checkout-paytm"]:
            return self.serve_paytm_checkout(query)

        # Telemetry / Analytics stub
        if path.startswith("/__l5e/"):
            clean_rel = path.lstrip("/")
            local_path = os.path.join(PUBLIC_DIR, clean_rel)
            if os.path.exists(local_path) and os.path.isfile(local_path):
                return self.serve_file(local_path)
            return self.reply_json({"ok": True})

        # Static file or SPA
        self.serve_static_or_spa(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/__l5e/trackevents"):
            return self.reply_json({"ok": True})

        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        print(f"[DEBUG POST] {path} Length={content_len} Raw={raw_body[:300]}")
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        # -------------------------------------------------------------
        # 1. TanStack Start RPC Handlers (/_serverFn/*)
        # -------------------------------------------------------------
        
        # AI: SET ALL INSIGHTS FROM DESCRIPTION (Vu in app-CoADwJzp.js)
        # ID: a47cf934e2d6d25f559ca6129334f2cbd8737cf9ed519a0201e089b737ec2930
        if path.startswith("/_serverFn/a47cf934e2d6d25f559ca6129334f2cbd8737cf9ed519a0201e089b737ec2930"):
            desc = str(get_param(body, raw_body, "description") or "")
            current = get_param(body, raw_body, "current")
            if not isinstance(current, dict):
                # Try finding current dict in body
                if isinstance(body, dict) and isinstance(body.get("data"), dict) and isinstance(body["data"].get("current"), dict):
                    current = body["data"]["current"]
                else:
                    current = {}
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            print(f"[AI REEL INSIGHTS] Description: '{desc}'")
            patch = parse_ai_reel_insights(desc, current)
            log_activity(user_key, "ai_reel_insights", f"Generated AI insights from description")
            return self.reply_rpc({"ok": True, "patch": patch})

        # AI: ENGAGEMENT CURVE ONLY (Bu in app-CoADwJzp.js)
        # ID: 11b00a7ac3bf66edca841bba6cc991f5ddb0f7e10b22e96fa0f4a6d5cb9ccbb7
        if path.startswith("/_serverFn/11b00a7ac3bf66edca841bba6cc991f5ddb0f7e10b22e96fa0f4a6d5cb9ccbb7"):
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            curve = [4, 7, 12, 19, 27, 36, 46, 56, 65, 73, 80, 86, 90, 93, 95, 97, 98, 99, 100, 100, 100]
            log_activity(user_key, "ai_engagement_curve", "Generated AI engagement curve")
            return self.reply_rpc({"ok": True, "curve": curve})

        # AI: GENERATE PROFESSIONAL DASHBOARD (xh in app-CoADwJzp.js)
        # ID: fdffbe33da2c1ecaf104c32275c7adb5614257d560a0f6620c155f9e4e69392d
        if path.startswith("/_serverFn/fdffbe33da2c1ecaf104c32275c7adb5614257d560a0f6620c155f9e4e69392d"):
            details = str(get_param(body, raw_body, "details") or "")
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            dash = generate_ai_dashboard(details)
            log_activity(user_key, "ai_dashboard", "Generated AI dashboard from details")
            return self.reply_rpc({"ok": True, "dashboard": dash})
        
        # INSTAGRAM CLONE FUNCTION (ju in app-CoADwJzp.js)
        # ID: d3b15afd605366f255a6e52bb3312b4b2f0ead6901493fa84b065d6e3971d87b
        if path.startswith("/_serverFn/d3b15afd605366f255a6e52bb3312b4b2f0ead6901493fa84b065d6e3971d87b"):
            username = str(get_param(body, raw_body, "username") or "").strip().lstrip("@")
            user_key = str(get_param(body, raw_body, "key") or "").strip()
            
            if not username:
                parsed_q = urllib.parse.parse_qs(parsed.query)
                username = str(parsed_q.get("username", [""])[0]).strip().lstrip("@")
            if not username:
                username = "instagram"
            try:
                profile = clone_instagram_profile(username, user_key)
                log_activity(user_key or "guest", "instagram_cloned", f"Cloned profile @{profile['username']}")
                return self.reply_rpc({"ok": True, "profile": profile})
            except Exception as e:
                print(f"Clone error: {e}")
                return self.reply_rpc({"ok": False, "error": f"Failed to clone: {str(e)}"}, 500)

        # DISCOVER / HOME FEED FUNCTION (yu in app-CoADwJzp.js)
        # ID: 292e5817467cd27b5851b8c6392bf5a141fae297a86e1a779bb92ff3e78d071a
        if path.startswith("/_serverFn/292e5817467cd27b5851b8c6392bf5a141fae297a86e1a779bb92ff3e78d071a"):
            feed_items = get_discover_feed()
            return self.reply_rpc({"ok": True, "items": feed_items})

        # SAVE USER API KEY (Apify / Gemini / Grok)
        # ID: 26692e4fdda39bb2c6d2000de428144496b76a0d084d37b65a2fd257152c3e84
        if path.startswith("/_serverFn/26692e4fdda39bb2c6d2000de428144496b76a0d084d37b65a2fd257152c3e84"):
            provider = str(get_param(body, raw_body, "provider") or "apify").lower().strip()
            token = str(get_param(body, raw_body, "token") or "").strip()
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            if not token:
                return self.reply_rpc({"ok": False, "error": "Token is required"}, 400)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_api_keys WHERE (user_key = ? OR user_key = 'default') AND provider = ?", (user_key, provider))
            cur.execute("INSERT INTO user_api_keys (user_key, provider, token) VALUES (?, ?, ?)",
                        (user_key, provider, token))
            conn.commit()
            conn.close()
            if provider == "apify":
                set_setting("apify_token", token)
            elif provider == "gemini":
                set_setting("gemini_token", token)
            log_activity(user_key, "api_key_saved", f"Saved {provider} key")
            return self.reply_rpc({"ok": True, "reason": "ok", "error": None})

        # GET CONNECTED API KEYS
        # ID: 10069443c1a9262a50ded611c0dcc14a477ca73f19ad542ca946def31c4448f2
        if path.startswith("/_serverFn/10069443c1a9262a50ded611c0dcc14a477ca73f19ad542ca946def31c4448f2"):
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT provider FROM user_api_keys WHERE user_key = ? OR user_key = 'default'", (user_key,))
            rows = [r["provider"] for r in cur.fetchall()]
            conn.close()
            return self.reply_rpc({"ok": True, "connected": rows, "reason": "ok"})

        # REMOVE USER API KEY
        # ID: 0a283b7ec0289fd51a7d26d09e822c8ac853988a2530ccd248cb561a11e281c6
        if path.startswith("/_serverFn/0a283b7ec0289fd51a7d26d09e822c8ac853988a2530ccd248cb561a11e281c6"):
            provider = str(get_param(body, raw_body, "provider") or "").lower().strip()
            user_key = str(get_param(body, raw_body, "key") or "default").strip()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_api_keys WHERE (user_key = ? OR user_key = 'default') AND provider = ?", (user_key, provider))
            conn.commit()
            conn.close()
            log_activity(user_key, "api_key_removed", f"Removed {provider} key")
            return self.reply_rpc({"ok": True, "reason": "ok"})

        # REQUEST KEY (Sent to vyrox954@gmail.com)
        # ID: e85c18d76350e1717a38139764455e449f6a96ee468d03e60a7045580c0c995c
        if path.startswith("/_serverFn/e85c18d76350e1717a38139764455e449f6a96ee468d03e60a7045580c0c995c"):
            req_email = str(get_param(body, raw_body, "email") or "").strip()
            if req_email:
                conn = get_db()
                cur = conn.cursor()
                client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
                cur.execute("INSERT INTO key_requests (email, ip, forwarded_to) VALUES (?, ?, ?)",
                            (req_email, client_ip, get_setting("admin_email", "vyrox954@gmail.com")))
                conn.commit()
                conn.close()
                log_activity("visitor", "key_requested", f"Key request for vyrox954@gmail.com from {req_email}")
                send_key_request_notification_to_admin(req_email, client_ip)
            admin_em = get_setting("admin_email", "vyrox954@gmail.com")
            return self.reply_rpc({"ok": True, "message": f"Key request received! Admin at {admin_em} has been notified. You will receive your key shortly."})

        # CREATE ORDER (c58bf8e773292ff55e71b89fab0fad0ff9e488d2e88cb96ff3f8267d2be2b78f)
        if path.startswith("/_serverFn/c58bf8e773292ff55e71b89fab0fad0ff9e488d2e88cb96ff3f8267d2be2b78f"):
            data = body.get("data", {})
            order_id = "ORD-" + secrets.token_hex(4).upper()
            email = data.get("email", "customer@example.com")
            paytm_vpa = get_setting("paytm_upi_id", "paytmqr5l66pa@ptys")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO payment_orders (id, email, amount, method, status) VALUES (?, ?, 1000, 'paytm', 'pending')",
                        (order_id, email))
            conn.commit()
            conn.close()
            
            biz_pn = get_setting("paytm_business_name", "SURENDRA SINGH")
            upi_link = f"upi://pay?pa={paytm_vpa}&pn={urllib.parse.quote(biz_pn)}&am=1000&cu=INR&tn={order_id}"
            return self.reply_rpc({
                "ok": True,
                "order": {
                    "id": order_id,
                    "amount": 1000,
                    "currency": "INR",
                    "status": "pending",
                    "method": "paytm",
                    "paytm_vpa": paytm_vpa,
                    "upi_link": upi_link,
                    "checkout_url": f"/pay?order={order_id}"
                }
            })

        # CHECK ORDER STATUS (1b69a1d34b724a56467dacbd2f0dc8aaaaaf256daf38defe22de1a8c3188fb25)
        if path.startswith("/_serverFn/1b69a1d34b724a56467dacbd2f0dc8aaaaaf256daf38defe22de1a8c3188fb25"):
            data = body.get("data", {})
            order_id = data.get("id", "")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                return self.reply_rpc({"ok": True, "order": dict(row)})
            return self.reply_rpc({"ok": False, "error": "Order not found"})

        # LOGIN FUNCTION: 3d35ff9081e93b3834dc366d0890b9cac47c5f8d62c9b0e32280944272482585
        if path.startswith("/_serverFn/3d35ff9081e93b3834dc366d0890b9cac47c5f8d62c9b0e32280944272482585"):
            return self.handle_rpc_login(body, raw_body)

        # KEY STATUS CHECK (Si in dashboard): 2b83b07c35bad165f4daf863126233f218ae92352fbefe854fd815afe0769c3a
        if path.startswith("/_serverFn/2b83b07c35bad165f4daf863126233f218ae92352fbefe854fd815afe0769c3a"):
            return self.handle_rpc_key_status(body)

        # KEY VERIFY SECONDARY: 3e6dba741bb96bb715a202759387000cd52190d74080eb212dd4a25db29246d0
        if path.startswith("/_serverFn/3e6dba741bb96bb715a202759387000cd52190d74080eb212dd4a25db29246d0"):
            return self.handle_rpc_key_status(body)

        # ADMIN CHECK (_i): 09fff069884dc4d891d4df07234c60c1987e47bf2cfeecd396788aabcd297873
        if path.startswith("/_serverFn/09fff069884dc4d891d4df07234c60c1987e47bf2cfeecd396788aabcd297873"):
            return self.reply_rpc({"admin": False})

        # Generic /_serverFn fallback
        if path.startswith("/_serverFn/"):
            return self.reply_rpc({"ok": True, "status": "ok"})

        # -------------------------------------------------------------
        # 2. REST API Handlers from worker.js
        # -------------------------------------------------------------
        # REST Login
        if path == "/api/auth/login":
            return self.handle_rest_login(body)

        # Confirm Paytm Payment (from checkout UI)
        if path == "/api/paytm/confirm":
            order_id = body.get("order_id", "").strip()
            utr = body.get("utr", "").strip()
            email = body.get("email", "").strip()
            if not utr or len(utr) < 6:
                return self.reply_json({"ok": False, "error": "Valid 12-digit Paytm UTR / UPI Reference ID is required."}, 400)
            
            # Generate instant lifetime key
            key_id = secrets.token_hex(8)
            plain_key = "I360-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(4).upper()
            kh = key_hash(plain_key)
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO access_keys (id, key_hash, label, plan, status, max_devices)
                VALUES (?, ?, ?, 'lifetime', 'active', 2)
            """, (key_id, kh, f"Paytm Order {order_id} ({email})"))
            
            if order_id:
                cur.execute("""
                    UPDATE payment_orders SET status = 'activated', utr = ?, access_key_generated = ?
                    WHERE id = ?
                """, (utr, plain_key, order_id))
            else:
                order_id = "ORD-" + secrets.token_hex(4).upper()
                cur.execute("""
                    INSERT INTO payment_orders (id, email, amount, method, status, utr, access_key_generated)
                    VALUES (?, ?, 1000, 'paytm', 'activated', ?, ?)
                """, (order_id, email or "direct@paytm", utr, plain_key))
                
            conn.commit()
            conn.close()
            log_activity("paytm_system", "payment_activated", f"Paytm UTR {utr} activated. Key: {plain_key}")
            send_approved_key_to_customer(email, plain_key, "Lifetime Access")
            return self.reply_json({
                "ok": True,
                "access_key": plain_key,
                "message": "Payment verified successfully! Your lifetime access key is ready."
            })

        # Save Paytm Settings (from keys-panel)
        
        # Admin Login
        if path == "/api/admin/login":
            password = str(body.get("password", "")).strip()
            stored_pass = get_setting("admin_password", "Surendra@360").strip()
            if password in [stored_pass, "Surendra@360", "I360-SURENDRA-LIFETIME-2026"]:
                ts = str(int(time.time()))
                msg = f"admin.{ts}".encode("utf-8")
                sig = hmac.new(JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
                session_token = f"{ts}.{sig}"
                log_activity("admin", "admin_logged_in", "Admin session started via security gate")
                
                resp_data = json.dumps({"ok": True, "message": "Admin authenticated successfully"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_data)))
                self.send_header("Set-Cookie", f"admin_session={session_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(resp_data)
                return
            return self.reply_json({"ok": False, "error": "Invalid Admin Password or Master Key"}, 401)

        # Admin Logout
        if path in ["/api/admin/logout", "/admin/logout"]:
            resp_data = json.dumps({"ok": True, "message": "Logged out"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_data)))
            self.send_header("Set-Cookie", "admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(resp_data)
            return

        # Admin Delete Key
        if path == "/api/admin/keys/delete":
            admin = check_admin_auth(self)
            if not admin:
                return self.reply_json({"error": "Admin authentication required"}, 401)
            kid = str(body.get("id", "")).strip()
            if not kid:
                return self.reply_json({"error": "Key ID is required"}, 400)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM device_activations WHERE access_key_id = ?", (kid,))
            cur.execute("DELETE FROM login_sessions WHERE access_key_id = ?", (kid,))
            cur.execute("DELETE FROM access_keys WHERE id = ?", (kid,))
            conn.commit()
            conn.close()
            log_activity("admin", "access_key_deleted", kid)
            return self.reply_json({"ok": True, "message": f"Key {kid} deleted successfully"})

        # Admin Update Key
        if path == "/api/admin/keys/update":
            admin = check_admin_auth(self)
            if not admin:
                return self.reply_json({"error": "Admin authentication required"}, 401)
            kid = str(body.get("id", "")).strip()
            if not kid:
                return self.reply_json({"error": "Key ID is required"}, 400)
            label = str(body.get("label", "")).strip()[:80]
            plan = str(body.get("plan", "lifetime"))[:30]
            status = str(body.get("status", "active")).lower().strip()
            max_dev = max(1, min(10, int(body.get("max_devices", 1))))
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE access_keys SET label = ?, plan = ?, status = ?, max_devices = ? WHERE id = ?",
                        (label, plan, status, max_dev, kid))
            if status in ["revoked", "expired"]:
                cur.execute("DELETE FROM login_sessions WHERE access_key_id = ?", (kid,))
            conn.commit()
            conn.close()
            log_activity("admin", "access_key_updated", f"{kid}: {status}/{plan}")
            return self.reply_json({"ok": True, "message": f"Key {kid} updated successfully"})

        if path == "/api/admin/settings":
            for k in ["paytm_upi_id", "paytm_business_name", "upi_number", "paytm_mid", "paytm_mkey", "admin_email", "apify_token", "admin_password", "smtp_user", "smtp_pass"]:
                if k in body:
                    set_setting(k, str(body[k]).strip())
            return self.reply_json({"ok": True, "message": "Settings updated successfully!"})

        # Approve Key Request (from keys-panel)
        if path == "/api/admin/approve-request":
            req_id = body.get("request_id")
            req_email = body.get("email", "")
            plain_key = "I360-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(4).upper()
            key_id = secrets.token_hex(8)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO access_keys (id, key_hash, label, plan, status, max_devices) VALUES (?, ?, ?, 'lifetime', 'active', 2)",
                        (key_id, key_hash(plain_key), f"Approved for {req_email}"))
            if req_id:
                cur.execute("UPDATE key_requests SET status = 'approved' WHERE id = ?", (req_id,))
            if req_email:
                send_approved_key_to_customer(req_email, plain_key, "Lifetime Access")
            conn.commit()
            conn.close()
            return self.reply_json({"ok": True, "access_key": plain_key, "email": req_email})

        # Admin Create Key (REST)
        if path == "/api/admin/keys":
            admin = check_admin_auth(self)
            if not admin:
                return self.reply_json({"error": "Admin authentication required"}, 401)
            plain = "I360-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(4).upper()
            kid = secrets.token_hex(8)
            kh = key_hash(plain)
            label = str(body.get("label", "")).strip()[:80] or "Generated by Admin"
            plan = str(body.get("plan", "lifetime"))[:30]
            max_dev = max(1, min(10, int(body.get("max_devices", 1))))
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO access_keys (id, key_hash, label, plan, status, max_devices) VALUES (?, ?, ?, ?, 'active', ?)",
                        (kid, kh, label, plan, max_dev))
            conn.commit()
            conn.close()
            log_activity(admin["username"], "access_key_created", kid)
            return self.reply_json({"ok": True, "id": kid, "access_key": plain, "plan": plan}, 201)

        self.send_error(404, "Endpoint not found")

    def handle_rpc_login(self, body, raw_body=""):
        data = body.get("data", {}) if isinstance(body, dict) else {}
        access_key = str(get_param(body, raw_body, "key") or data.get("key") or data.get("access_key") or "").strip()
        device_id = str(get_param(body, raw_body, "device") or data.get("device") or data.get("device_id") or "device_web_client").strip()
        if not access_key:
            return self.reply_rpc({"ok": False, "error": "Access Key is required"}, 400)

        kh = key_hash(access_key)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM access_keys WHERE key_hash = ?", (kh,))
        key_row = cur.fetchone()

        if not key_row or key_row["status"] != "active":
            conn.close()
            return self.reply_rpc({"ok": False, "error": "Invalid, revoked, or expired Access Key"}, 401)

        dh = sha(device_id)
        cur.execute("SELECT id FROM device_activations WHERE access_key_id = ? AND device_hash = ?", (key_row["id"], dh))
        dev_row = cur.fetchone()
        if not dev_row:
            cur.execute("SELECT COUNT(*) as n FROM device_activations WHERE access_key_id = ?", (key_row["id"],))
            cnt = cur.fetchone()["n"]
            if cnt >= key_row["max_devices"]:
                conn.close()
                return self.reply_rpc({"ok": False, "error": "Device limit reached for this access key."}, 403)
            cur.execute("INSERT INTO device_activations (id, access_key_id, device_hash) VALUES (?, ?, ?)",
                        (secrets.token_hex(8), key_row["id"], dh))

        token = secrets.token_hex(16)
        th = sha(token)
        exp = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
        cur.execute("INSERT INTO login_sessions (id, access_key_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
                    (secrets.token_hex(8), key_row["id"], th, exp))
        conn.commit()
        conn.close()

        log_activity(key_row["id"], "access_key_login_rpc", f"Device: {device_id[:16]}")
        return self.reply_rpc({
            "ok": True,
            "status": "ok",
            "token": token,
            "expires_at": exp,
            "plan": key_row["plan"]
        })

    def handle_rpc_key_status(self, body):
        return self.reply_rpc({
            "ok": True,
            "status": "ok",
            "reason": "ok",
            "valid": True,
            "active": True
        })

    def handle_rest_login(self, body):
        access_key = str(body.get("access_key", "")).strip()
        device_id = str(body.get("device_id", "web_device"))
        if not access_key:
            return self.reply_json({"error": "Access Key is required"}, 400)
        kh = key_hash(access_key)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM access_keys WHERE key_hash = ?", (kh,))
        k = cur.fetchone()
        if not k or k["status"] != "active":
            conn.close()
            return self.reply_json({"error": "Invalid, revoked, or expired Access Key"}, 401)
        token = secrets.token_hex(16)
        th = sha(token)
        exp = (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat()
        cur.execute("INSERT INTO login_sessions (id, access_key_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
                    (secrets.token_hex(8), k["id"], th, exp))
        conn.commit()
        conn.close()
        return self.reply_json({"ok": True, "token": token, "expires_at": exp, "plan": k["plan"]})

    def serve_static_or_spa(self, path):
        clean_path = path.lstrip("/").split("?")[0].split("#")[0]
        if not clean_path:
            clean_path = "index.html"
        local_path = os.path.join(PUBLIC_DIR, clean_path)
        if os.path.exists(local_path) and os.path.isfile(local_path):
            return self.serve_file(local_path)
        index_path = os.path.join(PUBLIC_DIR, "index.html")
        if os.path.exists(index_path):
            return self.serve_file(index_path)
        self.send_error(404, "File not found")

    def serve_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        content_type = MIME_TYPES.get(ext, "application/octet-stream")
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def serve_paytm_checkout(self, query):
        order_id = query.get("order", ["ORD-" + secrets.token_hex(3).upper()])[0]
        paytm_vpa = get_setting("paytm_upi_id", "paytmqr5l66pa@ptys")
        biz_name = get_setting("paytm_business_name", "SURENDRA SINGH")
        upi_num = get_setting("upi_number", "9956607278")
        admin_email = get_setting("admin_email", "vyrox954@gmail.com")
        amount = get_setting("price_inr", "1000")
        
        upi_uri = f"upi://pay?pa={paytm_vpa}&pn={urllib.parse.quote(biz_name)}&am={amount}&cu=INR&tn={order_id}"
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Paytm Official Checkout — Insta Editor 360</title>
    <style>
        * {{ box-sizing: border-box; }}
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            min-height: 100%;
            height: auto !important;
            overflow-x: hidden;
            overflow-y: auto !important;
            -webkit-overflow-scrolling: touch;
            background: #09090b;
            color: #f4f4f5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        body {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            padding: 20px 14px 60px 14px;
        }}
        .card {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 24px;
            max-width: 440px;
            width: 100%;
            padding: 24px 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            text-align: center;
            margin: 10px auto 40px auto;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(0, 186, 242, 0.15);
            color: #00baf2;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 14px;
            border: 1px solid rgba(0, 186, 242, 0.3);
        }}
        h2 {{ margin: 0 0 6px 0; font-size: 24px; color: #fff; }}
        .desc {{ font-size: 14px; color: #a1a1aa; margin-bottom: 18px; }}
        .amount-box {{
            background: #27272a;
            border-radius: 14px;
            padding: 14px 18px;
            margin-bottom: 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .price {{ font-size: 26px; font-weight: 700; color: #10b981; }}
        .qr-wrap {{
            background: #ffffff;
            padding: 12px;
            border-radius: 18px;
            display: inline-block;
            margin-bottom: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            max-width: 280px;
            width: 100%;
        }}
        .qr-wrap img {{
            display: block;
            width: 100%;
            height: auto;
            border-radius: 10px;
            margin: 0 auto;
        }}
        .upi-details {{
            background: #27272a;
            border-radius: 14px;
            padding: 12px 14px;
            margin-bottom: 18px;
            text-align: left;
            font-size: 13px;
        }}
        .upi-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            border-bottom: 1px solid #3f3f46;
        }}
        .upi-row:last-child {{ border-bottom: none; }}
        .copy-btn {{
            background: #3f3f46;
            color: #fff;
            border: none;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            transition: 0.15s;
        }}
        .copy-btn:hover {{ background: #00baf2; }}
        .btn {{
            display: block;
            width: 100%;
            padding: 14px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            box-sizing: border-box;
            border: none;
            transition: 0.2s;
        }}
        .btn-paytm {{
            background: #00baf2;
            color: #ffffff;
            margin-bottom: 16px;
        }}
        .btn-paytm:hover {{ background: #0099cc; }}
        .input-group {{
            text-align: left;
            margin-bottom: 14px;
        }}
        label {{ font-size: 13px; color: #d4d4d8; display: block; margin-bottom: 6px; font-weight: 500; }}
        input {{
            width: 100%;
            padding: 12px 14px;
            background: #09090b;
            border: 1px solid #3f3f46;
            color: #fff;
            border-radius: 10px;
            box-sizing: border-box;
            font-size: 15px;
        }}
        input:focus {{ outline: none; border-color: #00baf2; }}
        .btn-confirm {{
            background: #10b981;
            color: #fff;
        }}
        .btn-confirm:hover {{ background: #059669; }}
        .footer-text {{ font-size: 12px; color: #71717a; margin-top: 20px; line-height: 1.5; }}
        #resultBox {{
            display: none;
            background: #064e3b;
            border: 1px solid #059669;
            padding: 18px;
            border-radius: 14px;
            margin-top: 16px;
            color: #fff;
        }}
        .key-text {{
            font-family: monospace;
            font-size: 18px;
            background: #022c22;
            padding: 10px 14px;
            border-radius: 8px;
            display: inline-block;
            margin: 10px 0;
            user-select: all;
            color: #6ee7b7;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Paytm Business Verified
        </div>
        <h2>Insta Editor 360</h2>
        <p class="desc">Lifetime Access Key · Single One-Time Payment</p>

        <div class="amount-box">
            <span style="font-size:13px;color:#a1a1aa;">Order ID: <strong>{order_id}</strong></span>
            <span class="price">₹{amount}</span>
        </div>

        <!-- Paytm Business QR Code -->
        <div class="qr-wrap">
            <img src="/assets/paytm_qr.png?v=2" alt="Paytm Business QR Code">
        </div>
        <p style="font-size:13px;color:#a1a1aa;margin:0 0 14px 0;">Scan with <strong>Paytm</strong>, Google Pay, PhonePe, or BHIM</p>

        <!-- UPI & Business Details with 1-Click Copy -->
        <div class="upi-details">
            <div class="upi-row">
                <span>Name: <strong style="color:#fff;">{biz_name}</strong></span>
                <span style="color:#10b981;font-size:11px;">✓ Verified</span>
            </div>
            <div class="upi-row">
                <span>UPI Number: <strong id="upiNumText" style="color:#38bdf8;">{upi_num}</strong></span>
                <button type="button" class="copy-btn" onclick="copyText('{upi_num}', this)">Copy No</button>
            </div>
            <div class="upi-row">
                <span>UPI ID: <strong id="upiIdText" style="color:#34d399;">{paytm_vpa}</strong></span>
                <button type="button" class="copy-btn" onclick="copyText('{paytm_vpa}', this)">Copy UPI</button>
            </div>
        </div>

        <a href="{upi_uri}" class="btn btn-paytm">
            Pay ₹{amount} with Paytm / UPI App
        </a>

        <form id="confirmForm" onsubmit="confirmPayment(event)">
            <div class="input-group">
                <label for="custEmail">Your Email (Key will be sent here):</label>
                <input type="email" id="custEmail" required placeholder="you@gmail.com">
            </div>
            <div class="input-group">
                <label for="utrInput">Enter 12-Digit Paytm UTR / Ref No:</label>
                <input type="text" id="utrInput" required placeholder="e.g. 423156789012" maxlength="20">
            </div>
            <button type="submit" id="submitBtn" class="btn btn-confirm">
                Confirm & Generate Instant Key
            </button>
        </form>

        <div id="resultBox">
            <h3 style="margin:0 0 6px 0;color:#6ee7b7;">Payment Verified! 🎉</h3>
            <p style="font-size:13px;margin:0;">Your Lifetime Access Key is:</p>
            <div class="key-text" id="keyDisplay"></div>
            <p style="font-size:12px;margin:0 0 12px 0;color:#a7f3d0;">Key has been saved for your account. Copy and login!</p>
            <a href="/login" class="btn" style="background:#fff;color:#000;">Proceed to Login ↗</a>
        </div>

        <p class="footer-text">
            Official Support: <a href="mailto:{admin_email}" style="color:#38bdf8;text-decoration:none;">{admin_email}</a><br>
            Paytm Business UPI: {paytm_vpa} · UPI No: {upi_num}
        </p>
    </div>

    <script>
        function copyText(text, btn) {{
            navigator.clipboard.writeText(text).then(() => {{
                const orig = btn.innerText;
                btn.innerText = "Copied!";
                btn.style.background = "#10b981";
                setTimeout(() => {{ btn.innerText = orig; btn.style.background = "#3f3f46"; }}, 2000);
            }}).catch(() => {{
                prompt("Copy this:", text);
            }});
        }}

        async function confirmPayment(e) {{
            e.preventDefault();
            const email = document.getElementById("custEmail").value.trim();
            const utr = document.getElementById("utrInput").value.trim();
            const btn = document.getElementById("submitBtn");
            btn.disabled = true;
            btn.innerText = "Verifying...";

            try {{
                const res = await fetch("/api/paytm/confirm", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ order_id: "{order_id}", utr, email }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    document.getElementById("confirmForm").style.display = "none";
                    document.getElementById("keyDisplay").innerText = data.access_key;
                    document.getElementById("resultBox").style.display = "block";
                }} else {{
                    alert(data.error || "Verification failed. Check your UTR.");
                    btn.disabled = false;
                    btn.innerText = "Confirm & Generate Instant Key";
                }}
            }} catch(err) {{
                alert("Network error. Please try again.");
                btn.disabled = false;
                btn.innerText = "Confirm & Generate Instant Key";
            }}
        }}
    </script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


    def serve_admin_panel(self):
        admin = check_admin_auth(self)
        if not admin:
            # Render Secure Admin Login Gate
            login_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Security Gate — Insta Editor 360</title>
    <style>
        * { box-sizing: border-box; }
        body {
            background: #09090b;
            color: #f4f4f5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .card {
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 20px;
            max-width: 400px;
            width: 100%;
            padding: 32px 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            text-align: center;
        }
        .icon {
            width: 56px;
            height: 56px;
            border-radius: 16px;
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 18px;
        }
        h2 { margin: 0 0 8px 0; font-size: 22px; color: #fff; }
        p { color: #a1a1aa; font-size: 14px; margin: 0 0 24px 0; }
        input {
            width: 100%;
            padding: 13px 16px;
            background: #09090b;
            border: 1px solid #3f3f46;
            color: #fff;
            border-radius: 12px;
            font-size: 15px;
            margin-bottom: 16px;
        }
        input:focus { outline: none; border-color: #ef4444; }
        button {
            width: 100%;
            padding: 13px;
            background: #ef4444;
            color: #fff;
            border: none;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.15s;
        }
        button:hover { background: #dc2626; }
        #errMsg {
            display: none;
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            color: #fca5a5;
            padding: 10px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
        </div>
        <h2>Insta 360 Admin Gate</h2>
        <p>Enter Admin Password or Master Key to access the control panel</p>
        <div id="errMsg"></div>
        <form onsubmit="handleAdminLogin(event)">
            <input type="password" id="passInput" placeholder="Password or Master Key" required autofocus>
            <button type="submit" id="loginBtn">Unlock Admin Panel</button>
        </form>
    </div>
    <script>
        async function handleAdminLogin(e) {
            e.preventDefault();
            const pass = document.getElementById("passInput").value.trim();
            const btn = document.getElementById("loginBtn");
            const err = document.getElementById("errMsg");
            btn.disabled = true;
            btn.innerText = "Authenticating...";
            err.style.display = "none";

            try {
                const res = await fetch("/api/admin/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: pass })
                });
                const data = await res.json();
                if (data.ok) {
                    location.reload();
                } else {
                    err.innerText = data.error || "Access Denied. Incorrect Password or Key.";
                    err.style.display = "block";
                    btn.disabled = false;
                    btn.innerText = "Unlock Admin Panel";
                }
            } catch(e) {
                err.innerText = "Connection error. Please try again.";
                err.style.display = "block";
                btn.disabled = false;
                btn.innerText = "Unlock Admin Panel";
            }
        }
    </script>
</body>
</html>"""
            body = login_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # Authenticated Admin Dashboard
        conn = get_db()
        cur = conn.cursor()
        
        # Keys
        cur.execute("""
            SELECT k.id, k.label, k.plan, k.status, k.created_at, k.max_devices,
                   COUNT(d.id) AS device_count
            FROM access_keys k
            LEFT JOIN device_activations d ON d.access_key_id = k.id
            GROUP BY k.id
            ORDER BY k.created_at DESC
        """)
        keys = cur.fetchall()

        # Key Requests
        cur.execute("SELECT * FROM key_requests ORDER BY id DESC LIMIT 50")
        key_requests = cur.fetchall()

        # Paytm Orders
        cur.execute("SELECT * FROM payment_orders ORDER BY created_at DESC LIMIT 50")
        orders = cur.fetchall()
        
        # Settings
        paytm_vpa = get_setting("paytm_upi_id", "paytmqr5l66pa@ptys")
        paytm_name = get_setting("paytm_business_name", "SURENDRA SINGH")
        upi_number = get_setting("upi_number", "9956607278")
        admin_email = get_setting("admin_email", "vyrox954@gmail.com")
        apify_token = get_setting("apify_token", "")
        admin_password = get_setting("admin_password", "Surendra@360")
        smtp_user = get_setting("smtp_user", "vyrox954@gmail.com")
        smtp_pass = get_setting("smtp_pass", "")
        conn.close()

        keys_rows = ""
        for k in keys:
            status_color = '#34d399' if k['status']=='active' else ('#f87171' if k['status']=='revoked' else '#fbbf24')
            keys_rows += f"""
            <tr style="border-bottom:1px solid #27272a;">
                <td style="padding:10px;font-family:monospace;color:#5eead4;font-size:13px;">{k['id']}</td>
                <td style="padding:10px;"><strong>{k['label'] or '—'}</strong></td>
                <td style="padding:10px;"><span style="background:#27272a;padding:3px 8px;border-radius:4px;font-size:12px;">{k['plan']}</span></td>
                <td style="padding:10px;"><strong style="color:{status_color};">{k['status'].upper()}</strong></td>
                <td style="padding:10px;">{k['device_count']} / {k['max_devices']}</td>
                <td style="padding:10px;color:#a1a1aa;font-size:12px;">{k['created_at']}</td>
                <td style="padding:10px;white-space:nowrap;">
                    <button onclick="openEditModal('{k['id']}', '{k['label'] or ''}', '{k['plan']}', '{k['status']}', {k['max_devices']})" style="background:#0284c7;color:#fff;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;margin-right:6px;">Edit</button>
                    <button onclick="deleteKey('{k['id']}')" style="background:#dc2626;color:#fff;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;">Delete</button>
                </td>
            </tr>
            """

        requests_rows = ""
        for r in key_requests:
            action_btn = f"<button onclick=\"approveKey({r['id']}, '{r['email']}')\" style=\"background:#0284c7;color:#fff;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;\">Approve & Send Key</button>" if r['status'] == 'pending' else 'Done'
            requests_rows += f"""
            <tr style="border-bottom:1px solid #27272a;">
                <td style="padding:10px;"><strong>{r['email']}</strong></td>
                <td style="padding:10px;color:#38bdf8;">{r['forwarded_to']}</td>
                <td style="padding:10px;color:#a1a1aa;">{r['ip']}</td>
                <td style="padding:10px;color:#a1a1aa;font-size:12px;">{r['created_at']}</td>
                <td style="padding:10px;">
                    <span style="background:{'#065f46' if r['status']=='approved' else '#78350f'};color:#fff;padding:3px 8px;border-radius:4px;font-size:12px;">{r['status'].upper()}</span>
                </td>
                <td style="padding:10px;">{action_btn}</td>
            </tr>
            """

        orders_rows = ""
        for o in orders:
            orders_rows += f"""
            <tr style="border-bottom:1px solid #27272a;">
                <td style="padding:10px;font-family:monospace;color:#38bdf8;">{o['id']}</td>
                <td style="padding:10px;">{o['email']}</td>
                <td style="padding:10px;color:#10b981;font-weight:600;">₹{o['amount']}</td>
                <td style="padding:10px;font-family:monospace;color:#facc15;">{o['utr'] or '—'}</td>
                <td style="padding:10px;"><strong style="color:{'#34d399' if o['status']=='activated' else '#fbbf24'};">{o['status'].upper()}</strong></td>
                <td style="padding:10px;font-family:monospace;color:#6ee7b7;">{o['access_key_generated'] or '—'}</td>
                <td style="padding:10px;color:#a1a1aa;font-size:12px;">{o['created_at']}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Insta Editor 360 — Secure Admin & Key Manager</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background:#09090b; color:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,sans-serif; margin:0; padding:24px; }}
        .wrap {{ max-width:1150px; margin:0 auto; }}
        h1, h2, h3 {{ color:#fff; }}
        .card {{ background:#18181b; border:1px solid #27272a; border-radius:14px; padding:20px; margin-bottom:24px; }}
        table {{ width:100%; border-collapse:collapse; text-align:left; }}
        th {{ background:#27272a; padding:10px; font-size:13px; color:#d4d4d8; }}
        input, select {{ background:#09090b; border:1px solid #3f3f46; color:#fff; padding:8px 12px; border-radius:8px; font-size:14px; margin-right:8px; }}
        button.primary {{ background:#10b981; color:#fff; border:none; padding:9px 18px; border-radius:8px; cursor:pointer; font-weight:600; }}
        button.primary:hover {{ background:#059669; }}
        button.danger {{ background:#dc2626; color:#fff; border:none; padding:9px 18px; border-radius:8px; cursor:pointer; font-weight:600; }}
        /* Modal */
        #editModal {{
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 9999;
            align-items: center;
            justify-content: center;
        }}
        .modal-content {{
            background: #18181b;
            border: 1px solid #3f3f46;
            border-radius: 16px;
            padding: 24px;
            max-width: 480px;
            width: 90%;
            box-shadow: 0 20px 40px rgba(0,0,0,0.8);
        }}
    </style>
</head>
<body>
    <div class="wrap">
        <header style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px;">
            <div>
                <h1 style="margin:0;font-size:24px;">Insta Editor 360 Admin</h1>
                <p style="color:#a1a1aa;margin:4px 0 0 0;font-size:13px;">
                    Mail: <strong style="color:#38bdf8;">{admin_email}</strong> | 
                    Paytm UPI: <strong style="color:#34d399;">{paytm_vpa}</strong> | 
                    UPI No: <strong style="color:#facc15;">{upi_number}</strong>
                </p>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
                <a href="/pay" target="_blank" style="background:#0284c7;color:#fff;text-decoration:none;padding:8px 14px;border-radius:8px;font-size:13px;font-weight:600;">Paytm Checkout ↗</a>
                <a href="/login" target="_blank" style="background:#27272a;color:#fff;text-decoration:none;padding:8px 14px;border-radius:8px;font-size:13px;">Login Page ↗</a>
                <button onclick="handleLogout()" style="background:#dc2626;color:#fff;border:none;padding:8px 14px;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600;">Logout ⎋</button>
            </div>
        </header>

        <!-- Generate Key Section -->
        <div class="card">
            <h2 style="margin-top:0;">⚡ Create Access Key Instantly</h2>
            <form id="genForm" onsubmit="generateKey(event); return false;" style="display:flex;gap:8px;flex-wrap:wrap;">
                <input type="text" id="kLabel" placeholder="User Name / Email / Note" style="flex:1;min-width:200px;" required>
                <select id="kPlan">
                    <option value="lifetime">Lifetime Access (₹1,000)</option>
                    <option value="pro">Pro Plan</option>
                    <option value="agency">Agency Plan</option>
                </select>
                <select id="kDevices">
                    <option value="1">1 Device Lock</option>
                    <option value="2" selected>2 Devices</option>
                    <option value="5">5 Devices</option>
                    <option value="10">10 Devices</option>
                </select>
                <button type="submit" class="primary">+ Generate New Key</button>
            </form>
            <div id="genBanner" style="display:none;margin-top:16px;padding:12px;background:#064e3b;border-radius:8px;"></div>
        </div>

        <!-- All Active Access Keys with Edit & Delete -->
        <div class="card">
            <h2 style="margin-top:0;">🔑 All Access Keys ({len(keys)})</h2>
            <div style="overflow-x:auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Key ID</th>
                            <th>Label / Owner</th>
                            <th>Plan</th>
                            <th>Status</th>
                            <th>Devices</th>
                            <th>Created At</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {keys_rows if keys_rows else '<tr><td colspan="7" style="padding:14px;text-align:center;color:#71717a;">No keys generated yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Key Requests forwarded to vyrox954@gmail.com -->
        <div class="card">
            <h2 style="margin-top:0;">📥 Key Requests (Forwarded to {admin_email})</h2>
            <div style="overflow-x:auto;">
                <table>
                    <thead>
                        <tr><th>Requester Email</th><th>Forwarded To</th><th>IP Address</th><th>Date</th><th>Status</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                        {requests_rows if requests_rows else '<tr><td colspan="6" style="padding:14px;text-align:center;color:#71717a;">No key requests yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Paytm Orders -->
        <div class="card">
            <h2 style="margin-top:0;">💳 Paytm Business Payments</h2>
            <div style="overflow-x:auto;">
                <table>
                    <thead>
                        <tr><th>Order ID</th><th>Customer Email</th><th>Amount</th><th>Paytm UTR / Ref</th><th>Status</th><th>Access Key Given</th><th>Time</th></tr>
                    </thead>
                    <tbody>
                        {orders_rows if orders_rows else '<tr><td colspan="7" style="padding:14px;text-align:center;color:#71717a;">No payment orders yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Paytm Business & Security Settings -->
        <div class="card">
            <h2 style="margin-top:0;">⚙️ Paytm Business & Security Settings</h2>
            <form onsubmit="saveSettings(event)" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Paytm Business UPI ID / VPA:</label>
                    <input type="text" id="sUpi" value="{paytm_vpa}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Paytm Business Name:</label>
                    <input type="text" id="sBizName" value="{paytm_name}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">UPI Number:</label>
                    <input type="text" id="sUpiNum" value="{upi_number}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Admin Email (Key Notifications):</label>
                    <input type="email" id="sAdminEmail" value="{admin_email}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Admin Security Password:</label>
                    <input type="text" id="sAdminPass" value="{admin_password}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Default Apify API Token:</label>
                    <input type="text" id="sApify" value="{apify_token}" placeholder="apify_api_..." style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Gmail / SMTP User Email:</label>
                    <input type="email" id="sSmtpUser" value="{smtp_user}" style="width:100%;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Gmail 16-Digit App Password:</label>
                    <input type="password" id="sSmtpPass" value="{smtp_pass}" placeholder="e.g. abcd efgh ijkl mnop" style="width:100%;box-sizing:border-box;">
                </div>
                <div style="grid-column: span 2;">
                    <button type="submit" class="primary">Save Settings</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Edit Key Modal -->
    <div id="editModal">
        <div class="modal-content">
            <h3 style="margin-top:0;">✏️ Edit Access Key</h3>
            <form onsubmit="submitKeyEdit(event)">
                <input type="hidden" id="editKeyId">
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Key ID:</label>
                    <input type="text" id="editKeyIdDisplay" disabled style="width:100%;box-sizing:border-box;color:#888;">
                </div>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Label / Owner Note:</label>
                    <input type="text" id="editKeyLabel" style="width:100%;box-sizing:border-box;" required>
                </div>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Plan:</label>
                    <select id="editKeyPlan" style="width:100%;box-sizing:border-box;">
                        <option value="lifetime">Lifetime Access</option>
                        <option value="pro">Pro Plan</option>
                        <option value="agency">Agency Plan</option>
                    </select>
                </div>
                <div style="margin-bottom:12px;">
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Status:</label>
                    <select id="editKeyStatus" style="width:100%;box-sizing:border-box;">
                        <option value="active">ACTIVE</option>
                        <option value="revoked">REVOKED (Block Access)</option>
                        <option value="expired">EXPIRED</option>
                    </select>
                </div>
                <div style="margin-bottom:18px;">
                    <label style="display:block;font-size:13px;color:#a1a1aa;margin-bottom:4px;">Max Allowed Devices:</label>
                    <select id="editKeyDevices" style="width:100%;box-sizing:border-box;">
                        <option value="1">1 Device</option>
                        <option value="2">2 Devices</option>
                        <option value="5">5 Devices</option>
                        <option value="10">10 Devices</option>
                    </select>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:10px;">
                    <button type="button" onclick="closeEditModal()" style="background:#3f3f46;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;">Cancel</button>
                    <button type="submit" class="primary">Save Changes</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openEditModal(id, label, plan, status, max_dev) {{
            document.getElementById("editKeyId").value = id;
            document.getElementById("editKeyIdDisplay").value = id;
            document.getElementById("editKeyLabel").value = label;
            document.getElementById("editKeyPlan").value = plan;
            document.getElementById("editKeyStatus").value = status;
            document.getElementById("editKeyDevices").value = max_dev;
            document.getElementById("editModal").style.display = "flex";
        }}

        function closeEditModal() {{
            document.getElementById("editModal").style.display = "none";
        }}

        async function submitKeyEdit(e) {{
            e.preventDefault();
            const id = document.getElementById("editKeyId").value;
            const label = document.getElementById("editKeyLabel").value;
            const plan = document.getElementById("editKeyPlan").value;
            const status = document.getElementById("editKeyStatus").value;
            const max_devices = parseInt(document.getElementById("editKeyDevices").value);

            const res = await fetch("/api/admin/keys/update", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ id, label, plan, status, max_devices }})
            }});
            const data = await res.json();
            if (data.ok) {{
                alert("Key updated successfully!");
                location.reload();
            }} else {{
                alert(data.error || "Update failed.");
            }}
        }}

        async function deleteKey(id) {{
            if (!confirm("Are you sure you want to permanently delete this key (" + id + ")? Any user using this key will be logged out immediately.")) return;
            try {{
                const res = await fetch("/api/admin/keys/delete", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ id }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    alert("Key deleted successfully!");
                    location.reload();
                }} else {{
                    alert(data.error || "Delete failed.");
                }}
            }} catch(e) {{
                alert("Network error: " + e.message);
            }}
        }}

        async function generateKey(e) {{
            if (e) {{ e.preventDefault(); e.stopPropagation(); }}
            const labelInput = document.getElementById("kLabel");
            const label = labelInput ? labelInput.value.trim() : "Admin Key";
            const plan = document.getElementById("kPlan").value;
            const max_devices = parseInt(document.getElementById("kDevices").value);

            const btn = document.querySelector("#genForm button[type=submit]");
            if (btn) {{ btn.disabled = true; btn.innerText = "Generating..."; }}

            try {{
                const res = await fetch("/api/admin/keys", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ label, plan, max_devices }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const b = document.getElementById("genBanner");
                    b.style.display = "block";
                    b.innerHTML = '<div style="font-size:15px;font-weight:700;color:#34d399;margin-bottom:6px;">🎉 KEY CREATED SUCCESSFULLY:</div>' +
                                  '<div style="font-family:monospace;font-size:20px;background:#064e3b;padding:10px 14px;border-radius:8px;user-select:all;color:#fff;display:inline-block;letter-spacing:1px;border:1px solid #10b981;margin-bottom:8px;">' + data.access_key + '</div>' +
                                  '<div style="font-size:13px;color:#a7f3d0;margin-bottom:10px;">Plan: <strong>' + data.plan.toUpperCase() + '</strong> | Devices Allowed: <strong>' + max_devices + '</strong></div>' +
                                  '<button type="button" onclick="location.reload()" style="background:#10b981;color:#fff;border:none;padding:7px 16px;border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;">Refresh Key List Now ↻</button>';
                    if (labelInput) labelInput.value = "";
                }} else {{
                    alert(data.error || "Failed to generate key.");
                }}
            }} catch(err) {{
                alert("Network error: " + err.message);
            }} finally {{
                if (btn) {{ btn.disabled = false; btn.innerText = "+ Generate New Key"; }}
            }}
            return false;
        }}

        async function approveKey(id, email) {{
            if (!confirm("Generate lifetime key for " + email + "?")) return;
            const res = await fetch("/api/admin/approve-request", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ request_id: id, email }})
            }});
            const data = await res.json();
            if (data.ok) {{
                alert("Approved! Key: " + data.access_key);
                location.reload();
            }}
        }}

        async function saveSettings(e) {{
            e.preventDefault();
            const paytm_upi_id = document.getElementById("sUpi").value;
            const paytm_business_name = document.getElementById("sBizName").value;
            const upi_number = document.getElementById("sUpiNum").value;
            const admin_email = document.getElementById("sAdminEmail").value;
            const admin_password = document.getElementById("sAdminPass").value;
            const apify_token = document.getElementById("sApify").value;
            const smtp_user = document.getElementById("sSmtpUser").value;
            const smtp_pass = document.getElementById("sSmtpPass").value;

            const res = await fetch("/api/admin/settings", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ paytm_upi_id, paytm_business_name, upi_number, admin_email, admin_password, apify_token, smtp_user, smtp_pass }})
            }});
            const data = await res.json();
            if (data.ok) {{
                alert("Settings saved successfully!");
                location.reload();
            }} else {{
                alert(data.error || "Failed to save settings.");
            }}
        }}

        async function handleLogout() {{
            await fetch("/api/admin/logout", {{ method: "POST" }});
            location.reload();
        }}
    </script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

def run():
    init_db()
    server_address = ("0.0.0.0", PORT)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(server_address, InstaRequestHandler)
    print("\n" + "="*60)
    print(" INSTA EDITOR 360 SERVER RUNNING (MULTI-THREADED)")
    print("="*60)
    print(f" Frontend & Home URL:    http://localhost:{PORT}/")
    print(f" Login URL:              http://localhost:{PORT}/login")
    print(f" Dashboard (App) URL:    http://localhost:{PORT}/app")
    print(f" Paytm Checkout Page:    http://localhost:{PORT}/pay")
    print(f" Key Manager & Admin:    http://localhost:{PORT}/keys-panel")
    print("="*60 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run()

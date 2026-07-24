"""
GetDigitals Flow — Complete App
--------------------------------
Login/Signup + Google Drive publish + AI Studio (image gen) + Instagram Login (OAuth).
"""

import os
import re
import time
import requests
from urllib.parse import quote
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-env-file-please")

# ---- Database config ----
database_url = os.getenv("DATABASE_URL", "sqlite:///local_dev.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Pehle login karo yeh page dekhne ke liye."

GRAPH_API_VERSION = "v25.0"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Naya Instagram Login (Business Login) — Facebook Page ki zarurat nahi
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "")

activity_log = []


def log(message):
    activity_log.insert(0, message)
    activity_log[:] = activity_log[:20]
    print(message)


# ================= MODELS =================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ig_user_id = db.Column(db.String(120))
    ig_access_token = db.Column(db.Text)
    google_api_key = db.Column(db.String(255))
    ig_auth_type = db.Column(db.String(20), default="manual")  # "manual" ya "instagram_login"

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


def extract_folder_id(text):
    text = text.strip()
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', text)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', text)
    if match:
        return match.group(1)
    return text


# ================= AUTH ROUTES =================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Naam, email aur password zaroori hai.")
            return redirect(url_for("signup"))

        if User.query.filter_by(email=email).first():
            flash("Yeh email pehle se registered hai. Login karo.")
            return redirect(url_for("login"))

        new_user = User(name=name, email=email, phone=phone)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        log(f"✅ Naya user sign up hua: {email}")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            log(f"🔐 Login: {email}")
            return redirect(url_for("index"))

        flash("Email ya password galat hai.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ================= INSTAGRAM OAUTH (Instagram Login) =================

@app.route("/connect-instagram")
@login_required
def connect_instagram():
    if not INSTAGRAM_APP_ID or not INSTAGRAM_REDIRECT_URI:
        flash("Instagram Login abhi configure nahi hai — Render Environment mein INSTAGRAM_APP_ID set karo.")
        return redirect(url_for("settings"))

    scope = "instagram_business_basic,instagram_business_content_publish"
    auth_url = (
        "https://www.instagram.com/oauth/authorize"
        f"?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        f"&scope={scope}"
        "&response_type=code"
    )
    return redirect(auth_url)


@app.route("/instagram-callback")
@login_required
def instagram_callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        flash("Instagram connect nahi ho paya. Dobara try karo.")
        return redirect(url_for("settings"))

    try:
        token_resp = requests.post(
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": INSTAGRAM_APP_ID,
                "client_secret": INSTAGRAM_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": INSTAGRAM_REDIRECT_URI,
                "code": code,
            },
            timeout=20,
        ).json()

        if "error_message" in token_resp or "access_token" not in token_resp:
            log(f"❌ Instagram OAuth token exchange fail: {token_resp}")
            flash("Instagram se token nahi mila. Dobara try karo.")
            return redirect(url_for("settings"))

        short_lived_token = token_resp["access_token"]
        ig_user_id = str(token_resp.get("user_id", ""))

        long_lived_resp = requests.get(
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": INSTAGRAM_APP_SECRET,
                "access_token": short_lived_token,
            },
            timeout=20,
        ).json()

        final_token = long_lived_resp.get("access_token", short_lived_token)

        current_user.ig_user_id = ig_user_id
        current_user.ig_access_token = final_token
        current_user.ig_auth_type = "instagram_login"
        db.session.commit()

        log(f"✅ Instagram connect hua (Instagram Login): user_id {ig_user_id}")
        flash("Instagram connect ho gaya! 🎉")
        return redirect(url_for("settings"))

    except Exception as e:
        log(f"❌ Instagram callback exception: {e}")
        flash("Kuch galat ho gaya. Dobara try karo.")
        return redirect(url_for("settings"))


# ================= MAIN APP ROUTES =================

@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        ig_user_id=current_user.ig_user_id or "",
        configured=bool(current_user.ig_user_id and current_user.ig_access_token),
        log=activity_log,
        user=current_user,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.ig_user_id = request.form.get("ig_user_id", "").strip()
        current_user.ig_access_token = request.form.get("ig_access_token", "").strip()
        current_user.ig_auth_type = "manual"
        db.session.commit()
        flash("Settings save ho gayi.")
        return redirect(url_for("settings"))

    return render_template("settings.html", user=current_user)


@app.route("/studio")
@login_required
def studio():
    return render_template("studio.html", user=current_user)


@app.route("/api/generate-image", methods=["POST"])
@login_required
def generate_image():
    prompt = request.json.get("prompt", "").strip()
    width = request.json.get("width", 1024)
    height = request.json.get("height", 1024)

    if not prompt:
        return jsonify({"error": "Prompt zaroori hai"}), 400

    try:
        encoded_prompt = quote(prompt)
        seed = int(time.time())
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&seed={seed}&model=flux&nologo=true"
        )

        check = requests.get(image_url, timeout=60)
        if check.status_code != 200:
            log(f"❌ Image generation failed: status {check.status_code}")
            return jsonify({"error": "Image generate nahi ho payi, dobara try karo"}), 500

        log(f"🎨 AI Image bani: \"{prompt[:50]}...\"")
        return jsonify({"success": True, "image_url": image_url})

    except requests.exceptions.Timeout:
        log("❌ Image generation timeout")
        return jsonify({"error": "Timeout — Pollinations slow chal raha hai, dobara try karo"}), 504
    except Exception as e:
        log(f"❌ Image generation exception: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/drive-files", methods=["POST"])
@login_required
def get_drive_files():
    raw_input = request.json.get("folder_id", "").strip()
    if not raw_input:
        return jsonify({"error": "Folder ID ya link zaroori hai"}), 400
    folder_id = extract_folder_id(raw_input)

    if not GOOGLE_API_KEY:
        return jsonify({"error": "Server ki Google API Key set nahi hai — Render Environment mein GOOGLE_API_KEY add karo"}), 400

    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and (mimeType contains 'image/' or mimeType contains 'video/') and trashed=false",
        "fields": "files(id,name,mimeType,thumbnailLink,webContentLink)",
        "key": GOOGLE_API_KEY,
        "pageSize": 25,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if "error" in data:
            log(f"❌ Drive fetch failed: {data['error'].get('message')}")
            return jsonify({"error": data["error"].get("message", "Drive error")}), 400

        files = data.get("files", [])
        log(f"✅ Drive se {len(files)} files mile (folder: {folder_id})")
        return jsonify({"files": files})
    except Exception as e:
        log(f"❌ Drive fetch exception: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/publish", methods=["POST"])
@login_required
def publish_to_instagram():
    file_id = request.json.get("file_id", "").strip()
    direct_image_url = request.json.get("image_url", "").strip()
    caption = request.json.get("caption", "").strip()

    ig_user_id = current_user.ig_user_id
    ig_access_token = current_user.ig_access_token
    ig_auth_type = current_user.ig_auth_type or "manual"

    if not ig_user_id or not ig_access_token:
        return jsonify({"error": "Pehle Settings mein Instagram connect karo"}), 400
    if not file_id and not direct_image_url:
        return jsonify({"error": "file_id ya image_url zaroori hai"}), 400

    if ig_auth_type == "instagram_login":
        base = f"https://graph.instagram.com/{ig_user_id}"
    else:
        base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}"

    if direct_image_url:
        is_video = False
        media_url = direct_image_url
    else:
        if not GOOGLE_API_KEY:
            return jsonify({"error": "Server ki Google API Key set nahi hai"}), 400
        try:
            meta_resp = requests.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "mimeType,name", "key": GOOGLE_API_KEY},
                timeout=15,
            ).json()
            if "error" in meta_resp:
                msg = meta_resp["error"].get("message", "File metadata fetch failed")
                log(f"❌ File metadata fail: {msg}")
                return jsonify({"error": msg}), 400
            mime_type = meta_resp.get("mimeType", "")
        except Exception as e:
            log(f"❌ File metadata exception: {e}")
            return jsonify({"error": str(e)}), 500

        is_video = mime_type.startswith("video/")
        media_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={GOOGLE_API_KEY}"

    try:
        container_data = {
            "caption": caption,
            "access_token": ig_access_token,
        }
        if is_video:
            container_data["media_type"] = "REELS"
            container_data["video_url"] = media_url
        else:
            container_data["image_url"] = media_url

        container_resp = requests.post(f"{base}/media", data=container_data, timeout=60).json()

        if "error" in container_resp:
            msg = container_resp["error"].get("message", "Container creation failed")
            log(f"❌ Container fail: {msg}")
            return jsonify({"error": msg}), 400

        creation_id = container_resp["id"]
        log(f"📦 Container bana: {creation_id}")

        if is_video:
            status = "IN_PROGRESS"
            attempts = 0
            status_host = (
                f"https://graph.instagram.com/{creation_id}"
                if ig_auth_type == "instagram_login"
                else f"https://graph.facebook.com/{GRAPH_API_VERSION}/{creation_id}"
            )
            while status not in ("FINISHED", "ERROR") and attempts < 30:
                time.sleep(3)
                status_resp = requests.get(
                    status_host,
                    params={"fields": "status_code", "access_token": ig_access_token},
                    timeout=15,
                ).json()
                status = status_resp.get("status_code", "IN_PROGRESS")
                attempts += 1
                log(f"⏳ Video processing: {status} (try {attempts}/30)")

            if status == "ERROR":
                log("❌ Video processing failed Meta ki taraf se")
                return jsonify({"error": "Video processing failed on Meta's side"}), 400
            if status != "FINISHED":
                log("❌ Timeout: video processing bahut time le raha hai")
                return jsonify({"error": "Video processing timeout — thodi der baad try karo"}), 400

        publish_resp = requests.post(
            f"{base}/media_publish",
            data={"creation_id": creation_id, "access_token": ig_access_token},
            timeout=30,
        ).json()

        if "error" in publish_resp:
            msg = publish_resp["error"].get("message", "Publish failed")
            log(f"❌ Publish fail: {msg}")
            return jsonify({"error": msg}), 400

        post_id = publish_resp["id"]
        log(f"🚀 LIVE ho gaya! Post ID: {post_id}")
        return jsonify({"success": True, "post_id": post_id})

    except Exception as e:
        log(f"❌ Exception: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/log")
@login_required
def get_log():
    return jsonify({"log": activity_log})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

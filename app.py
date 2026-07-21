"""
GetDigitals Flow — Basic Demo
------------------------------
Ek chhota Flask app jo dikhata hai:
  1. Google Drive ke public folder se images fetch karna
  2. Un images ko Instagram Business account par publish karna (Graph API)

Ye app Meta App Review ke liye screencast demo banane ke kaam aayega.
Production mein iske upar scheduling, error-handling, aur database add hoga.
"""

import os
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---- Config: .env file se aayega ----
IG_USER_ID = os.getenv("IG_USER_ID", "")          # e.g. 17841407648926658
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")  # Page/User access token jisme instagram_business_content_publish ho
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")    # Drive API key (public folder read ke liye)
GRAPH_API_VERSION = "v25.0"

# Simple in-memory log — production mein ye database mein jayega
activity_log = []


def log(message):
    activity_log.insert(0, message)
    activity_log[:] = activity_log[:20]  # last 20 entries hi rakho
    print(message)


@app.route("/")
def index():
    return render_template(
        "index.html",
        ig_user_id=IG_USER_ID,
        configured=bool(IG_USER_ID and IG_ACCESS_TOKEN),
        log=activity_log,
    )


@app.route("/api/drive-files", methods=["POST"])
def get_drive_files():
    """
    Public Google Drive folder se image files ki list laata hai.
    Folder "Anyone with the link -> Viewer" hona chahiye.
    """
    folder_id = request.json.get("folder_id", "").strip()
    if not folder_id:
        return jsonify({"error": "Folder ID zaroori hai"}), 400
    if not GOOGLE_API_KEY:
        return jsonify({"error": "GOOGLE_API_KEY .env file mein set nahi hai"}), 400

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
def publish_to_instagram():
    """
    Ek image ko Instagram Business account par publish karta hai.
    Do-step Graph API flow: media container banao -> phir publish karo.
    """
    file_id = request.json.get("file_id", "").strip()
    caption = request.json.get("caption", "").strip()

    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        return jsonify({"error": "IG_USER_ID / IG_ACCESS_TOKEN .env mein set nahi hai"}), 400
    if not file_id:
        return jsonify({"error": "file_id zaroori hai"}), 400

    # Google Drive file ka direct-view URL (publicly shared file hona chahiye)
    image_url = f"https://drive.google.com/uc?export=view&id={file_id}"

    base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}"

    try:
        # Step 1: Media container banao
        container_resp = requests.post(
            f"{base}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=30,
        ).json()

        if "error" in container_resp:
            msg = container_resp["error"].get("message", "Container creation failed")
            log(f"❌ Container fail: {msg}")
            return jsonify({"error": msg}), 400

        creation_id = container_resp["id"]
        log(f"📦 Container bana: {creation_id}")

        # Step 2: Publish karo
        publish_resp = requests.post(
            f"{base}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": IG_ACCESS_TOKEN,
            },
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
def get_log():
    return jsonify({"log": activity_log})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

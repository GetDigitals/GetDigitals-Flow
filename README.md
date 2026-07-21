# GetDigitals Flow — Basic Demo

Ye ek chhota working demo hai jo dikhata hai:
1. Google Drive ke ek public folder se images fetch karna
2. Un images ko ek click mein Instagram Business account (@getdigitals.in) par publish karna

**Iska purpose**: Meta App Review ke liye screencast banana — taaki `instagram_business_content_publish` permission approve ho jaaye.

---

## Setup (5 minute)

### 1. Files yahan copy karo apne computer pe
Is poore folder ko apne laptop mein kisi jagah rakh do (jaise `Desktop/getdigitals-autopost`).

### 2. Python install hona chahiye
Terminal/Command Prompt kholo aur check karo:
```
python --version
```
Agar nahi hai, [python.org](https://python.org) se install karo (3.9+ version).

### 3. Dependencies install karo
Folder ke andar terminal khol ke:
```
pip install -r requirements.txt
```

### 4. `.env` file banao
`.env.example` file ko copy karke naam badal do `.env` — aur usme apni real values daalo:

- **IG_USER_ID**: Ye tumhara Instagram Business Account ID hai (already pata hai: `17841407648926658`)
- **IG_ACCESS_TOKEN**: Graph API Explorer se jo token generate kiya tha (wahi copy kar sakte ho abhi ke liye — production mein long-lived token banayenge)
- **GOOGLE_API_KEY**: Google Cloud Console se ek naya API key banao:
  1. https://console.cloud.google.com/apis/credentials pe jao
  2. "Create Credentials" → "API Key"
  3. Us project mein **Google Drive API enable** karo (APIs & Services → Library → search "Google Drive API" → Enable)

### 5. App chalao
```
python app.py
```
Terminal mein dikhega: `Running on http://127.0.0.1:5000`

Browser mein wahi link kholo.

---

## Kaise Use Karein

1. Google Drive mein ek folder banao, kuch images daalo
2. Us folder ko **"Anyone with the link can view"** share setting pe rakho
3. Folder ka URL open karo — URL mein jo lamba ID hota hai (jaise `1a2B3cD4E...`), wahi **Folder ID** hai
4. App mein wo ID paste karo → "Fetch Files" dabao
5. Caption likho → kisi bhi image ke "Publish" button pe click karo
6. **Instagram pe live ho jaayega!**

---

## Screencast Banate Waqt Ye Dikhana

Meta App Review ke liye recording mein ye sequence dikhao:
1. App khola (browser mein)
2. Drive folder connect kiya (files fetch hui, dikhi)
3. Ek image select karke caption likha
4. "Publish" dabaya
5. **Turant Instagram app/website khol ke dikhao ki post live ho gaya**

Ye poora flow ek continuous recording mein hona chahiye (2-3 minute ka video kaafi hai).

---

## Render.com Par Live Karna (Hosting)

App ko internet pe live karne ke liye Render.com free tier use kar sakte ho.

### 1. GitHub Par Upload Karo
- github.com pe free account banao
- Naya repository banao (jaise `getdigitals-flow`)
- Is poore folder ki saari files upload karo — **`.env` file upload MAT karna** (usmein secrets hain; `.gitignore` isko already exclude karta hai)

### 2. Render.com Par Web Service Banao
- render.com pe GitHub account se login karo
- **New** → **Web Service** → apna GitHub repo select karo
- Settings:
  | Field | Value |
  |---|---|
  | **Environment** | Python 3 |
  | **Build Command** | `pip install -r requirements.txt` |
  | **Start Command** | `gunicorn app:app` |

### 3. Environment Variables Add Karo (Zaroori!)
"Environment" tab mein ye **exact naam** ke saath teen variables add karo (`.env` file jaisa hi, lekin yahan Render ke dashboard mein):

| Key | Value |
|---|---|
| `IG_USER_ID` | `17841407648926658` |
| `IG_ACCESS_TOKEN` | Apna Instagram access token |
| `GOOGLE_API_KEY` | Apna Google Drive API key |

⚠️ **In naamo ko exactly copy karo** (capital letters, underscores sahi se) — agar naam match nahi hua to app "not configured" dikhayega.

### 4. Deploy
**Create Web Service** dabao → 2-3 minute mein live link milega, jaise:
```
https://getdigitals-flow.onrender.com
```

Ye link hi Meta App Review ke screencast/submission mein use karna hai.

⚠️ **Free tier note**: Render ka free tier kuch der inactive rehne pe "sleep" ho jaata hai — pehli request pe 30-50 second lag sakte hain wake-up hone mein. Demo/review ke liye ye theek hai, production scale pe paid tier chahiye hoga.

---

## Important Notes

- Ye **demo/prototype** hai — production version mein scheduling, database, error retry, aur multi-account support add hoga
- Access token abhi **short-lived** hai (Graph Explorer wala) — App Review ke baad long-lived token generate karna hoga
- `.env` file kabhi bhi GitHub ya kahi public share mat karna — isme secret keys hain

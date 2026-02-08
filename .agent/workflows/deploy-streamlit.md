---
description: Deploy EduTrack to Streamlit Community Cloud
---

# Deploy to Streamlit Community Cloud

## Prerequisites
- GitHub account with repo pushed
- Supabase project with `readonly_user` created (see `scripts/03_db_readonly_role_setup.sql`)

---

## Step 1: Push Code to GitHub

Ensure your repo is on GitHub and `.env` is in `.gitignore` (never commit secrets).

```bash
git add .
git commit -m "Prepare for Streamlit deployment"
git push origin main
```

---

## Step 2: Go to Streamlit Community Cloud

1. Visit: https://share.streamlit.io/
2. Click **"New app"**
3. Sign in with GitHub (authorize Streamlit if prompted)

---

## Step 3: Configure the App

| Field | Value |
|---|---|
| **Repository** | `your-username/EduTrack_Curriculum_Generator` |
| **Branch** | `main` |
| **Main file path** | `app.py` |

Click **"Advanced settings"** before deploying.

---

## Step 4: Add Secrets (CRITICAL)

In **Advanced settings** → **Secrets**, add your environment variables in TOML format:

```toml
DATABASE_URL = "postgresql://readonly_user:YOUR_PASSWORD@db.xxxx.supabase.co:5432/postgres"
GOOGLE_API_KEY = "your-gemini-api-key"
```

> ⚠️ Replace placeholders with real values. These are encrypted and never exposed.

---

## Step 5: Deploy

Click **"Deploy!"**

Streamlit will:
1. Clone your repo
2. Install `requirements.txt`
3. Run `streamlit run app.py`

First deploy takes 2-5 minutes.

---

## Step 6: Verify

1. Open the deployed URL (e.g., `https://your-app.streamlit.app`)
2. Confirm the app loads without errors
3. Test a curriculum generation to verify DB connectivity

---

## Troubleshooting

| Issue | Solution |
|---|---|
| **ModuleNotFoundError** | Add missing package to `requirements.txt` |
| **DB connection failed** | Check `DATABASE_URL` in secrets |
| **App crashes on load** | Check logs in Streamlit dashboard |

---

## Post-Deploy Checklist

- [ ] App loads successfully
- [ ] DB connection works (test curriculum generation)
- [ ] No secrets visible in logs or UI
- [ ] Share URL only with internal testers (staging phase)

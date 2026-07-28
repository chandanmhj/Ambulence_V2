# Deploying: Railway (backend) + Vercel (frontend)

This splits the stack: OSRM + FastAPI backend + Postgres all run on Railway;
the React frontend deploys separately to Vercel (free static hosting). This
keeps cost down versus putting everything on Railway.

---

## 0. Required security configuration before deploying

The backend now refuses to start in production if these aren't set - this is
intentional, so a misconfigured deploy fails loudly instead of silently
running insecurely. Set these as Railway environment variables on the
backend service:

- `ENVIRONMENT=production` - this is what triggers the safety checks below
- `JWT_SECRET_KEY` - a long random string, e.g. generate one with `openssl rand -hex 32`
- `ALLOWED_ORIGINS` - your exact deployed frontend URL (e.g. `https://your-app.vercel.app`), comma-separated if you have more than one

**Email (optional but recommended):** without these, email verification and
password reset are effectively disabled (accounts auto-verify, and
forgot-password will return a 400 telling you email isn't configured). The
app still works fully without email set up - this is a deliberate fallback
so you're not blocked while setting up an email provider. To enable it, set:

- `SMTP_HOST`, `SMTP_PORT` (587 for most providers), `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`
- `FRONTEND_URL` - your deployed frontend URL, used to build the links inside verification/reset emails

Any SMTP provider works - Gmail (with an app password, not your real
password), SendGrid, Mailgun, Resend, etc. all have free tiers sufficient
for a project this size.

**A note on rate limiting:** login/signup/password-reset endpoints are
rate-limited in-memory per backend instance. This resets on every deploy and
won't coordinate across multiple instances - fine for a single Railway
instance, but if you ever scale horizontally, swap this for Redis-backed
rate limiting.

---

## 1. Prepare a smaller OSRM extract for deployment

Your local `.osm.pbf` (southern-zone) is too large to bake into a deployable
image efficiently. Crop it down to just the Bangalore metro area first using
`osmium` (install via `pip install osmium` or your package manager):

```bash
# Bangalore metro bounding box (roughly matches BANGALORE_BOUNDS in config.js)
osmium extract -b 77.35,12.75,77.85,13.20 osrm-data/bangalore.osm.pbf -o osrm-deploy/bangalore.osm.pbf
```

This gives you a much smaller file focused on exactly the area the app locks
its map to, which keeps the Railway build fast and the image size reasonable.

---

## 2. Push your project to GitHub

Railway deploys from a GitHub repo. Push this whole project (create a repo,
commit, push) if you haven't already - Railway will let you pick subdirectories
as separate service roots in the next steps.

---

## 3. Create the Railway project and three services

Go to [railway.app](https://railway.app), sign in, and create a **New Project**.

**Service 1: OSRM**
- "Deploy from GitHub repo" → select your repo
- In the service settings, set **Root Directory** to `osrm-deploy`
- Railway will detect the `Dockerfile` there and build it automatically
- Once deployed, go to **Settings → Networking** and note its **private
  network address** (looks like `osrm.railway.internal`) - you'll need this
  for the backend's `OSRM_URL`. You do NOT need to expose OSRM publicly;
  only the backend talks to it.

**Service 2: Postgres**
- In the same project, click **+ New → Database → Add PostgreSQL**
- Railway provisions it and auto-generates a `DATABASE_URL` - you'll reference
  this from the backend service in the next step (Railway lets you reference
  another service's variable directly, or just copy the value).

**Service 3: Backend**
- "+ New → GitHub Repo" → same repo again
- Set **Root Directory** to `backend`
- Railway detects the existing `Dockerfile` there
- Go to **Variables** and add:
  - `ENVIRONMENT` = `production` (enables the required security checks from step 0)
  - `OSRM_URL` = `http://osrm.railway.internal:5000` (use the actual private address from Service 1)
  - `DATABASE_URL` = reference the Postgres service's `DATABASE_URL` variable (Railway shows a "reference" picker for this)
  - `JWT_SECRET_KEY` = generate a long random string (e.g. `openssl rand -hex 32`)
  - `GOOGLE_CLIENT_ID` = (from step 5 below)
  - `ALLOWED_ORIGINS` = your Vercel URL once you have it (step 4) - e.g. `https://your-app.vercel.app`
  - `FRONTEND_URL` = same as above - used to build links inside verification/reset emails
  - Optionally `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` (see step 0 for why this is optional)
- Under **Settings → Networking**, click **Generate Domain** to get a public URL
  (looks like `your-backend.up.railway.app`) - this is what the frontend will call.

---

## 4. Deploy the frontend to Vercel

1. Go to [vercel.com](https://vercel.com), sign in, **Add New → Project**, import the same GitHub repo
2. Set **Root Directory** to `frontend`
3. Framework preset: Vite (Vercel auto-detects this)
4. Add environment variables (Vercel's project settings → Environment Variables):
   - `VITE_BACKEND_HTTP` = `https://your-backend.up.railway.app` (from step 3)
   - `VITE_BACKEND_WS` = `wss://your-backend.up.railway.app` (same host, `wss://` not `ws://` since Railway serves HTTPS)
   - `VITE_GOOGLE_CLIENT_ID` = (from step 5 below)
5. Deploy. Vercel gives you a URL like `your-app.vercel.app`.
6. Go back to Railway's backend service and set `ALLOWED_ORIGINS` to this exact Vercel URL, then redeploy the backend so CORS allows it.

---

## 5. Set up "Sign in with Google" (free, no GCP billing needed)

Google reorganized this UI in the last year into the "Google Auth Platform" -
if you've seen older tutorials with different screens, that's why.

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a new project (or pick an existing one) from the project selector top-left
2. Navigate to **Google Auth Platform → Branding** (or you'll be prompted with a "Get started" wizard on a fresh project)
3. Walk through the 4-step wizard:
   - App name, support email
   - **Audience: pick "External"** (this matters - it's what lets any Google user sign in, not just people inside an organization, and can't be changed later without starting a fresh project)
   - Add your own email under test users while in testing mode
4. Once branding is set up, go to **Google Auth Platform → Clients → Create Client**
5. **Application type: Web application**
6. Under **Authorized JavaScript origins**, add:
   - `http://localhost:5173` (for local dev)
   - `https://your-app.vercel.app` (your real deployed frontend URL)
7. Click Create - you'll get a **Client ID** (looks like `xxxxx.apps.googleusercontent.com`). You do NOT need the client secret for this flow (the frontend button only needs the Client ID).
8. Put that Client ID into:
   - Railway backend's `GOOGLE_CLIENT_ID` variable
   - Vercel frontend's `VITE_GOOGLE_CLIENT_ID` variable

No billing account is required for any of this - OAuth clients are free regardless of how many users sign in.

---

## 6. Verify

Once both are deployed:
1. Open your Vercel URL
2. Try signing up with email/password
3. Try the Google button
4. Confirm the map loads and a test route calculates (this confirms the frontend → Railway backend → Railway OSRM chain all works over the internet, not just locally)

If the Google button doesn't appear: check the browser console for a Client ID mismatch error - the origin you're testing from must exactly match one of the Authorized JavaScript origins you added in step 5.

If routes fail but login works: double check `OSRM_URL` on the backend service - Railway's private networking address must match exactly what you see in the OSRM service's Networking tab.

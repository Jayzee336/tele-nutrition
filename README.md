# NutriConnect

NutriConnect is a Django web application for tele-nutrition. This repository contains the application source code and configuration for local development and deployment.

## Project links

- **GitHub repository:** https://github.com/Jayzee336/tele-nutrition
- **Live deployment:** https://tele-nutrition.onrender.com
- **Hosting:** Render (Singapore region)
- **Database:** Neon PostgreSQL in production; SQLite can be used for local development when `DATABASE_URL` is not set.

> The Render service may be suspended or spun down when not in use. If the website does not respond, check the service status in the Render dashboard.

## Requirements

Install these on your computer:

- Python compatible with the versions in `requirements.txt`
- Git
- A terminal (Windows Command Prompt is used in the examples below)

## Run NutriConnect locally on Windows

### 1. Clone the repository

Open Command Prompt and run:

```bat
cd %USERPROFILE%\Desktop\Projects
git clone https://github.com/Jayzee336/tele-nutrition.git
cd tele-nutrition
```

If the repository is private, sign in to GitHub or configure Git authentication when prompted.

### 2. Create and activate a virtual environment

```bat
py -m venv .venv
.venv\Scripts\activate
```

If `py` is unavailable but `python` works, use `python -m venv .venv` instead.

### 3. Install dependencies

```bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create a local environment file

Create a file named `.env` in the project root (the same folder as `manage.py`). Add a new local secret key and enable debug mode for local development:

```dotenv
DJANGO_SECRET_KEY=replace-with-a-new-local-secret-key
DJANGO_DEBUG=True
```

Generate a key with:

```bat
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated key into your local `.env` file. Do not commit `.env` or share secret values. The `.env` file and local SQLite database are intended to remain untracked.

For local SQLite development, leave `DATABASE_URL` unset. If you intentionally configure a database URL, make sure it points to a development database rather than a production database.

### 5. Apply migrations

```bat
python manage.py migrate
```

### 6. Start the development server

```bat
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser. Stop the local server with **Ctrl+C** in the terminal.

## Run checks and tests

With the virtual environment activated:

```bat
python manage.py check
python manage.py test core.tests
```

To prepare static files locally (the Render build does this automatically):

```bat
python manage.py collectstatic --noinput
```

## Production deployment on Render

The current Render service uses:

- **Repository:** `Jayzee336/tele-nutrition`
- **Branch:** `main`
- **Region:** Singapore
- **Root directory:** blank (repository root)
- **Build command:** `bash build.sh`
- **Start command:** `gunicorn config.wsgi:application`

The `build.sh` script installs dependencies, collects static files, and applies database migrations.

### Required Render environment variables

Configure these under the service's **Environment** settings. Never put production secrets in this README or in Git.

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A strong, unique production secret key. Do not reuse or publish the local key. |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | The Render hostname only, without `https://`, e.g. `tele-nutrition.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The full HTTPS origin, e.g. `https://tele-nutrition.onrender.com` |
| `DATABASE_URL` | The private Neon PostgreSQL connection string. Never commit or share it. |

If the service hostname changes, update both `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to match it.

### Resume the suspended Render service

If the service was manually suspended:

1. Sign in at https://dashboard.render.com/.
2. Open the `tele-nutrition` web service.
3. Use the available **Resume** action (or the equivalent action shown in the dashboard).
4. Wait for the service to become **Live**, then open https://tele-nutrition.onrender.com/.

If the service is not suspended but is simply sleeping on Render's free plan, visiting the URL normally wakes it. The first request may take a little while.

### Database and file storage notes

- Production database records are stored in Neon PostgreSQL when `DATABASE_URL` is configured correctly.
- Render web service filesystems are ephemeral. Do not rely on files written to the deployed service's local disk being permanently stored.
- The local `db.sqlite3` file is for development and should not be committed.
- Back up important data and keep Neon credentials private.

## Updating the deployed application

After making and testing changes locally:

```bat
git status
git add .
git commit -m "Describe your changes"
git push origin main
```

Render can automatically deploy new commits pushed to the connected branch, depending on the service's auto-deploy setting. Check the Render dashboard to confirm the deployment status.

Before staging files, review `git status` and ensure that `.env`, database files, virtual environments, and other secrets or local-only files are not included.

## Troubleshooting

- **Bad Request (400):** Check that `DJANGO_ALLOWED_HOSTS` contains `tele-nutrition.onrender.com` without a scheme, and `DJANGO_CSRF_TRUSTED_ORIGINS` contains `https://tele-nutrition.onrender.com`. Save changes and redeploy/restart if required.
- **Database connection error:** Verify `DATABASE_URL` in Render and check that the Neon database is active and its credentials are current. Never post the connection string publicly.
- **Static files missing:** Check the Render build logs for the `collectstatic` step.
- **Deployment failed:** Open the Render service's deploy/build logs and review the first error message.
- **Local import or package errors:** Confirm the virtual environment is activated and reinstall dependencies with `python -m pip install -r requirements.txt`.

## Project architecture

- **Backend:** Django (Python) with a single `core` application
- **Database:** SQLite for local development; Neon PostgreSQL (`DATABASE_URL`) for production
- **Static files:** WhiteNoise (`CompressedManifestStaticFilesStorage`) served through `collectstatic`
- **Hosting / deployment:** Render (`gunicorn config.wsgi:application`); build script `build.sh` runs `migrate` and `collectstatic`
- **Application server:** Gunicorn
- **Video conferencing:** Jitsi Meet embedded via the public `meet.jit.si` iFrame API (`external_api.js`); each approved appointment has a unique UUID-based room (`NutriConnect-<uuid>`)
- **Privacy / security notes:** The embedded meeting uses the free public Jitsi service. It does not claim healthcare-grade confidentiality or regulatory compliance (e.g., HIPAA). Sensitive health details should be shared only as needed for the consultation. No recording is enabled through the application.

## Tele-nutrition workflow supported by NutriConnect

The application supports a complete connected workflow:

1. **Consumer:** Register → Log in → Log meals → Request consultation → View appointment status → Join approved virtual session → Receive consultation notes/recommendations.
2. **Dietitian:** Log in → Review pending requests → Approve/reject (with reason) → Review patient meal logs → Create/update consultation notes → Provide recommendations → Complete appointment → Join assigned video session.

Appointment scheduling includes conflict detection (60-minute duration), past-time prevention, and role-based access control enforced on the Django backend. Only the assigned consumer and assigned dietitian can access an appointment's video room, and only after approval.

## Security reminders

- The embedded Jitsi Meet video room is accessible only for approved appointments and only to the assigned consumer and dietitian (`video_room`).
- The video interface includes camera/microphone permission guidance, a return-to-dashboard link, and privacy disclaimers.
- Never commit `.env`, secret keys, database passwords, or production connection strings.
- Keep `DJANGO_DEBUG=False` in production.
- Use a separate secret key for local development and production.
- Do not use the production database for experiments or destructive local tests.

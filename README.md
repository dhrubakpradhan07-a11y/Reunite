# Reunite 🌿 — Lost & Found Smart Matcher

A clean, responsive **Lost & Found social feed** with separate Lost/Found posts, optional photo uploads, private inquiry messaging, and smart matching based on category, keywords, location, and color. Created as a beginner-friendly Python/Flask project with SQLite storage and a browser-openable preview.

## Open the website now (no installation)

Double-click **`index.html`**. It will open in Chrome, Edge, Firefox, Safari, or another modern browser. This is **browser preview mode**. You can browse example posts, create your own reports, filter/search, add photos, and test private message dashboards. Posts in this mode are stored only in *that browser's localStorage*, **not shared between devices**. The example posts are fictional and clearly labeled SAMPLE.

For a **real shared website**, run the Python server below. Both modes use the same frontend design.

## Start the real Python website on Windows

1. Install **Python 3.10+** from https://python.org (tick **Add Python to PATH**).
2. Extract this project ZIP into a folder.
3. Double-click **`start_windows.bat`** to install dependencies and launch the server, **OR** open Terminal in the project folder:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

4. Visit **http://127.0.0.1:5000** in your browser. Keep the terminal running.

On macOS/Linux, use `python3 -m pip install -r requirements.txt` and `python3 app.py`.

Your actual reports, contact information, photos, and messages are now saved in `data/reunite.sqlite3` and `data/uploads/`. Those files are excluded from GitHub by `.gitignore`.

## Files

```text
reunite_lost_found/
├── index.html                # Mobile-first homepage, feed, modals
├── manage.html               # Private report dashboard
├── app.py                    # Flask API, validation, uploads, matching, SQLite
├── requirements.txt          # Flask, Pillow, Gunicorn
├── static/
│   ├── favicon.svg
│   ├── css/styles.css        # Responsive styling, dark mode, UI components
│   └── js/
│       ├── api.js            # Flask API / browser-preview adapter
│       ├── app.js            # Feed, search, filters, modal forms
│       └── manage.js         # Private messages, status, deletion
├── data/                     # Your local database/photo files (not committed)
├── start_windows.bat         # Beginner-friendly Windows launcher
├── render.yaml               # Cloud-host starter config
├── .env.example              # Optional environment settings
├── .gitignore
├── WEBSITE_PROMPT.md         # Prompt to rebuild or extend the project
└── README.md
```

## Main features

- **Two report paths:** `Lost` and `Found`, each with an item name, category, color, place, date, description, reporter details, and optional image.
- **Social-style feed:** filtering by Lost / Found / Reunited, category, keyword search, sort, pagination, responsive cards.
- **Smart match suggestions:** deterministic suggestions use overlapping category, item details, location, and color; these are not proof of ownership or AI predictions.
- **Private contact:** public posts show only the reporter's first name. Email/phone stays in the database, away from the public feed. A person who has a lead can send a message stored in the poster's private dashboard.
- **Private owner link:** displayed immediately after posting; save it to read messages, mark items reunited, reopen, or delete. Saved links also appear in **My reports** in the same browser.
- **Optional SMTP alerts:** if configured, private messages can also trigger an email to the original poster.
- **Modern responsive design:** light/dark mode, warm mint/cream palette, subtle motion, mobile forms, friendly illustrations, accessible labels.

## Publish using GitHub (important distinction)

**GitHub is where your source code lives. GitHub Pages cannot execute a Python/Flask backend.** You can publish this repo on GitHub, but a GitHub Pages deployment will only show the *browser-local preview* — not a shared public Lost & Found service. To have public accounts/posts/uploads that everyone can see, you must deploy the Flask app to a Python hosting service.

### A. Upload code to a GitHub repository

1. Create an empty GitHub repository such as `reunite-lost-and-found`.
2. In the extracted project folder, use:

   ```bash
   git init
   git add .
   git commit -m "Build Reunite lost and found website"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/reunite-lost-and-found.git
   git push -u origin main
   ```

3. Make sure you **never** commit the `data` directory contents, private contact records, SMTP passwords, or the generated `.flask_secret` file.

### B. Deploy the working Python app

1. Create a Python web service on a provider such as Render or another Python-compatible host and connect your GitHub repo.
2. Build command: `pip install -r requirements.txt`.
3. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60`.
4. Set environment variable `SECRET_KEY` to a random, long string and `COOKIE_SECURE=1` when hosted over HTTPS.
5. **Set persistent storage for both SQLite and uploaded images.** For example, on Render add a persistent disk at `/var/data/reunite` and set `DATA_DIR=/var/data/reunite`. This may require a paid hosting plan. Without persistent storage, uploaded images and reports can disappear after a restart or redeployment. Alternatively, adapt the backend to PostgreSQL + object storage.
6. You can use the provided `render.yaml` as a starter, but you still must configure durable storage before accepting real user posts.

### C. Optional email notifications

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` in your hosting provider's secret environment variables to send an email when someone contacts a post owner. Without SMTP, posts/messages **still work**, but owners must check their saved management link for replies. For larger-scale hosting, use a proper transactional email provider and domain authentication.

## Privacy and deployment warnings

This is a **student-project starter**, not a fully hardened production service. Do not use it for high-risk/sensitive data without adding real accounts, moderation tools, upload abuse controls, spam/bot protection, backup procedures, and data retention policy. The private management link functions like a password: **anyone with it can manage the listing**. Only the first name is shown publicly, but what people choose to write in descriptions/images may disclose personal information. Photos are converted to WebP by Pillow to strip common metadata. Avoid uploading government-ID details, full names visible on cards, or serial numbers. For real deployments, use HTTPS and durable storage/backups.

## API routes

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/config` | Obtain CSRF token |
| GET | `/api/stats` | Counters |
| GET | `/api/items` | Feed filters, pagination |
| POST | `/api/items` | Create Lost or Found report + optional photo |
| GET | `/api/items/<id>/matches` | Possible opposite-type matches |
| POST | `/api/items/<id>/inquiries` | Send private inquiry |
| GET | `/api/manage/<token>` | Owner-only report/messages |
| PATCH | `/api/manage/<token>` | Mark reunited / reopen |
| DELETE | `/api/manage/<token>` | Delete report + inquiries + photo |
| GET | `/health` | Deployment health check |

## Making it your own

Change the site name and copy in `index.html`, colors in `static/css/styles.css` (`:root` CSS variables), categories in both `static/js/app.js` and `app.py`, and the matching weights in `matching_items()` in `app.py`. The frontend in browser preview mode uses its own equivalent simple matching routine in `static/js/api.js`.

Made to be straightforward to understand, demo, modify, and push to GitHub.

## Run included tests

After installing `requirements.txt`, run `python -m unittest discover -s tests -v` from the project folder. The tests cover report creation, contact privacy, CSRF protection, messages/status changes, image uploads, and matching.

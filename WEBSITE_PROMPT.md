# Website-generation prompt: Reunite — Lost & Found Smart Matcher

Create a complete, elegant, beginner-friendly, real-world **Lost & Found website called “Reunite”** using **Python Flask + SQLite for the backend, and HTML5, CSS3, and vanilla JavaScript for the frontend**. It must be easy to open locally in a browser, with an optional functional offline/localStorage preview. Provide all source files, dependencies, setup instructions, a README, and guidance for uploading to GitHub and deploying the Python backend on a hosting provider.

## Core sections

**1. “I Found Something” reporting:** Let someone upload a photo of the item, write its name and a helpful description, choose a category and color, specify the exact or approximate place and date they found it, and provide private contact details. Validate every field, accept PNG/JPG/WebP photos safely, and support camera upload on mobile.

**2. “I Lost Something” reporting:** Let an owner upload a prior photo (optional), describe their lost item, specify color, category, when/where it was lost, their name and at least one private contact method (email or phone). Offer a friendly, simplified form with clear validation and a photo preview.

**3. Community social feed:** Build a fluid, vertical, scrollable feed inspired by the ease of Instagram Threads, Twitter/X, and modern community apps, while making the design original. Each post shows a polished photo/illustration, title, short description, Lost/Found/Reunited status, category, date, approximate location, and first name only. Include All/Lost/Found/Reunited tabs, live search, category filters, newest/oldest sorting, responsive cards, pagination or load more, and helpful empty states.

## Additional creative features

- A simple **smart matching suggestion system**: compare Lost versus Found posts using matching category, overlapping keywords, color, and location. Show transparent, explainable scores labeled *possible match*, not as guaranteed matches.
- Safe **“This might be mine / I have a lead” private inquiry** with message, sender name, and contact details, visible only to the original poster on a private management page.
- A private shareable **report management link** generated after submission, letting the original poster read messages, mark an item reunited, reopen it, or delete the report and images. Explain that the link must be saved privately.
- Dynamic community statistics: total items reported, active reports, and happy reunions.
- “My reports” list of the current browser’s saved private dashboard links.
- Helpful privacy reminders and a simple 3-step “How it works” section.
- An optional dark theme, nice subtle transitions, mobile-first design, responsive layouts, toast notifications, progress/loading states, and cheerful microcopy.
- Fictional example posts clearly marked SAMPLE for the browser-only preview, without mixing them into real public data.

## Visual direction

The aesthetic should be **fresh, warm, subtly futuristic, and emotionally reassuring — not overly techy**. Use a soft off-white or ivory background, deep forest green typography, sage/mint green accents, hints of peach/lilac, gentle gradients, clean rounded cards, lots of whitespace, small tasteful illustrations, and soft shadows. Headings should feel bold yet friendly, with rounded readable typography. Build an expressive hero (“Good things find their way back.”) with inviting “I lost something” / “I found something” buttons, a tasteful floating illustrative item card, and live activity statistics. Keep UI readable, delightful, and fast on both desktop and phone. Do not overuse glassmorphism, neon, or difficult animations.

## Technical and security requirements

Use clean Flask routes with persistent SQLite data and uploaded image storage, server-side form validation, randomly named filenames, sensible upload limits, image verification/metadata cleanup, parameterized SQL queries, HTML output escaping, CSRF protection for writes, and safe handling of private details. Public APIs must **never return email or phone numbers**. Include optional SMTP notifications; otherwise clearly explain owners must check the private dashboard. Provide `requirements.txt`, `.gitignore`, `.env.example`, `README.md`, and a deployment starter. Never claim that GitHub Pages can run Flask: explain it can host only a static preview while a real shared website requires a Python-capable web server and durable photo/database storage.

## Deliverables

A complete working project ZIP with all code, a double-clickable `index.html` browser preview, a local `python app.py` server, a beginner-friendly launcher for Windows, clean project structure, and detailed instructions to push to GitHub and deploy publicly. Avoid fake functionality and avoid dependencies that require a paid API key.

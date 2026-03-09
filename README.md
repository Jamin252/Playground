# TradeBoard (A-Level project starter)

TradeBoard is a beginner-friendly Flask web app for item trading (no payments), inspired by marketplace platforms like eBay.

## Features
- User registration and login
- Item listings with optional photos
- Categories for items
- Search and category filter
- Messaging system between users
- Seller profile pages

## Tech stack
- Flask (backend + routing)
- Flask-Login (authentication)
- Flask-SQLAlchemy (database ORM)
- SQL database via SQLAlchemy connection string
  - Default: SQLite (`trading.db`)
  - You can switch to MySQL/PostgreSQL by setting `DATABASE_URL`

## Quick start
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python app.py
   ```
3. Open: `http://127.0.0.1:5000`

## Database setup
The app automatically creates tables when started from `python app.py`.

To use a different SQL server:
```bash
export DATABASE_URL='mysql+pymysql://user:password@localhost/tradeboard'
python app.py
```

## Project structure
- `app.py` - Models, routes, and app configuration.
- `templates/` - HTML pages.
- `static/style.css` - Basic styling.
- `static/uploads/` - Uploaded item photos.
- `DOCUMENTATION.md` - Detailed function-by-function explanation.

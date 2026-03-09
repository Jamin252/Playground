# TradeBoard Documentation

This document explains the design ideas, files, and functions in the project.

## 1) Design idea
TradeBoard is designed for beginners:
- One main Python file (`app.py`) so learners can find logic quickly.
- Clear route names (`/register`, `/items/new`, `/messages/<user_id>`) that match app features.
- SQLAlchemy models used instead of writing raw SQL for easier understanding.
- Simple templates with reusable base layout (`base.html`).

The app focuses on **trading communication**, not online payments.

## 2) File-by-file explanation

### `app.py`
Main application file containing:
1. Flask config
2. Database models
3. Utility functions
4. Routes (views)

### `templates/base.html`
Base template with shared navigation and flash-message display.

### `templates/index.html`
Homepage with item grid, search box, and category filter dropdown.

### `templates/register.html` and `templates/login.html`
Forms for account creation and login.

### `templates/create_item.html`
Form to create listings with title, description, category, and optional image upload.

### `templates/edit_item.html`
Form to edit a listing the owner has already posted.

### `templates/item_detail.html`
Shows a single item in full detail and includes:
- quick message form to contact seller
- edit/delete controls for owner

### `templates/messages.html`
WhatsApp-like chat interface:
- left side: user chat list
- right side: message bubbles and composer

### `templates/profile.html`
Seller profile page with seller details and all listings from that seller.
If it is your own profile, you can edit bio and manage listings.

### `templates/edit_profile.html`
Form to update your bio.

### `static/style.css`
Responsive styling with eBay-inspired colors and chat bubble layout.

### `requirements.txt`
Python packages required to run the app.

## 3) Model design (`app.py`)

### `User`
Represents a registered user.
- `username`, `email`, `password_hash`
- `bio`, `created_at`
- Relationship: one user can have many items.

Helper methods:
- `set_password(password)` - hashes plain password before storing.
- `check_password(password)` - verifies login password.

### `Category`
Stores item categories (Electronics, Books, etc.).
- `name`
- Relationship: one category can contain many items.

### `Item`
Represents listed items.
- `title`, `description`, `image_filename`, `created_at`
- Foreign keys:
  - `user_id` -> seller
  - `category_id` -> category

### `Message`
Private message between two users.
- `sender_id`, `receiver_id`, optional `item_id`
- `body`, `created_at`

## 4) Utility functions (`app.py`)

### `load_user(user_id)`
Used by Flask-Login to load the logged-in user from session.

### `allowed_file(filename)`
Checks whether uploaded file extension is in allowed image list.

### `save_image(image_file)`
Creates a unique file name and stores uploaded image in `static/uploads/`.

### `seed_categories()`
Inserts default categories into database if they do not already exist.

## 5) Route/function documentation (`app.py`)

### `index()` -> `GET /`
Loads all items, optionally filtered by:
- search query (`q`) against title
- category (`category`)

### `register()` -> `GET/POST /register`
Creates new user account.
- Validates required fields
- Checks duplicate username/email
- Stores hashed password

### `login()` -> `GET/POST /login`
Authenticates user with email and password.

### `logout()` -> `GET /logout`
Logs out current user.

### `edit_profile()` -> `GET/POST /profile/edit`
Allows logged-in user to update their bio.

### `create_item()` -> `GET/POST /items/new`
Allows logged-in user to publish listing.
- Validates required fields
- Validates optional image extension
- Saves image into `static/uploads/`

### `edit_item(item_id)` -> `GET/POST /items/<id>/edit`
Allows owner of listing to modify title, description, category, and image.

### `delete_item(item_id)` -> `POST /items/<id>/delete`
Allows owner of listing to remove listing.

### `item_detail(item_id)` -> `GET /items/<id>`
Shows item details and seller information.

### `messages()` -> `GET /messages`
Redirects user to first available chat contact.

### `conversation(user_id)` -> `GET/POST /messages/<user_id>`
- `GET`: shows conversation thread (chat bubbles)
- `POST`: sends message to selected user

### `profile(user_id)` -> `GET /profile/<id>`
Shows public seller profile and all of their listings.

### `uploaded_file(filename)` -> `GET /uploads/<filename>`
Serves uploaded image files.

## 6) Beginner extension ideas
- Add listing "condition" and location fields.
- Add profile avatar uploads.
- Add read/unread message status badges.
- Add pagination for large item lists.
- Add form validation with Flask-WTF.

## 7) Security notes (important)
- Change `SECRET_KEY` in production.
- Add stricter image validation (MIME/content checks).
- Consider file size limits for uploads.
- Add CSRF protection before deployment.

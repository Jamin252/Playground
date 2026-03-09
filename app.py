import os
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "replace-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'trading.db'}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("Item", backref="seller", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    items = db.relationship("Item", backref="category", lazy=True)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")
    item = db.relationship("Item", backref="messages")


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(image_file) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_name = secure_filename(image_file.filename)
    image_filename = f"{timestamp}_{safe_name}"
    image_file.save(UPLOAD_FOLDER / image_filename)
    return image_filename


def is_listing_owner(item: Item) -> bool:
    return current_user.is_authenticated and item.user_id == current_user.id


def seed_categories() -> None:
    default_categories = ["Electronics", "Books", "Clothing", "Home", "Sports", "Other"]
    for category_name in default_categories:
        exists = Category.query.filter_by(name=category_name).first()
        if not exists:
            db.session.add(Category(name=category_name))
    db.session.commit()


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)

    query = Item.query.order_by(Item.created_at.desc())

    if search:
        query = query.filter(or_(Item.title.ilike(f"%{search}%"), Item.description.ilike(f"%{search}%")))

    if category_id:
        query = query.filter(Item.category_id == category_id)

    items = query.all()
    categories = Category.query.order_by(Category.name).all()
    return render_template("index.html", items=items, categories=categories, search=search, category_id=category_id)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        duplicate = User.query.filter((User.username == username) | (User.email == email)).first()
        if duplicate:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("register"))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


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
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))

        flash("Invalid credentials.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.bio = request.form.get("bio", "").strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile", user_id=current_user.id))

    return render_template("edit_profile.html")


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def create_item():
    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)
        image = request.files.get("image")

        if not title or not description or not category_id:
            flash("Title, description and category are required.", "danger")
            return redirect(url_for("create_item"))

        image_filename = None
        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Image must be png, jpg, jpeg, or gif.", "danger")
                return redirect(url_for("create_item"))
            image_filename = save_image(image)

        item = Item(
            title=title,
            description=description,
            user_id=current_user.id,
            category_id=category_id,
            image_filename=image_filename,
        )
        db.session.add(item)
        db.session.commit()

        flash("Item listed successfully.", "success")
        return redirect(url_for("item_detail", item_id=item.id))

    return render_template("create_item.html", categories=categories)


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    if not is_listing_owner(item):
        flash("You can only edit your own listings.", "danger")
        return redirect(url_for("item_detail", item_id=item.id))

    categories = Category.query.order_by(Category.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", type=int)
        image = request.files.get("image")

        if not title or not description or not category_id:
            flash("Title, description and category are required.", "danger")
            return redirect(url_for("edit_item", item_id=item.id))

        item.title = title
        item.description = description
        item.category_id = category_id

        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Image must be png, jpg, jpeg, or gif.", "danger")
                return redirect(url_for("edit_item", item_id=item.id))
            item.image_filename = save_image(image)

        db.session.commit()
        flash("Listing updated.", "success")
        return redirect(url_for("item_detail", item_id=item.id))

    return render_template("edit_item.html", item=item, categories=categories)


@app.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    if not is_listing_owner(item):
        flash("You can only remove your own listings.", "danger")
        return redirect(url_for("item_detail", item_id=item.id))

    Message.query.filter_by(item_id=item.id).update({"item_id": None})
    db.session.delete(item)
    db.session.commit()

    flash("Listing removed.", "info")
    return redirect(url_for("profile", user_id=current_user.id))


@app.route("/items/<int:item_id>")
def item_detail(item_id: int):
    item = Item.query.get_or_404(item_id)
    return render_template("item_detail.html", item=item)


@app.route("/messages", methods=["GET"])
@login_required
def messages():
    requested_user_id = request.args.get("with", type=int)
    if requested_user_id and requested_user_id != current_user.id:
        return redirect(url_for("conversation", user_id=requested_user_id))

    first_contact = User.query.filter(User.id != current_user.id).order_by(User.username.asc()).first()
    if not first_contact:
        flash("No other users available yet to chat with.", "info")
        return redirect(url_for("index"))

    return redirect(url_for("conversation", user_id=first_contact.id))


@app.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
def conversation(user_id: int):
    contact = User.query.get_or_404(user_id)
    if contact.id == current_user.id:
        flash("Choose another user to start chatting.", "info")
        return redirect(url_for("messages"))

    selected_item_id = request.args.get("item_id", type=int)

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        item_id = request.form.get("item_id", type=int)

        if not body:
            flash("Message cannot be empty.", "danger")
            return redirect(url_for("conversation", user_id=contact.id))

        db.session.add(Message(sender_id=current_user.id, receiver_id=contact.id, item_id=item_id, body=body))
        db.session.commit()
        return redirect(url_for("conversation", user_id=contact.id))

    contacts = User.query.filter(User.id != current_user.id).order_by(User.username.asc()).all()
    conversation_messages = (
        Message.query.filter(
            or_(
                (Message.sender_id == current_user.id) & (Message.receiver_id == contact.id),
                (Message.sender_id == contact.id) & (Message.receiver_id == current_user.id),
            )
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return render_template(
        "messages.html",
        contacts=contacts,
        contact=contact,
        messages=conversation_messages,
        selected_item_id=selected_item_id,
    )


@app.route("/profile/<int:user_id>")
def profile(user_id: int):
    seller = User.query.get_or_404(user_id)
    seller_items = Item.query.filter_by(user_id=seller.id).order_by(Item.created_at.desc()).all()
    return render_template("profile.html", seller=seller, seller_items=seller_items)


@app.route("/uploads/<filename>")
def uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_categories()
    app.run(debug=True)

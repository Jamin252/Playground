import os
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, inspect, or_, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "replace-me-in-production"
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

    items = db.relationship("Item", backref="seller", lazy=True, foreign_keys="Item.user_id")
    reviews_received = db.relationship("Review", foreign_keys="Review.reviewee_id", backref="reviewee", lazy=True)
    reviews_given = db.relationship("Review", foreign_keys="Review.reviewer_id", backref="reviewer", lazy=True)

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
    status = db.Column(db.String(20), default="open", nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    sold_to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    sold_to = db.relationship("User", foreign_keys=[sold_to_user_id])

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


class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    location_suggestion = db.Column(db.String(255), nullable=True)
    location_suggested_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    buyer_agreed = db.Column(db.Boolean, default=False, nullable=False)
    seller_agreed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship("Item", backref="deals")
    buyer = db.relationship("User", foreign_keys=[buyer_id], backref="buyer_deals")
    seller = db.relationship("User", foreign_keys=[seller_id], backref="seller_deals")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship("Item", backref="reviews")


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def seed_categories() -> None:
    default_categories = ["Electronics", "Books", "Clothing", "Home", "Sports", "Other"]
    for category_name in default_categories:
        exists = Category.query.filter_by(name=category_name).first()
        if not exists:
            db.session.add(Category(name=category_name))
    db.session.commit()


def run_schema_migrations() -> None:
    inspector = inspect(db.engine)
    item_columns = {column["name"] for column in inspector.get_columns("item")}

    if "status" not in item_columns:
        db.session.execute(text("ALTER TABLE item ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'"))
    if "closed_at" not in item_columns:
        db.session.execute(text("ALTER TABLE item ADD COLUMN closed_at DATETIME"))
    if "sold_to_user_id" not in item_columns:
        db.session.execute(text("ALTER TABLE item ADD COLUMN sold_to_user_id INTEGER"))

    tables = set(inspector.get_table_names())
    if "deal" not in tables:
        Deal.__table__.create(db.engine)
    if "review" not in tables:
        Review.__table__.create(db.engine)

    db.session.execute(text("UPDATE item SET status='open' WHERE status IS NULL OR status=''"))
    db.session.execute(text("UPDATE item SET status='closed_down' WHERE status='put_down'"))
    db.session.commit()


def get_conversation_deals(other_user_id: int):
    return (
        Deal.query.join(Item, Item.id == Deal.item_id)
        .filter(
            or_(
                and_(Deal.seller_id == current_user.id, Deal.buyer_id == other_user_id),
                and_(Deal.buyer_id == current_user.id, Deal.seller_id == other_user_id),
            )
        )
        .order_by(Item.created_at.desc())
        .all()
    )


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    sort = request.args.get("sort", "date_desc")
    show_closed = request.args.get("show_closed") == "1"
    show_sold = request.args.get("show_sold") == "1"

    query = Item.query

    if search:
        query = query.filter(Item.title.ilike(f"%{search}%"))

    if category_id:
        query = query.filter(Item.category_id == category_id)

    allowed_statuses = ["open"]
    if show_closed:
        allowed_statuses.append("closed_down")
    if show_sold:
        allowed_statuses.append("sold")
    query = query.filter(Item.status.in_(allowed_statuses))

    if sort == "date_asc":
        query = query.order_by(Item.created_at.asc())
    else:
        sort = "date_desc"
        query = query.order_by(Item.created_at.desc())

    items = query.all()
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "index.html",
        items=items,
        categories=categories,
        search=search,
        category_id=category_id,
        sort=sort,
        show_closed=show_closed,
        show_sold=show_sold,
    )


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

        if User.query.filter((User.username == username) | (User.email == email)).first():
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

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            image_filename = f"{timestamp}_{secure_filename(image.filename)}"
            image.save(UPLOAD_FOLDER / image_filename)

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


@app.route("/items/<int:item_id>")
def item_detail(item_id: int):
    item = Item.query.get_or_404(item_id)
    current_deal = None
    if current_user.is_authenticated and current_user.id != item.user_id:
        current_deal = Deal.query.filter_by(item_id=item.id, buyer_id=current_user.id, seller_id=item.user_id).first()
    return render_template("item_detail.html", item=item, current_deal=current_deal)


@app.route("/items/<int:item_id>/status", methods=["POST"])
@login_required
def update_item_status(item_id: int):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You can only close your own listing.", "danger")
        return redirect(url_for("item_detail", item_id=item.id))

    status = request.form.get("status")
    if status not in {"closed_down", "sold"}:
        flash("Invalid status.", "danger")
        return redirect(url_for("item_detail", item_id=item.id))

    item.status = status
    item.closed_at = datetime.utcnow()

    if status == "sold":
        sold_to_user_id = request.form.get("sold_to_user_id", type=int)
        if sold_to_user_id:
            valid_buyer = Deal.query.filter_by(item_id=item.id, buyer_id=sold_to_user_id, seller_id=current_user.id).first()
            if not valid_buyer:
                flash("Selected buyer is not valid for this listing.", "danger")
                return redirect(url_for("item_detail", item_id=item.id))
            item.sold_to_user_id = sold_to_user_id
        else:
            item.sold_to_user_id = None
    else:
        item.sold_to_user_id = None

    db.session.commit()
    flash("Listing status updated.", "success")
    return redirect(url_for("item_detail", item_id=item.id))


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
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

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            image_filename = f"{timestamp}_{secure_filename(image.filename)}"
            image.save(UPLOAD_FOLDER / image_filename)
            item.image_filename = image_filename

        db.session.commit()
        flash("Listing updated.", "success")
        return redirect(url_for("item_detail", item_id=item.id))

    return render_template("edit_item.html", item=item, categories=categories)


@app.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: int):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("You can only close your own listings.", "danger")
        return redirect(url_for("item_detail", item_id=item.id))

    item.status = "closed_down"
    item.closed_at = datetime.utcnow()
    db.session.commit()
    flash("Listing marked as closed down.", "info")
    return redirect(url_for("profile", user_id=current_user.id))


@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages():
    selected_user_id = request.args.get("user", type=int)

    if request.method == "POST":
        action = request.form.get("action", "message")

        if action == "message":
            receiver_id = request.form.get("receiver_id", type=int)
            item_id = request.form.get("item_id", type=int)
            body = request.form.get("body", "").strip()

            if not receiver_id or not body:
                flash("Receiver and message body are required.", "danger")
                return redirect(url_for("messages"))

            message = Message(sender_id=current_user.id, receiver_id=receiver_id, item_id=item_id, body=body)
            db.session.add(message)
            db.session.commit()
            flash("Message sent.", "success")
            return redirect(url_for("messages", user=receiver_id))

        if action == "suggest_location":
            receiver_id = request.form.get("receiver_id", type=int)
            item_id = request.form.get("item_id", type=int)
            location = request.form.get("location_suggestion", "").strip()

            if not receiver_id or not item_id or not location:
                flash("Receiver, item and location are required.", "danger")
                return redirect(url_for("messages", user=receiver_id))

            item = Item.query.get_or_404(item_id)
            if item.user_id not in {current_user.id, receiver_id}:
                flash("This deal is not valid.", "danger")
                return redirect(url_for("messages", user=receiver_id))

            seller_id = item.user_id
            buyer_id = receiver_id if current_user.id == seller_id else current_user.id
            if current_user.id == seller_id and receiver_id == seller_id:
                flash("You cannot suggest a deal with yourself.", "danger")
                return redirect(url_for("messages"))

            deal = Deal.query.filter_by(item_id=item_id, buyer_id=buyer_id, seller_id=seller_id).first()
            if not deal:
                deal = Deal(item_id=item_id, buyer_id=buyer_id, seller_id=seller_id)
                db.session.add(deal)

            if deal.buyer_agreed and deal.seller_agreed:
                flash("Location is locked because both sides already agreed.", "danger")
                return redirect(url_for("messages", user=receiver_id))

            deal.location_suggestion = location
            deal.location_suggested_by_id = current_user.id
            deal.buyer_agreed = False
            deal.seller_agreed = False

            db.session.commit()
            flash("Location suggestion sent.", "success")
            return redirect(url_for("messages", user=receiver_id))

        if action == "agree_location":
            receiver_id = request.form.get("receiver_id", type=int)
            deal_id = request.form.get("deal_id", type=int)
            deal = Deal.query.get_or_404(deal_id)

            if current_user.id not in {deal.buyer_id, deal.seller_id}:
                flash("You cannot update this deal.", "danger")
                return redirect(url_for("messages"))

            if deal.buyer_agreed and deal.seller_agreed:
                flash("Location already locked.", "info")
                return redirect(url_for("messages", user=receiver_id))

            if current_user.id == deal.buyer_id:
                deal.buyer_agreed = True
            else:
                deal.seller_agreed = True

            db.session.commit()
            if deal.buyer_agreed and deal.seller_agreed:
                flash("Both parties agreed. Location is now locked.", "success")
            else:
                flash("Your agreement is saved.", "success")

            return redirect(url_for("messages", user=receiver_id))

    if selected_user_id == current_user.id:
        selected_user_id = None

    conversation_users = (
        User.query.join(
            Message,
            or_(
                and_(Message.sender_id == current_user.id, Message.receiver_id == User.id),
                and_(Message.receiver_id == current_user.id, Message.sender_id == User.id),
            ),
        )
        .distinct()
        .order_by(User.username)
        .all()
    )

    users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
    if not selected_user_id and conversation_users:
        selected_user_id = conversation_users[0].id

    thread = []
    selected_user = None
    deals = []
    if selected_user_id:
        selected_user = User.query.get(selected_user_id)
        if selected_user and selected_user.id != current_user.id:
            thread = (
                Message.query.filter(
                    or_(
                        and_(Message.sender_id == current_user.id, Message.receiver_id == selected_user.id),
                        and_(Message.sender_id == selected_user.id, Message.receiver_id == current_user.id),
                    )
                )
                .order_by(Message.created_at.asc())
                .all()
            )
            deals = get_conversation_deals(selected_user.id)

    return render_template(
        "messages.html",
        users=users,
        conversation_users=conversation_users,
        thread=thread,
        selected_user=selected_user,
        selected_user_id=selected_user_id,
        deals=deals,
    )


@app.route("/items/<int:item_id>/reviews", methods=["POST"])
@login_required
def submit_review(item_id: int):
    item = Item.query.get_or_404(item_id)
    if item.status != "sold":
        flash("Reviews are only allowed for sold items.", "danger")
        return redirect(url_for("item_detail", item_id=item_id))

    buyer_id = item.sold_to_user_id
    if not buyer_id:
        flash("A buyer must be selected before reviewing.", "danger")
        return redirect(url_for("item_detail", item_id=item_id))

    if current_user.id not in {item.user_id, buyer_id}:
        flash("Only buyer and seller can review this sale.", "danger")
        return redirect(url_for("item_detail", item_id=item_id))

    rating = request.form.get("rating", type=int)
    if not rating or rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("item_detail", item_id=item_id))

    reviewee_id = buyer_id if current_user.id == item.user_id else item.user_id
    existing = Review.query.filter_by(item_id=item_id, reviewer_id=current_user.id).first()
    if existing:
        flash("You already submitted a review for this item.", "info")
        return redirect(url_for("item_detail", item_id=item_id))

    db.session.add(Review(item_id=item_id, reviewer_id=current_user.id, reviewee_id=reviewee_id, rating=rating))
    db.session.commit()
    flash("Review submitted.", "success")
    return redirect(url_for("item_detail", item_id=item_id))


@app.route("/profile/<int:user_id>")
def profile(user_id: int):
    seller = User.query.get_or_404(user_id)
    seller_items = Item.query.filter_by(user_id=seller.id).order_by(Item.created_at.desc()).all()
    reviews = Review.query.filter_by(reviewee_id=seller.id).order_by(Review.created_at.desc()).all()
    average_rating = round(sum(review.rating for review in reviews) / len(reviews), 2) if reviews else None
    return render_template(
        "profile.html",
        seller=seller,
        seller_items=seller_items,
        reviews=reviews,
        average_rating=average_rating,
    )


@app.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.bio = request.form.get("bio", "").strip()
        db.session.commit()
        flash("Bio updated.", "success")
        return redirect(url_for("profile", user_id=current_user.id))

    return render_template("edit_profile.html")


@app.route("/uploads/<filename>")
def uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        run_schema_migrations()
        seed_categories()
    app.run(debug=True)

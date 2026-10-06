import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo import DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash


SAMPLE_POSTS = [
    {
        "category": "CREATIVITY",
        "title": "Finding time for your own ideas",
        "content": (
            "The best ideas do not always arrive when we are looking for them. "
            "Sometimes they show up in the quiet moments between tasks, or when "
            "we finally give ourselves room to try something new.\n\n"
            "I have been learning that making time for creativity does not need "
            "to mean a perfect schedule. A short walk, a notebook nearby, or "
            "ten minutes away from a screen can be enough to start. The important "
            "part is to stay curious and keep going, even when the first attempt "
            "is not quite what you imagined."
        ),
        "excerpt": "Chiranth shares a few simple ways to make room for learning, creativity, and the projects that matter.",
        "author_name": "Chiranth Vraj P",
        "author_email": "chiranth.vraj.p@example.com",
        "date": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "color": "lavender",
    },
    {
        "category": "LIFE",
        "title": "Small habits, brighter mornings",
        "content": (
            "A calmer morning can begin with one small change. Bhuvan has been "
            "trying to leave a little time before the day gets busy: opening the "
            "window, making a cup of tea, and deciding what matters most today.\n\n"
            "It is not about making every morning perfect. It is about finding "
            "a routine that helps you start with a clearer head, one ordinary "
            "day at a time."
        ),
        "excerpt": "Bhuvan shares how a calmer start to the day can make space for better focus and fresh ideas.",
        "author_name": "Bhuvan",
        "author_email": "bhuvan@example.com",
        "date": datetime(2026, 10, 3, tzinfo=timezone.utc),
        "color": "peach",
    },
    {
        "category": "LEARNING",
        "title": "Learning by building something real",
        "content": (
            "Manoj's favorite way to learn a new skill is to build something "
            "small with it. A working project turns abstract ideas into real "
            "questions: What happens when the input is empty? How should an error "
            "be shown? What can be made clearer?\n\n"
            "Mistakes are part of the process. Each one is a chance to read the "
            "message, understand the cause, and try again with a little more "
            "confidence."
        ),
        "excerpt": "Manoj reflects on turning a new skill into a small project and learning from every mistake along the way.",
        "author_name": "Manoj",
        "author_email": "manoj@example.com",
        "date": datetime(2026, 10, 1, tzinfo=timezone.utc),
        "color": "mint",
    },
    {
        "category": "CREATIVITY",
        "title": "A notebook full of possibilities",
        "content": (
            "Sanketh keeps a notebook for things that catch his attention: a "
            "question from a conversation, an interesting sign, or a solution "
            "that could be a little easier to use.\n\n"
            "Not every note needs to become a project. Collecting observations "
            "is valuable on its own, and sometimes a few unrelated notes become "
            "the beginning of a new idea."
        ),
        "excerpt": "Sanketh writes about collecting everyday observations and turning them into ideas worth exploring.",
        "author_name": "Sanketh",
        "author_email": "sanketh@example.com",
        "date": datetime(2026, 9, 29, tzinfo=timezone.utc),
        "color": "peach",
    },
    {
        "category": "LIFE",
        "title": "Making a little space to think",
        "content": (
            "When everything feels urgent, Prabhudev finds it helpful to pause "
            "and write down what actually needs attention. A short list can turn "
            "a noisy day into a few manageable next steps.\n\n"
            "Taking a break is not wasted time. A moment to reset can make it "
            "easier to return to the work with patience and a clearer mind."
        ),
        "excerpt": "Prabhudev shares a few practical ways to step back, reset, and return to the day with a clearer mind.",
        "author_name": "Prabhudev",
        "author_email": "prabhudev@example.com",
        "date": datetime(2026, 9, 26, tzinfo=timezone.utc),
        "color": "lavender",
    },
    {
        "category": "LEARNING",
        "title": "Curiosity is a good place to start",
        "content": (
            "Nethra likes to begin learning with a question. Instead of worrying "
            "about how much there is to know, she picks one thing she does not "
            "understand and follows it a little further.\n\n"
            "Questions make a subject feel more personal. They help us connect "
            "new information to what we already know and keep the process "
            "interesting, even when it takes time."
        ),
        "excerpt": "Nethra explores how asking one more question can make learning feel less like a task and more like an adventure.",
        "author_name": "Nethra",
        "author_email": "nethra@example.com",
        "date": datetime(2026, 9, 23, tzinfo=timezone.utc),
        "color": "mint",
    },
]


def utc_now():
    return datetime.now(timezone.utc)


def api_request():
    return request.path.startswith("/api/")


def api_error(message, status):
    return jsonify({"error": message}), status


def json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Send the request body as a JSON object.")
    return payload


def post_document(post):
    return {
        "id": str(post["_id"]),
        "title": post["title"],
        "content": post["content"],
        "author": post["author_name"],
        "author_id": str(post["author_id"]) if post.get("author_id") else None,
        "created_at": post["created_at"].isoformat(),
        "updated_at": post.get("updated_at").isoformat() if post.get("updated_at") else None,
        "is_demo": bool(post.get("is_demo")),
    }


def comment_document(comment):
    return {
        "id": str(comment["_id"]),
        "text": comment["text"],
        "author": comment["author_name"],
        "author_id": str(comment["author_id"]),
        "post_id": str(comment["post_id"]),
        "created_at": comment["created_at"].isoformat(),
    }


def find_post(post_id):
    if not ObjectId.is_valid(post_id):
        return None
    return g.db.posts.find_one({"_id": ObjectId(post_id)})


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-before-deploying"),
        MONGO_URI=os.environ.get("MONGO_URI", "mongodb://127.0.0.1:27017"),
        MONGO_DATABASE=os.environ.get("MONGO_DATABASE", "little_stories"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    app.logger.setLevel(logging.INFO)
    app.mongo_client = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=2000,
        tz_aware=True,
    )
    app.mongo_db = app.mongo_client[app.config["MONGO_DATABASE"]]
    try:
        app.mongo_client.admin.command("ping")
        app.mongo_db.users.create_index("email", unique=True)
        app.mongo_db.posts.create_index([("created_at", DESCENDING)])
        app.mongo_db.comments.create_index([("post_id", 1), ("created_at", 1)])
        app.logger.info("Connected to MongoDB database '%s'.", app.config["MONGO_DATABASE"])
    except PyMongoError:
        app.logger.warning("MongoDB is unavailable at startup. Check that MongoDB is running and reload the site.")

    @app.before_request
    def load_request_data():
        g.db = app.mongo_db
        g.user = None
        user_id = session.get("user_id")
        if user_id and ObjectId.is_valid(user_id):
            g.user = g.db.users.find_one({"_id": ObjectId(user_id)})

    @app.context_processor
    def add_template_values():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"current_user": g.get("user"), "csrf_token": session["csrf_token"]}

    @app.template_filter("pretty_date")
    def pretty_date(value):
        if not value:
            return ""
        return value.strftime("%B %-d, %Y") if os.name != "nt" else value.strftime("%B %#d, %Y")

    @app.errorhandler(PyMongoError)
    def handle_database_error(error):
        app.logger.error("MongoDB request failed (%s).", type(error).__name__)
        message = "The database is not available. Start MongoDB and try again."
        if api_request():
            return api_error(message, 503)
        return render_template("error.html", message=message), 503

    @app.errorhandler(413)
    def handle_large_request(_error):
        if api_request():
            return api_error("The request is too large.", 413)
        flash("That form is too large. Please shorten the content and try again.", "danger")
        return redirect(url_for("home"))

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                if api_request():
                    return api_error("Log in to perform this action.", 401)
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def valid_csrf():
        submitted = request.headers.get("X-CSRF-Token")
        if submitted is None:
            submitted = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        return bool(expected and submitted and hmac.compare_digest(expected, submitted))

    def require_csrf():
        if valid_csrf():
            return None
        if api_request():
            return api_error("Your security token is missing or expired. Reload and try again.", 400)
        abort(400, description="Your security token is missing or expired. Reload the page and try again.")

    def get_posts(query=None):
        cursor = g.db.posts.find(query or {}).sort("created_at", DESCENDING)
        return list(cursor)

    def post_form_values(payload):
        title = str(payload.get("title", "")).strip()
        content = str(payload.get("content", "")).strip()
        errors = []
        if not title:
            errors.append("A title is required.")
        elif len(title) > 160:
            errors.append("Titles must be 160 characters or fewer.")
        if not content:
            errors.append("Post content is required.")
        elif len(content) > 20000:
            errors.append("Post content must be 20,000 characters or fewer.")
        values = {"title": title, "content": content}
        return values, errors

    @app.route("/")
    def home():
        if g.db.posts.count_documents({}) == 0:
            g.db.posts.insert_many(
                [
                    {
                        "title": sample["title"],
                        "content": sample["content"],
                        "category": sample["category"],
                        "excerpt": sample["excerpt"],
                        "author_id": None,
                        "author_name": sample["author_name"],
                        "author_email": sample["author_email"],
                        "created_at": sample["date"],
                        "updated_at": None,
                        "is_demo": True,
                        "color": sample["color"],
                    }
                    for sample in SAMPLE_POSTS
                ]
            )
        posts = get_posts()
        sample_categories = {sample["title"]: sample["category"] for sample in SAMPLE_POSTS}
        for post in posts:
            post["excerpt"] = post.get("excerpt") or post["content"][:180].strip()
            post["color"] = post.get("color", "mint")
            if post.get("is_demo") and not post.get("category"):
                post["category"] = sample_categories.get(post["title"], "STORY")
                g.db.posts.update_one(
                    {"_id": post["_id"], "category": {"$exists": False}},
                    {"$set": {"category": post["category"]}},
                )
            else:
                post["category"] = post.get("category", "STORY")
        return render_template("index.html", posts=posts)

    @app.route("/register", methods=["GET", "POST"])
    @app.route("/api/register", methods=["POST"])
    def register():
        if request.method == "GET":
            return render_template("register.html")
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        payload = request.get_json(silent=True) if api_request() else request.form
        if not isinstance(payload, dict) and not hasattr(payload, "get"):
            if api_request():
                return api_error("Send the request body as a JSON object.", 400)
            payload = {}
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        errors = []
        if not name or len(name) > 80:
            errors.append("Enter your name (up to 80 characters).")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            errors.append("Enter a valid email address.")
        if len(password) < 8 or len(password) > 128:
            errors.append("Choose a password between 8 and 128 characters.")
        if errors:
            if api_request():
                return jsonify({"errors": errors}), 400
            for error in errors:
                flash(error, "danger")
            return render_template("register.html", name=name, email=email), 400
        user = {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "created_at": utc_now(),
        }
        try:
            result = g.db.users.insert_one(user)
        except DuplicateKeyError:
            if api_request():
                return api_error("An account with that email already exists.", 409)
            flash("An account with that email already exists. Try logging in instead.", "danger")
            return render_template("register.html", name=name, email=email), 409
        session.clear()
        session["user_id"] = str(result.inserted_id)
        session["csrf_token"] = secrets.token_urlsafe(32)
        if api_request():
            return jsonify({"message": "Account created.", "user": {"id": str(result.inserted_id), "name": name, "email": email}}), 201
        flash("Your account is ready. Welcome!", "success")
        return redirect(url_for("home"))

    @app.route("/login", methods=["GET", "POST"])
    @app.route("/api/login", methods=["POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html")
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        payload = request.get_json(silent=True) if api_request() else request.form
        if not isinstance(payload, dict) and not hasattr(payload, "get"):
            if api_request():
                return api_error("Send the request body as a JSON object.", 400)
            payload = {}
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        user = g.db.users.find_one({"email": email})
        if not user or not check_password_hash(user["password_hash"], password):
            if api_request():
                return api_error("Email or password is incorrect.", 401)
            flash("Email or password is incorrect.", "danger")
            return render_template("login.html", email=email), 401
        session.clear()
        session["user_id"] = str(user["_id"])
        session["csrf_token"] = secrets.token_urlsafe(32)
        if api_request():
            return jsonify({"message": "Logged in.", "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}})
        flash("Welcome back, {}!".format(user["name"]), "success")
        next_url = request.args.get("next", "")
        if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
            return redirect(next_url)
        return redirect(url_for("home"))

    @app.route("/logout", methods=["POST"])
    @app.route("/api/logout", methods=["POST"])
    def logout():
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        session.clear()
        if api_request():
            return jsonify({"message": "Logged out."})
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    @app.route("/posts/new", methods=["GET", "POST"])
    @login_required
    def create_post():
        if request.method == "GET":
            return render_template("create_post.html")
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        values, errors = post_form_values(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("create_post.html", title=values["title"], content=values["content"]), 400
        result = g.db.posts.insert_one(
            {
                **values,
                "category": "STORY",
                "author_id": g.user["_id"],
                "author_name": g.user["name"],
                "created_at": utc_now(),
                "updated_at": None,
                "is_demo": False,
            }
        )
        flash("Your post has been published.", "success")
        return redirect(url_for("post_detail", post_id=str(result.inserted_id)))

    @app.route("/posts/<post_id>")
    def post_detail(post_id):
        post = find_post(post_id)
        if post is None:
            abort(404)
        post["comments"] = list(g.db.comments.find({"post_id": post["_id"]}).sort("created_at", 1))
        return render_template("post.html", post=post)

    @app.route("/posts/<post_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_post(post_id):
        post = find_post(post_id)
        if post is None:
            abort(404)
        if post.get("author_id") != g.user["_id"]:
            abort(403)
        if request.method == "GET":
            return render_template("edit_post.html", post=post)
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        values, errors = post_form_values(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            post.update(values)
            return render_template("edit_post.html", post=post), 400
        g.db.posts.update_one(
            {"_id": post["_id"], "author_id": g.user["_id"]},
            {"$set": {**values, "updated_at": utc_now()}},
        )
        flash("Your changes have been saved.", "success")
        return redirect(url_for("post_detail", post_id=post_id))

    @app.route("/posts/<post_id>/delete", methods=["POST"])
    @login_required
    def delete_post(post_id):
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        post = find_post(post_id)
        if post is None:
            abort(404)
        if post.get("author_id") != g.user["_id"]:
            abort(403)
        g.db.comments.delete_many({"post_id": post["_id"]})
        g.db.posts.delete_one({"_id": post["_id"], "author_id": g.user["_id"]})
        flash("Your post and its comments have been deleted.", "success")
        return redirect(url_for("my_posts"))

    @app.route("/my-posts")
    @login_required
    def my_posts():
        return render_template("my_posts.html", posts=get_posts({"author_id": g.user["_id"]}))

    @app.route("/posts/<post_id>/comments", methods=["POST"])
    @app.route("/api/posts/<post_id>/comments", methods=["POST"])
    @login_required
    def add_comment(post_id):
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        post = find_post(post_id)
        if post is None:
            if api_request():
                return api_error("Post not found.", 404)
            abort(404)
        if api_request():
            try:
                payload = json_payload()
            except ValueError as error:
                return api_error(str(error), 400)
        else:
            payload = request.form
        text = str(payload.get("text", "")).strip()
        if not text or len(text) > 2000:
            message = "A comment is required and must be 2,000 characters or fewer."
            if api_request():
                return api_error(message, 400)
            flash(message, "danger")
            return redirect(url_for("post_detail", post_id=post_id))
        comment = {
            "text": text,
            "post_id": post["_id"],
            "author_id": g.user["_id"],
            "author_name": g.user["name"],
            "created_at": utc_now(),
        }
        result = g.db.comments.insert_one(comment)
        comment["_id"] = result.inserted_id
        if api_request():
            return jsonify({"comment": comment_document(comment)}), 201
        flash("Your comment has been added.", "success")
        return redirect(url_for("post_detail", post_id=post_id) + "#comments")

    @app.route("/comments/<comment_id>/delete", methods=["POST"])
    @login_required
    def delete_comment(comment_id):
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        if not ObjectId.is_valid(comment_id):
            abort(404)
        comment = g.db.comments.find_one({"_id": ObjectId(comment_id)})
        if comment is None:
            abort(404)
        if comment["author_id"] != g.user["_id"]:
            abort(403)
        g.db.comments.delete_one({"_id": comment["_id"], "author_id": g.user["_id"]})
        flash("Your comment has been deleted.", "success")
        return redirect(url_for("post_detail", post_id=str(comment["post_id"])) + "#comments")

    @app.route("/api/posts", methods=["GET", "POST"])
    def posts_api():
        if request.method == "GET":
            return jsonify({"posts": [post_document(post) for post in get_posts()]})
        if g.user is None:
            return api_error("Log in to create a post.", 401)
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        try:
            payload = json_payload()
        except ValueError as error:
            return api_error(str(error), 400)
        values, errors = post_form_values(payload)
        if errors:
            return jsonify({"errors": errors}), 400
        post = {
            **values,
            "category": "STORY",
            "author_id": g.user["_id"],
            "author_name": g.user["name"],
            "created_at": utc_now(),
            "updated_at": None,
            "is_demo": False,
        }
        result = g.db.posts.insert_one(post)
        post["_id"] = result.inserted_id
        return jsonify({"post": post_document(post)}), 201

    @app.route("/api/posts/<post_id>", methods=["GET", "PUT", "DELETE"])
    def post_api(post_id):
        post = find_post(post_id)
        if post is None:
            return api_error("Post not found.", 404)
        if request.method == "GET":
            return jsonify({"post": post_document(post)})
        if g.user is None:
            return api_error("Log in to change a post.", 401)
        if post.get("author_id") != g.user["_id"]:
            return api_error("You can only change your own posts.", 403)
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        if request.method == "PUT":
            try:
                payload = json_payload()
            except ValueError as error:
                return api_error(str(error), 400)
            values, errors = post_form_values(payload)
            if errors:
                return jsonify({"errors": errors}), 400
            g.db.posts.update_one(
                {"_id": post["_id"], "author_id": g.user["_id"]},
                {"$set": {**values, "updated_at": utc_now()}},
            )
            post.update(values)
            post["updated_at"] = utc_now()
            return jsonify({"post": post_document(post)})
        g.db.comments.delete_many({"post_id": post["_id"]})
        g.db.posts.delete_one({"_id": post["_id"], "author_id": g.user["_id"]})
        return jsonify({"message": "Post and its comments deleted."})

    @app.route("/api/posts/<post_id>/comments", methods=["GET"])
    def comments_api(post_id):
        post = find_post(post_id)
        if post is None:
            return api_error("Post not found.", 404)
        comments = list(g.db.comments.find({"post_id": post["_id"]}).sort("created_at", 1))
        return jsonify({"comments": [comment_document(comment) for comment in comments]})

    @app.route("/api/comments/<comment_id>", methods=["DELETE"])
    def comment_api(comment_id):
        if not ObjectId.is_valid(comment_id):
            return api_error("Comment not found.", 404)
        comment = g.db.comments.find_one({"_id": ObjectId(comment_id)})
        if comment is None:
            return api_error("Comment not found.", 404)
        if g.user is None:
            return api_error("Log in to delete a comment.", 401)
        if comment["author_id"] != g.user["_id"]:
            return api_error("You can only delete your own comments.", 403)
        csrf_error = require_csrf()
        if csrf_error:
            return csrf_error
        g.db.comments.delete_one({"_id": comment["_id"], "author_id": g.user["_id"]})
        return jsonify({"message": "Comment deleted."})

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def handle_http_error(error):
        if api_request():
            return api_error(error.description or error.name, error.code)
        return render_template("error.html", message=error.description or error.name), error.code

    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)

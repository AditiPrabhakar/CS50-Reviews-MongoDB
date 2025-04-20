from cs50 import SQL
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

mongo_uri = os.getenv("REVIEWS_DB")
client = MongoClient(mongo_uri)

db = client['cs50_reviews']
users = db['users']
reviews = db['reviews']
votes = db['votes']

# db = SQL("sqlite:///reviews.db")

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def index():
    return render_template('index.html')


@app.route("/homepage")
@login_required
def home():
    user_id = session["user_id"]

    try:
        user = users.find_one({"_id": ObjectId(user_id)})
    except Exception as e:
        print("Error fetching user", e)
        user = None

    if user: 
        profile_data = {
            "username": user.get("username", "Unknown"),
            "reviews_count": user.get("reviews_count", 0),
            "total_upvotes": user.get("total_upvotes", 0),
            "total_downvotes": user.get("total_downvotes", 0),
        }
    else:
        profile_data = {
            "username": "Unknown",
            "reviews_count": 0,
            "total_upvotes": 0,
            "total_downvotes": 0,
        }

    # Pass the profile data to the template
    return render_template('home.html', profile=profile_data)



@app.route("/postReview", methods=["GET", "POST"])
@login_required
def post_review():
    user = users.find_one({"_id": ObjectId(session.get('user_id'))})
    
    if request.method == "POST":
        review = request.form.get("review")

        if not review:
            return render_template("failure.html", error=400, message="Both fields are required.")


        if not user:
            return render_template("failure.html", error=400, message="Kindly enter your correct username.")

        username = user.get("username")
        reviews_count = user.get("reviews_count", 0)

        reviews.insert_one({
            "user_id": ObjectId(session.get('user_id')),
            "username": username,
            "review": review
        })

        users.update_one(
            {"_id": ObjectId(session.get('user_id'))},
            {"$set": {"reviews_count": reviews_count + 1}}
        )

        return render_template("post-review.html", success=f"Thank you for your review!", name=username)

    return render_template("post-review.html", name=username)


@app.route("/showReviews", methods=["GET", "POST"])
@login_required
def show_reviews():
    if request.method == "POST":
        # Get the form data
        review_id = request.form.get("review_id")
        vote_type = request.form.get("vote_type")

        # Get user_id from session
        user_id = session["user_id"]

        # Check if review exists
        review = db.execute("SELECT * FROM reviews WHERE id = ?", review_id)
        if not review:
            return redirect("/showReviews")

        review = review[0]  # Since db.execute returns a list

        # Check if user already voted on this review
        existing_vote = db.execute(
            "SELECT * FROM votes WHERE user_id = ? AND review_id = ?", user_id, review_id
        )

        if existing_vote:
            # If user already voted, handle changing vote
            if existing_vote[0]["vote_type"] != vote_type:
                # Update the votes based on new vote type
                if vote_type == "upvote":
                    # Update review upvotes and downvotes
                    db.execute(
                        "UPDATE reviews SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = ?", review_id)
                    # Update user total votes
                    db.execute(
                        "UPDATE users SET total_upvotes = total_upvotes + 1, total_downvotes = total_downvotes - 1 WHERE id = ?", review["user_id"])
                elif vote_type == "downvote":
                    db.execute(
                        "UPDATE reviews SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = ?", review_id)
                    db.execute(
                        "UPDATE users SET total_upvotes = total_upvotes - 1, total_downvotes = total_downvotes + 1 WHERE id = ?", review["user_id"])

                # Update the vote type in the votes table
                db.execute("UPDATE votes SET vote_type = ? WHERE user_id = ? AND review_id = ?",
                           vote_type, user_id, review_id)
        else:
            # If the user has not voted before, insert their vote
            if vote_type == "upvote":
                db.execute(
                    "UPDATE reviews SET upvotes = upvotes + 1 WHERE id = ?", review_id)
                db.execute(
                    "UPDATE users SET total_upvotes = total_upvotes + 1 WHERE id = ?", review["user_id"])
            elif vote_type == "downvote":
                db.execute(
                    "UPDATE reviews SET downvotes = downvotes + 1 WHERE id = ?", review_id)
                db.execute(
                    "UPDATE users SET total_downvotes = total_downvotes + 1 WHERE id = ?", review["user_id"])

            # Insert the new vote into the votes table
            db.execute("INSERT INTO votes (user_id, review_id, vote_type) VALUES (?, ?, ?)",
                       user_id, review_id, vote_type)

        return redirect("/showReviews")

    # For GET request, fetch all reviews along with the user's upvote/downvote status
    reviews = db.execute(
        "SELECT reviews.id, reviews.username, reviews.review, reviews.upvotes, reviews.downvotes, users.total_upvotes, users.total_downvotes, "
        "CASE WHEN EXISTS (SELECT 1 FROM votes WHERE user_id = ? AND review_id = reviews.id AND vote_type = 'upvote') THEN 1 ELSE 0 END AS voted_up, "
        "CASE WHEN EXISTS (SELECT 1 FROM votes WHERE user_id = ? AND review_id = reviews.id AND vote_type = 'downvote') THEN 1 ELSE 0 END AS voted_down "
        "FROM reviews JOIN users ON reviews.user_id = users.id",
        session["user_id"], session["user_id"]
    )

    return render_template("showreviews.html", reviews=reviews)



@app.route("/faqs")
@login_required
def faqs():
    return render_template("faqs.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return render_template("failure.html", message="must provide username", error=403)

        # Ensure password was submitted
        elif not password:
            return render_template("failure.html", message="must provide password", error=403)

        # Query database for username
        user = users.find_one({"username": username})

        if not user or not check_password_hash(user["hash"], password):
            return render_template('failure.html', message="invalid username/password", error=403)

        # store user session id
        session['user_id'] = str(user["_id"])

        # Redirect user to home page
        return redirect("/homepage")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def register(): 
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return render_template("failure.html", message="must provide username", error="400")

        elif not password:
            return render_template("failure.html", message="must provide password", error="400")

        elif password != confirmation:
            return render_template("failure.html", message="passwords don't match", error="400")

        existing_user = users.find_one({"username": username})
        if existing_user:
            return render_template("failure.html", message="username already exists", error="400")

        hashed_password = generate_password_hash(password)

        result = users.insert_one({
            "username": username,
            "hash": hashed_password,
            "reviews_count": 0,
            "total_upvotes": 0,
            "total_downvotes": 0,
        })

        session['user_id'] = str(result.inserted_id)

        return redirect("/homepage")
    else:
        return render_template("signup.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


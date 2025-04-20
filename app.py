# from cs50 import SQL
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

# votes.create_index([("user_id", 1), ("review_id", 1)], unique=True)

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
            "firstLetter": user.get("username")[0].capitalize(),
        }
    else:
        profile_data = {
            "username": "Unknown",
            "reviews_count": 0,
            "total_upvotes": 0,
            "total_downvotes": 0,
            "firstLetter": "?",
        }

    # Pass the profile data to the template
    return render_template('home.html', profile=profile_data)



@app.route("/postReview", methods=["GET", "POST"])
@login_required
def post_review():
    user = users.find_one({"_id": ObjectId(session.get('user_id'))})

    if not user:
        return render_template("failure.html", error=400, message="User not found.")
    
    username = user.get("username")
    reviews_count = user.get("reviews_count", 0)

    if request.method == "POST":
        review = request.form.get("review") 

        if not review:
            return render_template("failure.html", error=400, message="Both fields are required.")

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
    user_id = ObjectId(session['user_id'])
    all_reviews = list(reviews.find())
    user_votes = votes.find({"user_id": user_id})
    vote_map = {str(v['review_id']): v['vote_type'] for v in user_votes}

    reviews_list = []

    for review in all_reviews:
        user = users.find_one({"_id": review["user_id"]})
        review_id_str = str(review["_id"])

        reviews_list.append({
            "id": review_id_str,
            "username": review["username"],
            "review": review["review"],
            "upvotes": review.get("upvotes", 0),
            "downvotes": review.get("downvotes", 0),
            "total_upvotes": user.get("total_upvotes") if user else 0,
            "total_downvotes": user.get("total_downvotes") if user else 0,
            "upvoted": vote_map.get(review_id_str) == "upvote",
            "downvoted": vote_map.get(review_id_str) == "downvote",
        })

    return render_template('showreviews.html', reviews=reviews_list)

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    data = request.get_json()
    review_id = data.get("review_id")
    vote_type = data.get("vote_type")
    user_id = ObjectId(session['user_id'])

    try:
        review_obj_id = ObjectId(review_id)
    except:
        return jsonify({"success": False}), 400

    review = reviews.find_one({"_id": review_obj_id})
    if not review:
        return jsonify({"success": False}), 404

    existing_vote = votes.find_one({"user_id": user_id, "review_id": review_obj_id})
    author_id = review['user_id']

    if existing_vote:
        if existing_vote['vote_type'] == vote_type:
            # Clicking same button again = remove vote
            if vote_type == 'upvote':
                reviews.update_one({"_id": review_obj_id}, {"$inc": {"upvotes": -1}})
                users.update_one({"_id": author_id}, {"$inc": {"total_upvotes": -1}})
            else:
                reviews.update_one({"_id": review_obj_id}, {"$inc": {"downvotes": -1}})
                users.update_one({"_id": author_id}, {"$inc": {"total_downvotes": -1}})

            votes.delete_one({"_id": existing_vote['_id']})
            current_vote = None
        else:
            # Switching vote
            if vote_type == 'upvote':
                reviews.update_one({"_id": review_obj_id}, {"$inc": {"upvotes": 1, "downvotes": -1}})
                users.update_one({"_id": author_id}, {"$inc": {"total_upvotes": 1, "total_downvotes": -1}})
            else:
                reviews.update_one({"_id": review_obj_id}, {"$inc": {"upvotes": -1, "downvotes": 1}})
                users.update_one({"_id": author_id}, {"$inc": {"total_upvotes": -1, "total_downvotes": 1}})

            votes.update_one({"_id": existing_vote['_id']}, {"$set": {"vote_type": vote_type}})
            current_vote = vote_type
    else:
        # New vote
        if vote_type == "upvote":
            reviews.update_one({"_id": review_obj_id}, {"$inc": {"upvotes": 1}})
            users.update_one({"_id": author_id}, {"$inc": {"total_upvotes": 1}})
        else:
            reviews.update_one({"_id": review_obj_id}, {"$inc": {"downvotes": 1}})
            users.update_one({"_id": author_id}, {"$inc": {"total_downvotes": 1}})

        votes.insert_one({
            "user_id": user_id,
            "review_id": review_obj_id,
            "vote_type": vote_type,
        })
        current_vote = vote_type

    updated_review = reviews.find_one({"_id": review_obj_id})

    return jsonify({
        "success": True,
        "upvotes": updated_review.get("upvotes", 0),
        "downvotes": updated_review.get("downvotes", 0),
        "current_vote": current_vote  # can be "upvote", "downvote", or None
    })

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

if __name__ == "__main__":
    app.run(debug=True)
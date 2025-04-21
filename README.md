# 📚 CS50 Reviews 

A full-stack web application built using **Flask** and **MongoDB** that allows users to register, log in, and post reviews related to the CS50 course. The platform offers a dynamic voting system, user statistics, and strong validation features. All passwords are securely **hashed before being stored**, ensuring safe authentication.

---

## 🚀 Features

### 🔐 User Authentication
- Secure login and signup functionality.
- Passwords are hashed before storing in the database.
- Sessions and cookies manage user login states.
- Robust validation handles edge cases and ensures clean user input.

### 📝 Create Reviews
- Users can write and submit reviews about CS50.
- User-friendly interface encourages thoughtful content creation.

### 👀 View Reviews
- Browse all user-submitted reviews.
- Each review displays the number of upvotes and downvotes.

### 👍👎 Upvote/Downvote System
- Users can upvote or downvote any review.
- The system is dynamic and responsive for real-time interactions.

### 🧑‍💼 User Dashboard
- Users can view their profile and review-related stats.
- Displays number of reviews posted, total upvotes, and total downvotes received.

### ❓ FAQs Page
- Includes a dedicated page inspired by the official Harvard CS50 FAQ.
- Direct links to CS50x lectures and related course content for quick access.

### ✅ Validation
- Strong input validation across all forms (login, signup, review submission).
- Prevents edge case issues and maintains data integrity.

---

## 🧠 Tech Stack

- **Backend:** Flask, Python
- **Frontend:** HTML, CSS, Bootstrap
- **Database:** MongoDB (via Flask-PyMongo)
- **Security:** Password hashing with `werkzeug.security`

import os
from datetime import datetime
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
from aiSolver import getLLManswer

from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)


app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db_url = os.getenv("DATABASE_URL", "sqlite:///data/ProblemList.db")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, echo=False, future=True)
db = scoped_session(sessionmaker(bind=engine))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("login.html", error="Please provide a username")
        if not request.form.get("password"):
            return render_template("login.html", error="Please provide a password")

        rows = db.execute(
            text("SELECT * FROM users WHERE username = :username"),
            {"username": request.form.get("username")}
        ).mappings().all()

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("login.html", error="Invalid Username or Password")

        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        if not name:
            return render_template("register.html", error="Please provide a username")
        if name.isdigit():
            return render_template("register.html", error="Invalid characters in username")
        if not password or not confirm_password:
            return render_template("register.html", error="Please provide a password")
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match!")

        existing = db.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": name}
        ).first()

        if existing:
            return render_template("register.html", error="Username already taken")

        pw_hash = generate_password_hash(password)
        db.execute(
            text("INSERT INTO users (username, hash) VALUES (:username, :hash)"),
            {"username": name, "hash": pw_hash}
        )
        db.commit()

        return redirect("/login")

    return render_template("register.html")



@app.route("/")
def index():
    if "user_id" in session:
        rows = db.execute(
            text("SELECT username FROM users WHERE id = :id"),
            {"id": session["user_id"]}
        ).mappings().all()
        if not rows:
            return redirect("/")
        return render_template("index.html", name=rows[0]["username"])
    else:
        return render_template("home.html")


@app.route("/solve/<int:problem_id>", methods=["POST"])
@login_required
def mark_solved(problem_id):
    user_id = session["user_id"]

    db.execute(
        text("INSERT INTO user_solved (user_id, problem_id) VALUES (:uid, :pid) ON CONFLICT DO NOTHING"),
        {"uid": user_id, "pid": problem_id}
    )
    db.commit()
    return redirect("/problems")


@app.route("/unsolve/<int:problem_id>", methods=["POST"])
@login_required
def mark_unsolved(problem_id):
    user_id = session["user_id"]

    db.execute(
        text("DELETE FROM user_solved WHERE user_id = :uid AND problem_id = :pid"),
        {"uid": user_id, "pid": problem_id}
    )
    db.commit()
    return redirect("/problems")


@app.route("/problems", methods=["GET", "POST"])
@login_required
def showProblem():
    category = request.args.get("category")
    difficulty = request.args.get("difficulty")
    search = request.args.get("search")

    query = """
        SELECT p.id,
               p.name,
               p.category,
               p.difficulty,
               CASE WHEN us.problem_id IS NOT NULL THEN 1 ELSE 0 END AS manually_solved,
               CASE WHEN s.problem_id IS NOT NULL THEN 1 ELSE 0 END  AS ai_solved
        FROM problems p
                 LEFT JOIN user_solved us
                           ON p.id = us.problem_id AND us.user_id = :uid
                 LEFT JOIN solutions s
                           ON p.id = s.problem_id AND s.user_id = :uid2
        WHERE 1 = 1
    """
    params = {"uid": session["user_id"], "uid2": session["user_id"]}

    if category and category != "all":
        query += " AND p.category = :cat"
        params["cat"] = category

    if difficulty and difficulty != "all":
        query += " AND p.difficulty = :diff"
        params["diff"] = difficulty

    if search:
        query += " AND p.name LIKE :search"
        params["search"] = f"%{search}%"

    problems = db.execute(text(query), params).mappings().all()
    categories = db.execute(text("SELECT DISTINCT category FROM problems")).scalars().all()
    difficulties = db.execute(text("SELECT DISTINCT difficulty FROM problems")).scalars().all()
    user = db.execute(
        text("SELECT username FROM users WHERE id = :id"),
        {"id": session["user_id"]}
    ).mappings().first()

    return render_template("problems.html",
                           problems=problems,
                           categories=categories,
                           difficulties=difficulties,
                           selected_category=category,
                           selected_difficulty=difficulty,
                           search=search,
                           name=user["username"])


@app.route("/progress")
@login_required
def progress():
    user_id = session["user_id"]
    total = db.execute(text("SELECT COUNT(*) FROM problems")).scalar()
    solved = db.execute(
        text("SELECT COUNT(*) FROM user_solved WHERE user_id = :uid"),
        {"uid": user_id}
    ).scalar()
    username = db.execute(
        text("SELECT username FROM users WHERE id = :id"),
        {"id": user_id}
    ).scalar()

    return render_template("progress.html", solved=solved, total=total, name=username)


@app.route("/solution/<int:problem_id>", methods=["GET", "POST"])
@login_required
def solution(problem_id):
    user_id = session["user_id"]

    problem = db.execute(
        text("SELECT id, name, category, difficulty FROM problems WHERE id = :pid"),
        {"pid": problem_id}
    ).mappings().first()

    if not problem:
        return render_template("problems.html", error="Problem Not Found")

    user_solution = db.execute(
        text("SELECT solution_text FROM solutions WHERE problem_id = :pid AND user_id = :uid"),
        {"pid": problem_id, "uid": user_id}
    ).mappings().first()

    if user_solution:
        return render_template("solution.html",
                               problem=problem,
                               llm_answer=user_solution["solution_text"],
                               name=db.execute(text("SELECT username FROM users WHERE id = :id"),
                                               {"id": user_id}).scalar())

    existing_solution = db.execute(
        text("SELECT solution FROM problems WHERE id = :pid"),
        {"pid": problem_id}
    ).mappings().first()

    if existing_solution and existing_solution["solution"]:
        llm_answer = existing_solution["solution"]
        db.execute(
            text("INSERT INTO solutions (user_id, problem_id, solution_text) VALUES (:uid, :pid, :ans)"),
            {"uid": user_id, "pid": problem_id, "ans": llm_answer}
        )
        db.commit()
        return render_template("solution.html",
                               problem=problem,
                               llm_answer=llm_answer,
                               name=db.execute(text("SELECT username FROM users WHERE id = :id"),
                                               {"id": user_id}).scalar())

    today = datetime.now().strftime("%Y-%m-%d")
    usage = db.execute(
        text("SELECT count FROM usage_log WHERE user_id = :uid AND date = :d"),
        {"uid": user_id, "d": today}
    ).mappings().first()

    if usage and usage["count"] >= 5:
        return render_template("solution.html",
                               problem=problem,
                               error="Daily limit of 5 solutions reached. Try again tomorrow.",
                               name=db.execute(text("SELECT username FROM users WHERE id = :id"),
                                               {"id": user_id}).scalar())

    llm_answer = getLLManswer(problem_id)
    if not llm_answer:
        return render_template("solution.html",
                               problem=problem,
                               error="Solution not available at the moment. Please try again later.",
                               name=db.execute(text("SELECT username FROM users WHERE id = :id"),
                                               {"id": user_id}).scalar())

    db.execute(
        text("INSERT INTO solutions (user_id, problem_id, solution_text) VALUES (:uid, :pid, :ans)"),
        {"uid": user_id, "pid": problem_id, "ans": llm_answer}
    )
    db.execute(
        text("UPDATE problems SET solution = :ans WHERE id = :pid"),
        {"ans": llm_answer, "pid": problem_id}
    )

    if usage:
        db.execute(
            text("UPDATE usage_log SET count = count + 1 WHERE user_id = :uid AND date = :d"),
            {"uid": user_id, "d": today}
        )
    else:
        db.execute(
            text("INSERT INTO usage_log (user_id, date, count) VALUES (:uid, :d, 1)"),
            {"uid": user_id, "d": today}
        )
    db.commit()

    return render_template("solution.html",
                           problem=problem,
                           llm_answer=llm_answer,
                           name=db.execute(text("SELECT username FROM users WHERE id = :id"),
                                           {"id": user_id}).scalar())


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)

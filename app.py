import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import login_required
from aiSolver import getLLManswer

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL("sqlite:///data/ProblemList.db")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method =="POST":
        if not request.form.get("username"):
            return render_template("login.html", error="Please provide a username")
        if not request.form.get("password"):
            return render_template("login.html", error="Please provide a password")
        rows=db.execute("SELECT * FROM users WHERE username = ?",request.form.get("username"))

        if len(rows)!=1 or not check_password_hash(rows[0]["hash"],request.form.get("password")):

            return render_template("login.html", error="Invalid Username or Password")
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/register",methods=["GET","POST"])
def register():
    import sqlite3
    if request.method == "POST":
        name = request.form.get("username")
        if not name:
            return render_template("register.html", error="Please provide a username")
        if(request.form.get("username").isdigit()):
            return render_template("register.html",error="Invalid characters in username")

        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")
        if not password or not confirm_password:
           return render_template("register.html", error="Please provide a password")
        if password != confirm_password:
           return render_template("register.html", error="Passwords do not match!")

        pw_hash = generate_password_hash(password)

        try:
             db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", name, pw_hash)
        except ValueError:
            return render_template("register.html", error="Username already taken")
        return redirect("/login")
    else:
        return render_template("register.html")

@app.route("/")
def index():
    if "user_id" in session:
        rows=db.execute("SELECT username FROM users WHERE id = ?",session["user_id"])
        if not rows:
            return redirect("/")
        name=rows[0]["username"]
        return render_template("index.html",name=name)
    else:
        return render_template("home.html")

@app.route("/solve/<int:problem_id>", methods=["POST"])
@login_required
def mark_solved(problem_id):
    user_id = session["user_id"]

    db.execute("""
        INSERT OR IGNORE INTO user_solved (user_id, problem_id)
        VALUES (?, ?)
    """, user_id, problem_id)

    return redirect("/problems")

@app.route("/unsolve/<int:problem_id>", methods=["POST"])
@login_required
def mark_unsolved(problem_id):
    user_id = session["user_id"]

    db.execute("""
        DELETE FROM user_solved
        WHERE user_id = ? AND problem_id = ?
    """, user_id, problem_id)

    return redirect("/problems")

@app.route("/problems", methods=["GET", "POST"])
@login_required
def showProblem():
    category = request.args.get("category")
    difficulty = request.args.get("difficulty")
    search = request.args.get("search")

    query = """
            SELECT p.id, \
                   p.name, \
                   p.category, \
                   p.difficulty,
                   CASE WHEN us.problem_id IS NOT NULL THEN 1 ELSE 0 END AS manually_solved,
                   CASE WHEN s.problem_id IS NOT NULL THEN 1 ELSE 0 END  AS ai_solved
            FROM problems p
                     LEFT JOIN user_solved us
                               ON p.id = us.problem_id AND us.user_id = ?
                     LEFT JOIN solutions s
                               ON p.id = s.problem_id AND s.user_id = ?
            WHERE 1 = 1 \
            """
    params = [session["user_id"], session["user_id"]]

    if category and category != "all":
        query += " AND p.category = ?"
        params.append(category)

    if difficulty and difficulty != "all":
        query += " AND p.difficulty = ?"
        params.append(difficulty)

    if search:
        query += " AND p.name LIKE ?"
        params.append(f"%{search}%")

    problems = db.execute(query, *params)

    categories = db.execute("SELECT DISTINCT category FROM problems")
    difficulties = db.execute("SELECT DISTINCT difficulty FROM problems")
    user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    name = user[0]["username"]

    return render_template("problems.html",
                           problems=problems,
                           categories=[c["category"] for c in categories],
                           difficulties=[d["difficulty"] for d in difficulties],
                           selected_category=category,
                           selected_difficulty=difficulty,
                           search=search,
                           name=name)

@app.route("/progress")
@login_required
def progress():
    user_id= session["user_id"]
    total= db.execute("SELECT COUNT(*) as count FROM problems")[0]["count"]
    solved= db.execute("SELECT COUNT(*) as count FROM user_solved WHERE user_id = ?",user_id)[0]["count"]
    return render_template("progress.html",solved=solved,total=total,name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"])

@app.route("/solution/<int:problem_id>", methods=["GET", "POST"])
@login_required
def solution(problem_id):
    user_id = session["user_id"]

    problem = db.execute("SELECT id, name, category, difficulty FROM problems WHERE id = ?",
        problem_id
    )
    if not problem:
        return render_template("problems.html", error="Problem Not Found")
    problem = problem[0]

    user_solution=db.execute( "SELECT solution_text FROM solutions WHERE problem_id = ? AND user_id = ?",
        problem_id, user_id
    )
    if user_solution:
        llm_answer = user_solution[0]["solution_text"]
        return render_template("solution.html",
                               problem=problem,
                               llm_answer=llm_answer,
                               name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"])

    existing_solution = db.execute("SELECT Solution FROM problems WHERE id = ?",
        problem_id
    )

    if existing_solution:
        llm_answer = existing_solution[0]["Solution"]
        if llm_answer:
            db.execute(
                "INSERT INTO solutions (user_id, problem_id, solution_text) VALUES (?, ?, ?)",
                user_id, problem_id, llm_answer
            )
            return render_template("solution.html",
                                   problem=problem,
                                   llm_answer=llm_answer,
                                   name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"])

    today = datetime.now().strftime("%Y-%m-%d")
    usage = db.execute("SELECT count FROM usage_log WHERE user_id = ? AND date = ?",
        user_id, today
    )

    if usage and usage[0]["count"] >= 5:
        return render_template("solution.html",
                               problem=problem,
                               error="You have reached your daily limit of 5 solutions. Please try again tomorrow.",
                               name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"])


    llm_answer = getLLManswer(problem_id)

    if not llm_answer:
        return render_template("solution.html",
            problem=problem,
            error="Solution not available at the moment. Please try again later.",
            name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"]
        )
    #
    #
    db.execute("INSERT INTO solutions (user_id, problem_id, solution_text) VALUES (?, ?, ?)",
        user_id, problem_id, llm_answer
    )

    db.execute("UPDATE problems SET solution = ? WHERE id = ?",
        llm_answer, problem_id
    )


    if usage:
        db.execute("UPDATE usage_log SET count = count + 1 WHERE user_id = ? AND date = ?",
            user_id, today
        )
    else:
        db.execute("INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, 1)",
            user_id, today
        )

    return render_template("solution.html",
                           problem=problem,
                           llm_answer=llm_answer,
                           name=db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")



if __name__=="__main__":
    app.run(debug = True)
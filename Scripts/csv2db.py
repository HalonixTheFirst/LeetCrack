import csv
import sqlite3

dbPath="../data/ProblemList.db"
csvPath="../data/problems.csv"

con=sqlite3.connect(dbPath)
cur=con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS problems(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            topics TEXT,
            difficulty TEXT,
            category TEXT,
            llmprompt TEXT,
            solution TEXT
               )""")

cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL
                )""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS user_solved (
        user_id INTEGER,
        problem_id INTEGER,
        solved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, problem_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (problem_id) REFERENCES problems(id)
    )
""")

cur.execute("""CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    UNIQUE(user_id, date)
);
""")

cur.execute("""CREATE TABLE IF NOT EXISTS solutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    solution_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (problem_id) REFERENCES problems(id)
);
""")

with open(csvPath,newline='',encoding='utf-8') as f:
    reader=csv.DictReader(f)
    for row in reader:
        cur.execute("""
            INSERT INTO problems
            (id,name,topics,difficulty,category,llmprompt)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET 
            name =excluded.name ,
            topics = excluded.topics ,
            difficulty = excluded.difficulty ,
            category = excluded.category ,
            llmprompt = excluded.llmprompt""",(
            row["ID"],
            row["Problem Name"],
            row["Topics"],
            row["Difficulty"],
            row["Category"],
            row["LLM Prompt"]
        ))
con.commit()
con.close()
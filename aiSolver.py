from cs50 import SQL

db = SQL("sqlite:///data/ProblemList.db")

def getLLManswer(problem_id):
    promptList=db.execute("SELECT llmprompt FROM problems WHERE id IS ?",problem_id)
    prompt=promptList[0]["llmprompt"]
    print(prompt)

def main():
    getLLManswer(2)

main()
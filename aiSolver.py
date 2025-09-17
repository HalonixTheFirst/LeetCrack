from google import generativeai
from cs50 import SQL
import os
from llama_cpp import Llama


localLlamaPath="./models/codellama-7b-instruct-hf-q4_k_m.gguf"
llm=None
if os.path.exists(localLlamaPath):
    print("Local model found....")
    try:
        llm=Llama(model_path=localLlamaPath,
        # n_gpu_layers=-1, # Uncomment to use GPU acceleration
        # seed=1337, # Uncomment to set a specific seed
        # n_ctx=2048, # Uncomment to increase the context window
        #     n_threads=4,
        )
    except Exception :
        print("Loading Failed")
with open("env/gemini_api_key.txt", "r") as f:
    GEMINI_API_KEY = f.read().strip()
generativeai.configure(api_key=GEMINI_API_KEY)


db = SQL("sqlite:///data/ProblemList.db")

def getLLManswer(problem_id):
    promptList=db.execute("SELECT llmprompt FROM problems WHERE id = ?",problem_id)
    prompt=promptList[0]["llmprompt"]
    prompt=prompt+" (Write in plain text and give C++ and Python Codes)"
    if llm:
        output=llm( f"[INST] {prompt} [/INST]",
        max_tokens=512,  # safer than 2048 for Flask
        # stop=["</s>"],
        )
        answer=output["choices"][0]["text"].strip()
        # return(prompt)
        # print(answer)
        return answer
    gemini_model = generativeai.GenerativeModel("gemini-2.5-flash")
    response = gemini_model.generate_content(
        prompt
    )
    return (response.text)

# def main():
#     print(getLLManswer(2))
#
# main()


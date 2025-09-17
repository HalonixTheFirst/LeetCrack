from google import generativeai
from cs50 import SQL
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
generativeai.configure(api_key=GEMINI_API_KEY)

db = SQL("sqlite:///data/ProblemList.db")

def getLLManswer(problem_id):
    promptList = db.execute("SELECT llmprompt FROM problems WHERE id = ?", problem_id)
    prompt = promptList[0]["llmprompt"]
    prompt += " (Write in plain text and give C++ and Python Codes)"

    # Try to use LLaMA if available, but ignore errors
    try:
        from llama_cpp import Llama
        localLlamaPath = "./models/codellama-7b-instruct-hf-q4_k_m.gguf"
        if os.path.exists(localLlamaPath):
            llm = Llama(model_path=localLlamaPath)
            output = llm(f"[INST] {prompt} [/INST]", max_tokens=512)
            answer = output["choices"][0]["text"].strip()
            return answer
    except Exception:
        # If LLaMA fails, fall back to Gemini
        pass

    # Always use Gemini API
    gemini_model = generativeai.GenerativeModel("gemini-2.5-flash")
    response = gemini_model.generate_content(prompt)
    return response.text

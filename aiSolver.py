from google import generativeai
from sqlalchemy import create_engine, text
import os
try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


localLlamaPath = "./models/codellama-7b-instruct-hf-q4_k_m.gguf"
llm = None
if Llama and os.path.exists(localLlamaPath):
    print("Local model found....")
    try:
        llm = Llama(
            model_path=localLlamaPath,
            # n_gpu_layers=-1, # Uncomment to use GPU acceleration
            # seed=1337,
            # n_ctx=2048,
            # n_threads=4,
        )
    except Exception:
        print("Loading Failed")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
generativeai.configure(api_key=GEMINI_API_KEY)

db_url = os.getenv("DATABASE_URL", "sqlite:///data/ProblemList.db")
connect_args = {"sslmode": "require"} if db_url.startswith("postgresql") else {}
engine = create_engine(db_url, connect_args=connect_args, future=True)

def getLLManswer(problem_id):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT llmprompt FROM problems WHERE id = :id"),
            {"id": problem_id}
        )
        prompt = result.scalar_one_or_none()

    if not prompt:
        return "No prompt found for this problem."

    prompt = prompt + " (Write in plain text and give C++ and Python Codes)"

    if llm:
        output = llm(
            f"[INST] {prompt} [/INST]",
            max_tokens=512,
            # stop=["</s>"],
        )
        answer = output["choices"][0]["text"].strip()
        return answer

    gemini_model = generativeai.GenerativeModel("gemini-2.5-flash")
    response = gemini_model.generate_content(prompt)
    return response.text

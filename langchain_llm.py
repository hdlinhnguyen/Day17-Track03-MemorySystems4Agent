import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# --- Config ---
LLM_KEY   =""
LLM_URL   = "https://ai-gateway.antco.ai/v1"
LLM_MODEL = "gemini-3-flash"

# --- Load LLM ---
# Use custom http_client to avoid gateway blocking the default OpenAI SDK User-Agent
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=LLM_KEY,
    base_url=LLM_URL,
    http_client=httpx.Client(headers={"User-Agent": "python-httpx/0.27.0"}),
)

# --- Run ---
if __name__ == "__main__":
    prompt = "Write a short 3-sentence paragraph about AI."

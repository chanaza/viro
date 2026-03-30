import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.google.chat import ChatGoogle

from src.models import BranchList
from src.task import build_task
from src.output import extract_branch_list, save_outputs
from src.config import LLM_MAX_OUTPUT_TOKENS

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SUBJECT = os.getenv("SUBJECT", "שופרסל")

llm = ChatGoogle(
    model=os.getenv("GEMINI_MODEL"),
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("LLM_LOCATION"),
    vertexai=True,
    max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
    thinking_budget=0,
)

agent = Agent(
    task=build_task(SUBJECT),
    llm=llm,
    output_model_schema=BranchList,
    file_system_path=OUTPUT_DIR,
)

result = asyncio.run(agent.run())

print(result.final_result() or "")

branch_list = extract_branch_list(result)
save_outputs(result, branch_list, SUBJECT, OUTPUT_DIR)

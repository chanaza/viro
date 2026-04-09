import os
from dotenv import load_dotenv

load_dotenv()

from src.branches.agent import BranchesResearchAgent

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
SUBJECT    = os.getenv("SUBJECT", "שופרסל")

agent  = BranchesResearchAgent(SUBJECT, OUTPUT_DIR)
result = agent.run()
agent.print_log(result)

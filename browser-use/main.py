import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.google.chat import ChatGoogle

load_dotenv()

# LLM שמנהל את האייג'נט דרך Vertex AI (ללא API key, מבוסס על gcloud auth)
llm = ChatGoogle(
    model=os.getenv("GEMINI_MODEL"),
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
    vertexai=True,
)

# יצירת agent עם scope של browser בלבד
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHAIN = os.getenv("CHAIN", "שופרסל")

agent = Agent(
    task=f"""
    מצא את כל הסניפים של רשת {CHAIN} בישראל.
    החזר רשימה מסודרת עם:
    - שם סניף
    - כתובת
    - עיר
    השתמש רק במידע מהאינטרנט.
    שמור את התוצאות לקובץ branches.csv בתיקייה הנוכחית.
    """,
    llm=llm,
    file_system_path=OUTPUT_DIR,
)

result = asyncio.run(agent.run())

print(result.final_result())
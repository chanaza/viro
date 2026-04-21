# researcher-agent — הקשר פרויקט

## מה הפרויקט עושה
מציאת כל סניפי רשת קמעונאית ישראלית לפי שם רשת, שמירה ל-CSV.
נגיש דרך ממשק צ'אט (Viro) או דרך CLI.

## Stack
- Python, browser-use, Pydantic, python-dotenv, pyyaml, FastAPI, uvicorn
- LLM: Gemini דרך Vertex AI (ברירת מחדל), תמיכה גם ב-Groq, OpenAI, Anthropic
- Google Cloud Project: ראה `.env` — מיקום הפרויקט: `me-west1`
- מיקום LLM מועדף: `europe-west3` או `europe-west4` (עדיפות, לא אילוץ קשיח)
- venv: `.venv/` בשורש הפרויקט

## מבנה קבצים
```
researcher-agent/
├── config.py               ← קבועי סוכן: MAX_FAILURES, MAX_ACTIONS_PER_STEP, COLLECT_ALL
├── requirements.txt        ← תלויות מאוחדות לכל הפרויקט
├── run_app.py              ← מפעיל uvicorn + פותח Edge (ל-Viro בלבד)
├── .venv/                  ← venv יחיד לכל הפרויקט
│
├── core/                   ← קוד shared, ללא תלות ב-app או agent_service
│   ├── llm.py              ← LLM factory: create_llm_for(model, settings), get_models()
│   ├── models.py           ← Skill, SkillMatch, SkillPreset, SkillOutputModel, SourceLog
│   ├── profiles.py         ← browser profile detection, build_browser_profile()
│   ├── prompts.py          ← ROUTER_PROMPT, KEEP_BROWSER_PROMPT, JUDGE_PROMPT, RESUME_BRIEFING_*, COLLECT_ALL_INSTRUCTION, STOP_FIRST_INSTRUCTION
│   ├── agent_setup.py      ← load_system_extension(), load_sensitive_data()
│   └── config/
│       ├── models.json     ← רשימת מודלים זמינים עם provider
│       ├── system_extension.md   ← system prompt extension לסוכן
│       └── sensitive_data.json.example
│
├── agent_service/          ← שכבת עסקית: browser-use + orchestration
│   ├── service.py          ← AgentService: thin wrapper סביב browser-use Agent
│   ├── orchestrator.py     ← AgentOrchestrator: routing, skills, security, שמירה; בונה system_ext פנימית
│   ├── skill_registry.py   ← SkillRegistry: load, find, build_prompt, output_schema, resolve_presets
│   ├── security_judge.py   ← SecurityJudge, Verdict — מדיניות ביטחון בריצה
│   ├── session_output/     ← שמירת תוצאות
│   │   ├── artifacts_saver.py   ← ArtifactsSaver: CSV, history, URLs
│   │   └── final_response_saver.py  ← FinalResponseSaver: answer.md, log.md
│   └── errors.py           ← friendly_error()
│
├── skills/                 ← תוכן בלבד: הגדרות SKILL.md + output schemas + context
│   ├── research-navigation/SKILL.md  ← base skill: כללי ניווט גנריים
│   └── branches/
│       ├── SKILL.md        ← research skill: מחקר סניפים (5 מקורות)
│       ├── config.py       ← TRUSTED_AGGREGATORS, BUSINESS_PROFILE_PLATFORMS
│       ├── output_schema.py ← Branch, BranchList (extends SkillOutputModel מ-core)
│       └── render_context.py ← get_context(params) → platforms_block, aggregators_block
│
├── app/                    ← שכבת UI בלבד (Viro)
│   ├── server.py           ← FastAPI: SSE, /start, /pause, /resume, /stop, /send
│   ├── chat_agent.py       ← ChatBrowserAgent: thin UI adapter מעל AgentOrchestrator
│   ├── llm_config.py       ← create_llm(), create_orchestrator_llm(), create_judge_llm()
│   ├── user_config.py      ← UserSettings, load_settings(), SESSIONS_DIR
│   └── static/index.html   ← Chat UI (vanilla JS + SSE)
│
├── cli/                    ← הרצת CLI ישירה (ללא UI)
│   ├── main.py             ← entry point: קורא מ-.env, ללא תלות ב-app/
│   ├── .env                ← SUBJECT, SKILLS, TASK, COLLECT_ALL, BROWSER_PROFILE, ...
│   └── output/             ← תוצאות CLI (לא ב-git)
│
├── installer/              ← Inno Setup installer לאפליקציית Viro
│   ├── viro.iss
│   ├── setup_install.ps1
│   └── launch.vbs
│
└── legacy/                 ← קוד ישן — לעיון בלבד
    └── src/
        ├── core/           ← ResearchAgent ABC (הוחלף ע"י agent_service/)
        └── branches/       ← BranchesResearchAgent (הוחלף ע"י skills/branches/)
```

## הרצה — CLI
```bash
.venv/Scripts/python.exe cli/main.py
```
משתני `cli/.env` רלוונטיים:
- `SUBJECT` — שם הרשת (ברירת מחדל: שופרסל)
- `SKILLS` — שמות skills מופרדים בפסיקים (ברירת מחדל: branches)
- `TASK` — ניסוח המשימה; `{subject}` מוחלף אוטומטית
- `COLLECT_ALL` — `true` לאיסוף מכל המקורות, `false` לעצור אחרי הצלחה ראשונה

## הרצה — Viro (UI)
```bash
.venv/Scripts/python.exe run_app.py
```

## ארכיטקטורה — שכבות
```
core/              ← shared utilities (LLM, profiles, prompts, policy) — ללא תלויות אפליקציה
skills/            ← הגדרות skill, output schemas, context renderers
agent_service/     ← לוגיקה עסקית: browser-use Agent + orchestration
app/               ← UI layer: ChatBrowserAgent, FastAPI server, settings
cli/               ← CLI consumer
```

**זרימת אחריות:**
- `AgentService` — wraps browser-use Agent בלבד; מוציא events: `step`, `done`, `stopped`, `error`
- `AgentOrchestrator` — routing (BROWSE/ANSWER), skill resolution, security judge, שמירת final response; בונה system_ext פנימית (`_build_system_ext`); מוציא events: `skill_matched`, `step`, `security_warning`, `security_stop`, `security_approved`, `security_rejected`, `done`, `stopped`, `error`
- `ChatBrowserAgent` — UI adapter: conversation history, relay events ל-SSE queue

**preset_skills בסטארט, לא ב-init:**
- `AgentOrchestrator.__init__` = session-level (LLM, browser, policy)
- `AgentOrchestrator.start(preset_skills=...)` = per-run; כשמסופק — מדלג על routing LLM call

**שלושה סוגי output (לפי פרמטרי dir):**
- `agent_log_dir` — `conversation.json` (browser-use LLM log) — תמיד
- `full_results_dir` — CSV, actions, URLs — CLI תמיד; UI לפי `save_full_results` ב-settings
- `final_response_dir` — `answer.md`, `steps.md` — כל caller שרוצה human-readable summary

## הגדרות LLM
- `thinking_budget=0` — חשיבה מורחבת מבוטלת (מנעה timeout של 75 שניות)
- `max_output_tokens=65536`

## אאוטפוט (skill branches)
קבצים עם prefix `{timestamp}`:
- `_result.csv` — רשימת סניפים
- `_sources.csv` — לוג מקורות (visited/found/count/notes)
- `_actions.csv` — היסטוריית פעולות מהסוכן
- `_urls.txt` — URLs ייחודיים
- `_answer.md` — תשובה סופית (final_response_dir בלבד)
- `_steps.md` — לוג steps (final_response_dir בלבד)

## סדר מקורות (branches)
1. האתר הרשמי — גוגל → תוצאה ראשונה אם שייכת לרשת
2. שקיפות מחירים — גוגל → אתר ייעודי / פורטל ממשלתי
3. פלטפורמות עסקיות: פייסבוק, אינסטגרם
4. אגרגטורים: easy.co.il, maps.google.com, d.co.il, cheapersal.co.il, pricez.co.il
5. חיפוש גוגל — עמוד ראשון בלבד

## בעיות ידועות / אתגרים פתוחים
- פייסבוק/אינסטגרם חסומים ע"י אתרוג בסביבת הבדיקה
- **maps.google.com**: extract לא עקבי — לפעמים מצליח (7-10 תוצאות), לפעמים נכשל לגמרי
- **d.co.il**: extract נכשל לעיתים גם כשיש תוצאות — הסוכן נכנס ללולאת find_elements/evaluate
- **post-processing**: לא מומש — עסקים עם שם דומה נכנסים לתוצאות מ-d.co.il

## הוראות פיתוח וולידציה

### לפני כל שינוי קוד — בדיקות חובה

**1. בדיקת סינטקס:**
```bash
python -m py_compile <file>
```
רק בודק סינטקס בסיסי, לא טייפים!

**2. בדיקת טייפים:**
- השתמש ב־**Pyright/Pylance** ב־VS Code (מוגדר עם `pyrightconfig.json`)
- וודא שאין שגיאות אדומות לפני המשך
- בדוק במיוחד TypedDict וטייפים מורכבים
- אם שינית imports / העברת קוד בין מודולים / יצרת קובץ חדש:
  - בדוק **בפועל את הקובץ הערוך ב-IDE** שאין עליו `unknown import symbol`, `reportMissingImports`, `reportAttributeAccessIssue`
  - אל תסתפק ב־`py_compile` או בייבוא ריצה בלבד — הם לא תופסים את כל שגיאות Pylance

**3. בדיקת ייבוא:**
```bash
python -c "import <module>"
```
מוודא שאין שגיאות ייבוא בסיסיות.

**4. בדיקת אינטגרציה:**
- הרץ את האפליקציה: `python run_app.py`
- הרץ CLI: `SUBJECT="טסט" python cli/main.py`
- וודא שפעולות בסיסיות עובדות

### כללי ארכיטקטורה

**חלוקת שכבות קשיחה:**
- `core/` = קוד שיתופי, utilities, ללא תלות באפליקציה ספציפית
- `app/` = קוד אפליקציה, קונפיגורציה, UI, תלויות ספציפיות
- `agent_service/` = לוגיקת סוכן, שכבה עסקית

### טייפים וולידציה

**השתמש ב־TypedDict, לא dict רחב:**
```python
# ❌ רע - מאפשר הכל
ProfileDict = dict[str, str | None]

# ✅ טוב - מדויק ותופס שגיאות
class ProfileDict(TypedDict):
    id: str
    label: str
    user_data_dir: str
    profile_directory: str  # חייב להיות str
    browser: str
    executable: str | None
```

**בדוק התאמה ל־APIs חיצוניים:**
- השווה טייפים עם BrowserProfile, Pydantic models וכו'
- וודא שהטייפים תואמים את הציפיות של הספריות

### תהליך עבודה

**לפני commit/push:**
1. ✅ Pyright/Pylance נקי משגיאות
2. ✅ כל המודולים נטענים ללא שגיאה
3. ✅ אפליקציה ו־CLI רצים ללא קריסה
4. ✅ שינויים לא מפרים ארכיטקטורה
5. ✅ אין שגיאות אדומות גם בקבצים שנגעתי בהם עצמם, לא רק ברמת runtime

**אחרי שינוי טייפים:**
- הרץ מחדש את Pyright/Pylance
- בדוק שכל הקריאות מתאימות לטייפ החדש
- עדכן את כל המשתמשים של הטייפ

**אחרי refactor של מודולים / imports:**
- בדוק את כל ה-callers ששונו, לא רק את המודול החדש
- אם Pylance מסמן import בעייתי, אל תניח שזה "רק cache" לפני שנוסו:
  - import מפורש מהמודול המלא
  - import של המודול עצמו במקום symbol import
  - בדיקה שהחבילה כוללת `__init__.py`
- אל תכריז "טופל ותקין" עד שהשגיאה האדומה עצמה נעלמה או שהוסבר במפורש למה זו בעיית IDE חיצונית ולא בעיית קוד

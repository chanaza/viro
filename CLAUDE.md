# researcher-agent — הקשר פרויקט

## מה הפרויקט עושה
מציאת כל סניפי רשת קמעונאית ישראלית לפי שם רשת, שמירה ל-CSV.
נגיש דרך ממשק צ'אט (Viro) או דרך CLI.

## Stack
- Python, browser-use, Pydantic, python-dotenv, pyyaml, FastAPI, uvicorn
- LLM: **Gemini בלבד דרך Vertex AI** (אילוץ קשיח)
- Google Cloud Project: ראה `.env` — מיקום הפרויקט: `me-west1`
- מיקום LLM מועדף: `europe-west3` או `europe-west4` (עדיפות, לא אילוץ קשיח)
- venv: `.venv/` בשורש הפרויקט

## מבנה קבצים
```
researcher-agent/
├── agent_service.py        ← שכבת שירות: לוגיקת browser-use, async generator events
├── config.py               ← קבועי סוכן: MAX_FAILURES, MAX_ACTIONS_PER_STEP, COLLECT_ALL
├── security_judge.py       ← SecurityJudge, Verdict (ללא תלות ב-UI)
├── requirements.txt        ← תלויות מאוחדות לכל הפרויקט
├── run_app.py              ← מפעיל uvicorn + פותח Edge (ל-Viro בלבד)
├── .venv/                  ← venv יחיד לכל הפרויקט
│
├── skills/                 ← הגדרות Skill (SKILL.md format), ללא תלות ב-app/
│   ├── __init__.py         ← exports: Skill, SkillMatch, SkillRegistry
│   ├── models.py           ← Skill, SkillMatch dataclasses
│   ├── registry.py         ← SkillRegistry: load, find, build_prompt, save_result
│   ├── research_models.py  ← ResearchModel, SourceLog
│   ├── research-navigation/SKILL.md  ← base skill: כללי ניווט גנריים
│   └── branches/
│       ├── SKILL.md        ← research skill: מחקר סניפים (5 מקורות)
│       ├── config.py       ← TRUSTED_AGGREGATORS, BUSINESS_PROFILE_PLATFORMS
│       ├── output_schema.py ← Branch, BranchList
│       └── render_context.py ← get_context(params) → platforms_block, aggregators_block
│
├── app/                    ← שכבת UI בלבד (Viro)
│   ├── server.py           ← FastAPI: SSE, /start, /pause, /resume, /stop, /send
│   ├── chat_agent.py       ← thin wrapper: AgentService + session log + history
│   ├── llm.py              ← create_llm(), create_orchestrator_llm()
│   ├── profiles.py         ← get_active_profile()
│   ├── user_config.py      ← load_settings(), allowed/denied actions
│   └── static/index.html   ← Chat UI (vanilla JS + SSE)
│
├── cli/                    ← הרצת CLI ישירה (ללא UI)
│   ├── main.py             ← entry point: SUBJECT + SKILL env vars
│   └── output/             ← תוצאות CLI (לא ב-git)
│
├── installer/              ← Inno Setup installer לאפליקציית Viro
│   ├── viro.iss
│   ├── setup_install.ps1
│   └── launch.vbs
│
└── legacy/                 ← קוד ישן (browser-use/src/) — לעיון בלבד
    └── src/
        ├── core/           ← ResearchAgent ABC (הוחלף ע"י agent_service.py)
        └── branches/       ← BranchesResearchAgent (הוחלף ע"י skills/branches/)
```

## הרצה — CLI
```bash
SUBJECT="שופרסל" .venv/Scripts/python.exe cli/main.py
```
משתני `.env` רלוונטיים:
- `SUBJECT` — שם הרשת (ברירת מחדל: שופרסל)
- `SKILL` — שם ה-skill להרצה (ברירת מחדל: branches)
- `COLLECT_ALL` — `true` לאיסוף מכל המקורות, `false` (ברירת מחדל) לעצור אחרי הצלחה ראשונה

## הרצה — Viro (UI)
```bash
.venv/Scripts/python.exe run_app.py
```

## ארכיטקטורה — שכבות
```
skills/          ← נתונים: הגדרות skill, output schemas, context renderers
agent_service.py ← לוגיקה: browser-use Agent, events async generator
app/chat_agent   ← UI logic: session, history, pause/resume briefing
app/server       ← HTTP/SSE transport
cli/main.py      ← CLI consumer
```

- `AgentService.run(task, skill_match)` — async generator מחזיר events: `skill_matched`, `step`, `security_warning`, `security_stop`, `done`, `stopped`, `error`
- `skill_output_dir` — תוצאות CSV: `cli/output/` (CLI) / `~/.viro/output/` (app)
- `session_output_dir` — artifacts טכניים: `~/.viro/sessions/`
- `COLLECT_ALL` — נשלט ע"י .env, מוזרק לפרומפט דרך `SkillRegistry.build_prompt()`

## הגדרות LLM
- `thinking_budget=0` — חשיבה מורחבת מבוטלת (מנעה timeout של 75 שניות)
- `max_output_tokens=32000`

## אאוטפוט (skill branches)
4 קבצים, prefix: `{skill_name}_{timestamp}`:
- `.csv` — רשימת סניפים
- `_log.csv` — לוג מקורות (visited/found/count/notes)
- `_history.csv` — היסטוריית פעולות מהסוכן
- `_urls.txt` — URLs ייחודיים

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

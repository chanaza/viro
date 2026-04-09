# researcher-agent — הקשר פרויקט

## מה הפרויקט עושה
מציאת כל סניפי רשת קמעונאית ישראלית לפי שם רשת, שמירה ל-CSV.
שני מימושים עצמאיים: `browser-use/` (Python, סוכן אוטונומי) ו-`stagehand/` (TypeScript, pipeline מובנה).

## Stack — browser-use
- Python, browser-use v0.12.5, Pydantic, python-dotenv, pyyaml
- LLM: **Gemini בלבד דרך Vertex AI** (אילוץ קשיח)
- Google Cloud Project: ראה `.env` — מיקום הפרויקט: `me-west1`
- מיקום LLM מועדף: `europe-west3` או `europe-west4` (עדיפות, לא אילוץ קשיח)

## מבנה קבצים — browser-use
```
browser-use/
├── main.py                    ← entry point בלבד
├── src/
│   ├── config.py              ← קבועים גנריים: LLM_MAX_OUTPUT_TOKENS, COLLECT_ALL
│   ├── core/
│   │   ├── agent.py           ← ResearchAgent ABC — כל התשתית הגנרית
│   │   ├── models.py          ← SourceLog
│   │   └── prompts.yaml       ← preamble, navigation, stop_rule variants
│   └── branches/
│       ├── agent.py           ← BranchesResearchAgent
│       ├── models.py          ← Branch, BranchList
│       ├── task.py            ← get_branches_specific_instructions()
│       └── config.py          ← TRUSTED_AGGREGATORS, BUSINESS_PROFILE_PLATFORMS
└── output/                    ← קבצי תוצאות (לא ב-git)
```

## הרצה
```bash
browser-use/.venv/Scripts/python.exe browser-use/main.py
```
משתני `.env` רלוונטיים:
- `SUBJECT` — שם הרשת (ברירת מחדל: שופרסל)
- `COLLECT_ALL` — `true` לאיסוף מכל המקורות, `false` (ברירת מחדל) לעצור אחרי הצלחה ראשונה

## הגדרות LLM
- `thinking_budget=0` — חשיבה מורחבת מבוטלת (מנעה timeout של 75 שניות)
- `max_output_tokens=32000`
- `file_system_path=OUTPUT_DIR` — browser-use שומר תוצאות evaluate גדולות לקובץ

## ארכיטקטורה — עקרונות
- **core** = תשתית גנרית שלא משתנה בין סוגי מחקר: ResearchAgent ABC, שמירת קבצים, prompts.yaml
- **branches** = הגדרות ספציפיות לסניפים: goal, output schema, specific instructions, aggregators
- **config.py** = פרמטרים שמשתנים בין ריצות (COLLECT_ALL, LLM settings)
- **prompts.yaml** = כל הפרומפטים הגנריים כולל שני וריאנטי stop_rule — מוזרקים ב-`_build_task`
- כל פרמטר התנהגותי שמשתנה בין ריצות חי ב-.env עם ברירת מחדל ב-config.py

## אופן פעולת הסוכן
1. **קבלת משימה**: הפרומפט מ-`build_task()` — כל ההיגיון (סדר מקורות, כלל עצירה) מגיע אך ורק משם
2. **ריצה אוטונומית**: screenshot + DOM → decide → act. מחזורי read→decide→act
3. **כלל עצירה**: נשלט ע"י `COLLECT_ALL` — מוזרק מ-core לפרומפט דרך prompts.yaml
4. **אאוטפוט קשיח**: `done()` מחזיר את המודל המוגדר ב-`output_model_schema`
5. **שמירה**: `save_domain_data()` ב-core — גנרי, כותב CSV לפי `model_fields` של הפריטים. ניתן לדרוס בתת-קלאס אם נדרש פורמט שונה.

## אאוטפוט
4 קבצים בתיקיית `output/`, prefix: `{subject}_{research_type}`:
- `.csv` — רשימת פריטים
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
- **maps.google.com**: extract לא עקבי — לפעמים מצליח (7-10 תוצאות), לפעמים נכשל לגמרי. הערים לעיתים ריקות, מה שמקשה על הערכת כיסוי גיאוגרפי
- **d.co.il**: extract נכשל לעיתים גם כשיש תוצאות — הסוכן נכנס ללולאת find_elements/evaluate
- **post-processing**: לא מומש — עסקים עם שם דומה (למשל "פרזול חצי חינם") נכנסים לתוצאות מ-d.co.il

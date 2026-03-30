# researcher-agent — הקשר פרויקט

## מה הפרויקט עושה
מציאת כל סניפי רשת קמעונאית ישראלית לפי שם רשת, שמירה ל-CSV.
שני מימושים עצמאיים: `browser-use/` (Python, סוכן אוטונומי) ו-`stagehand/` (TypeScript, pipeline מובנה).

## Stack — browser-use
- Python, browser-use v0.12.5, Pydantic, python-dotenv
- LLM: **Gemini בלבד דרך Vertex AI** (אילוץ קשיח)
- Google Cloud Project: ראה `.env` — מיקום הפרויקט: `me-west1`
- מיקום LLM מועדף: `europe-west3` או `europe-west4` (עדיפות, לא אילוץ קשיח)
- `output_model_schema=BranchList` — מאכיף structured output ישירות מהסוכן

## מבנה קבצים — browser-use
```
browser-use/
├── main.py          ← entry point בלבד
├── src/
│   ├── config.py   ← קבועים + TRUSTED_AGGREGATORS (ללא פונקציות)
│   ├── models.py   ← Branch, SourceLog, BranchList
│   ├── task.py     ← build_task()
│   └── output.py   ← שמירת 4 קבצי אאוטפוט
└── output/         ← קבצי תוצאות (לא ב-git)
```

## הרצה
```bash
browser-use/.venv/Scripts/python.exe browser-use/main.py
```
משתנה `SUBJECT` ב-.env קובע את שם הרשת (ברירת מחדל: שופרסל).

## הגדרות LLM
- `thinking_budget=0` — חשיבה מורחבת מבוטלת (מנעה timeout של 75 שניות בעיבוד dropdown גדול)
- `max_output_tokens=32000`
- `file_system_path=OUTPUT_DIR` — browser-use שומר תוצאות evaluate גדולות לקובץ; הסוכן יכול לקרוא אותן בשלבים מאוחרים

## אופן פעולת הסוכן
1. **קבלת משימה**: הסוכן מקבל את הפרומפט מ-`build_task()` — כל ההיגיון (סדר מקורות, מתי לעבור הלאה, מתי לעצור) מגיע **אך ורק משם**. אין קוד Python שמפעיל לוגיקה זו.
2. **ריצה אוטונומית**: הסוכן רואה את המסך (screenshot + DOM) ומחליט בעצמו על כל פעולה — ניווט, לחיצה, גלילה, חילוץ. חוזר על מחזורי read→decide→act.
3. **תנאי עצירה**: הסוכן עוצר כשהכיסוי הגיאוגרפי מספק או כשמיצה את כל המקורות, וקורא ל-`done()`.
4. **אאוטפוט קשיח**: `done()` מחזיר `BranchList` — רשימת פריטים שמצא + לוג אתרים שנוסו. המבנה נאכף על ידי `output_model_schema=BranchList`.
5. **שמירה**: `output.py` שולף את ה-`BranchList` ושומר 4 קבצים (ראה אאוטפוט).

## אאוטפוט
4 קבצים בתיקיית `output/`:
- `{subject}.csv` — רשימת סניפים
- `{subject}_log.csv` — לוג LLM (מקורות שנוסו, הצלחה/כישלון)
- `{subject}_history.csv` — היסטוריית פעולות אמיתית מהסוכן (מתוך `result.history`)
- `{subject}_urls.txt` — URLs ייחודיים שנוסו

## סדר עדיפויות מקורות (בתוך הפרומפט)
1. האתר הרשמי של הרשת
2. אתר שקיפות מחירים (חיפוש גוגל)
3. דפים עסקיים (פייסבוק, אינסטגרם, גוגל מאפס)
4. אגרגטורים: easy.co.il, maps.google.com, d.co.il, waze.com
5. כל מקור רלוונטי אחר

## בעיות ידועות / מצב נוכחי
- סביבת הבדיקה חסומה על ידי אתרוג (פילטר תוכן) — פייסבוק, אינסטגרם, DuckDuckGo אינם נגישים
- שמות סניפים מה-dropdown מכילים מספר סידורי (`"1 - שלי ת"א- בן יהודה"`) — ניתן לנקות ב-post-processing
- כתובת ועיר ריקים כשהמקור הוא dropdown של שקיפות מחירים — המידע לא קיים שם

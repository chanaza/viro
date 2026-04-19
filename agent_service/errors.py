def friendly_error(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        return "חרגת ממכסת ה-API של Gemini. המתן עד מחר או עדכן את פרטי החיבור ב-Viro."
    if "Reauthentication" in msg or "reauthenticate" in msg:
        return "פג תוקף האימות ל-Google Cloud. הרץ: gcloud auth application-default login"
    if "401" in msg or "403" in msg or "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
        return "שגיאת אימות — בדוק את ה-API key או פרטי Vertex AI בהגדרות Viro."
    if "UNAVAILABLE" in msg or "503" in msg or "connection" in msg.lower():
        return "שירות Gemini לא זמין כרגע. נסה שוב בעוד מספר שניות."
    return f"שגיאה: {msg}"

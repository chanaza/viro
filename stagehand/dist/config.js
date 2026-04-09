// ─── מה אנחנו מחפשים ─────────────────────────────────────────────────────────
// שנה כאן כדי לחפש משהו אחר מחר (לדוגמה: "מחירים", "מוצרים")
export const SEARCH_TARGET = "סניפים";
export const CSV_HEADERS = "שם סניף,כתובת,עיר";
// ─── הגדרות חיפוש ─────────────────────────────────────────────────────────────
export const NUM_SEARCH_RESULTS = 5;
export const buildSearchQuery = (subject) => `"${subject}" ${SEARCH_TARGET}`;
// ─── דירוג מקורות ─────────────────────────────────────────────────────────────
// Priority 2: רשתות חברתיות / דפים עסקיים שנחשבים (Gemini יזהה אם הדף שייך לרשת)
export const BUSINESS_PROFILE_PLATFORMS = [
    "facebook.com",
    "instagram.com",
    "maps.google.com",
    "business.google.com",
    "tiktok.com",
];
// Priority 3: aggregators מוכרים לנושא
// searchUrl: ניווט ישיר לתוצאות חיפוש — כאשר קיים, עדיף על פני homepage + act()
// ללא searchUrl: Stagehand יגיע לדף הבית ויחפש עם act()
export const TRUSTED_AGGREGATORS = [
    {
        domain: "easy.co.il",
        // /search/{hebrew} redirects to /list/{EnglishSlug} — no need to know the English slug
        searchUrl: (subject) => `https://easy.co.il/search/${encodeURIComponent(subject)}`,
        // order=5: sort by rating (not distance); radius=500000: nationwide
        appendParams: "order=5&radius=500000",
    },
    { domain: "d.co.il" },
    { domain: "waze.com" },
];
// ─── תבניות prompt ────────────────────────────────────────────────────────────
export const PROMPTS = {
    searchExtract: (n) => `חלץ את ${n} תוצאות החיפוש הראשונות. עבור כל תוצאה: URL מלא, כותרת, תיאור קצר.`,
    classify: (subject, list, platforms) => `אתה מסווג URLs עבור "${subject}".\n` +
        `עבור כל URL קבע:\n` +
        `- relevant: true אם הוא מקור ישיר לרשימת ${SEARCH_TARGET} של "${subject}", אחרת false\n` +
        `- type: "api" אם endpoint, "pdf" אם PDF, "html" אחרת\n` +
        `- priority:\n` +
        `    1 = האתר הרשמי של "${subject}"\n` +
        `    2 = הדף העסקי הרשמי של "${subject}" באחת מהפלטפורמות: ${platforms.join(", ")}\n` +
        `    4 = כל שאר\n\n` +
        `URLs:\n${list}\n\n` +
        `החזר JSON בלבד: {"classified": [{"url":"...","relevant":true,"type":"html","priority":1}, ...]}`,
    actHtml: (subject) => `הדף הוא מאתר "${subject}". בצע את הפעולות הנדרשות כדי להציג את רשימת כל ה${SEARCH_TARGET} המלאה: ` +
        `לחץ על כפתורי "הצג הכל" אם קיימים, הסר פילטרים, טען תוצאות נוספות אם צריך.`,
    actOnAggregator: (subject, domain) => `אתה באתר ${domain}. חפש את "${subject}" ונווט לדף המציג את רשימת כל ה${SEARCH_TARGET} שלה.`,
    extractHtml: (subject) => `חלץ את כל ה${SEARCH_TARGET} של רשת ${subject} המופיעים בדף. עבור כל פריט: שם, עיר, כתובת מלאה.`,
    extractApi: (subject, data) => `חלץ ${SEARCH_TARGET} של "${subject}" מנתוני ה-API הבאים.\n` +
        `החזר JSON בלבד: {"items": [{"name":"...","city":"...","address":"..."}, ...]}\n\n` +
        data.slice(0, 100_000),
    extractPdf: (subject) => `חלץ את כל ה${SEARCH_TARGET} של "${subject}" מהמסמך.\n` +
        `החזר JSON בלבד: {"items": [{"name":"...","city":"...","address":"..."}, ...]}`,
};

import { Stagehand } from "@browserbasehq/stagehand";
import { GoogleGenAI } from "@google/genai";
import { VertexGoogleClient } from "./vertexClient.js";
import { z } from "zod";
import * as dotenv from "dotenv";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHAIN = process.env.CHAIN || "שופרסל";
const PROJECT = process.env.GOOGLE_CLOUD_PROJECT!;
const LOCATION = process.env.GOOGLE_CLOUD_LOCATION!;
const MODEL = process.env.GEMINI_MODEL!;

const ai = new GoogleGenAI({ vertexai: true, project: PROJECT, location: LOCATION });

// ─── שלב 1: מחקר – מצא מקור נתוני סניפים באמצעות Gemini + Google Search ───

async function researchBranchUrls(chain: string): Promise<string[]> {
  console.log(`\n🔍 שלב 1: חיפוש מקורות נתונים של "${chain}" באמצעות Gemini...`);

  // שלב א: שאל את Gemini מידע כללי על האתר מתוך ידע האימון (ללא גוגל)
  const result = await ai.models.generateContent({
    model: MODEL,
    contents: [
      {
        role: "user",
        parts: [
          {
            text: `אתה מומחה לאתרי אינטרנט ישראליים.
ספר לי מה אתה יודע על האתר הרשמי של רשת "${chain}" בישראל:
1. מהו ה-domain הרשמי?
2. האם יש דף ממנו ניתן לשלוף רשימת כל הסניפים? (שם, כתובת, עיר)
3. האם יש API endpoint ידוע? (למשל /api/stores, /api/branches)
4. האם יש קבצי PDF/JSON ציבוריים עם רשימת הסניפים?

ענה בעברית וציין URL מלא ומדויק אם אתה יודע.`,
          },
        ],
      },
    ],
    // ללא tools: [{ googleSearch }] — רק ידע אימון
  });

  const text = result.text ?? "";
  console.log("תשובת Gemini:\n", text);

  // שלוף URLs אמיתיים מהטקסט (רק תווי URL חוקיים)
  const allUrlsInText = text.match(/https?:\/\/[a-zA-Z0-9\-._~:/?#\[\]@!$&()*+,;=%]+/g) ?? [];
  const realUrls = [...new Set(
    allUrlsInText.filter(
      (u) => !u.includes("vertexaisearch") && !u.includes("google.com/search")
    )
  )];

  if (realUrls.length > 0) {
    console.log("URLs שנמצאו:", realUrls);
    return realUrls;
  }

  // Fallback: grounding metadata
  const candidate = (result.candidates as any)?.[0];
  const groundingChunks = candidate?.groundingMetadata?.groundingChunks ?? [];
  const metaUrls: string[] = groundingChunks
    .map((c: any) => c.web?.uri)
    .filter((u: any): u is string => typeof u === "string")
    .filter((u: string) => !u.includes("vertexaisearch") && !u.includes("google.com/search"));

  if (metaUrls.length > 0) {
    console.log("URLs מ-grounding metadata:", metaUrls);
    return metaUrls;
  }

  return [];
}

// ─── שלב 2: חילוץ – בהתאם לסוג ה-URL ───

async function extractFromPdf(
  url: string,
  browserPage?: any
): Promise<{ name: string; city: string; address: string }[]> {
  console.log(`📄 מוריד PDF ומעביר ל-Gemini לניתוח...`);

  let base64: string;

  if (browserPage) {
    // הורד דרך Playwright request context (עוקף CORS וחסימות IP)
    const requestContext = browserPage.context().request;
    const response = await requestContext.get(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
      },
    });
    if (!response.ok()) throw new Error(`HTTP ${response.status()}`);
    const pdfBuffer = await response.body();
    base64 = pdfBuffer.toString("base64");
  } else {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const pdfBytes = await resp.arrayBuffer();
    base64 = Buffer.from(pdfBytes).toString("base64");
  }

  const result = await ai.models.generateContent({
    model: MODEL,
    contents: [
      {
        role: "user",
        parts: [
          {
            inlineData: { mimeType: "application/pdf", data: base64 },
          },
          {
            text: `זהו מסמך עם רשימת סניפים של רשת "${CHAIN}".
חלץ את כל הסניפים ממנו והחזר JSON בלבד בפורמט:
{"branches": [{"name": "שם סניף", "city": "עיר", "address": "כתובת מלאה"}, ...]}`,
          },
        ],
      },
    ],
  });

  const text = result.text ?? "";
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) return [];
  const parsed = JSON.parse(jsonMatch[0]);
  return parsed.branches ?? [];
}

async function extractFromHtml(
  page: any,
  stagehand: any,
  url: string
): Promise<{ name: string; city: string; address: string }[]> {
  const isApiUrl =
    url.includes("/api/") || url.includes("filter?") || url.includes("storeType=");

  if (isApiUrl) {
    // ניווט ישיר ל-API endpoint ושליפת JSON מהדפדפן
    console.log("📡 ניווט ל-API endpoint...");
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);

    // שלוף את תוכן הגוף כ-JSON
    const rawText: string = await page.evaluate(
      () => document.body?.innerText ?? document.documentElement.innerText ?? ""
    );
    console.log(`📄 קיבלנו ${rawText.length} תווים מה-API`);

    if (rawText.length > 100) {
      const result = await ai.models.generateContent({
        model: MODEL,
        contents: [
          {
            role: "user",
            parts: [
              {
                text: `הנה נתוני JSON שהגיעו מ-API של רשת "${CHAIN}".
חלץ את כל הסניפים מהנתונים והחזר JSON בלבד בפורמט:
{"branches": [{"name": "שם סניף", "city": "עיר", "address": "כתובת מלאה"}, ...]}

נתוני ה-API:
${rawText.slice(0, 100000)}`,
              },
            ],
          },
        ],
      });
      const text = result.text ?? "";
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        try {
          const parsed = JSON.parse(match[0]);
          return parsed.branches ?? [];
        } catch {}
      }
    }
    return [];
  }

  // HTML רגיל: Stagehand extract (a11y snapshot)
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  console.log("URL שנטען:", page.url());

  const result = await stagehand.extract(
    `חלץ את כל הסניפים של רשת ${CHAIN} המופיעים בדף.
     עבור כל סניף החזר: שם הסניף, העיר, הכתובת המלאה.`,
    z.object({
      branches: z.array(
        z.object({
          name: z.string().describe("שם הסניף"),
          city: z.string().describe("העיר"),
          address: z.string().describe("הכתובת המלאה"),
        })
      ),
    })
  );
  return result.branches;
}

// ─── ריצה ראשית ───

const urls = await researchBranchUrls(CHAIN);

if (urls.length === 0) {
  console.error("לא נמצאו URLs. עוצר.");
  process.exit(1);
}

console.log(`\n📋 נמצאו ${urls.length} URL(s):`, urls);

const isPdf = (url: string) => url.toLowerCase().includes(".pdf");

let allBranches: { name: string; city: string; address: string }[] = [];

const htmlUrls = urls.filter((u) => !isPdf(u));
const pdfUrls = urls.filter((u) => isPdf(u));

const needsBrowser = urls.length > 0; // צריך דפדפן לכל המקרים (PDF דרך דפדפן + HTML)

let stagehand: Stagehand | null = null;
let page: any = null;

if (needsBrowser) {
  stagehand = new Stagehand({
    env: "LOCAL",
    llmClient: new VertexGoogleClient({ modelName: MODEL, project: PROJECT, location: LOCATION }),
    verbose: 1,
  });
  await stagehand.init();
  page = stagehand.context.pages()[0];
}

// PDF: הורד דרך הדפדפן + Gemini לניתוח
for (const url of pdfUrls) {
  console.log(`\n📄 PDF: ${url}`);
  try {
    const branches = await extractFromPdf(url, page);
    console.log(`✅ נמצאו ${branches.length} סניפים`);
    allBranches.push(...branches);
  } catch (err: any) {
    console.warn(`⚠️ שגיאה ב-${url}:`, err.message);
  }
}

// HTML: Stagehand extract
for (const url of htmlUrls) {
  console.log(`\n🌐 HTML: ${url}`);
  try {
    const branches = await extractFromHtml(page, stagehand, url);
    console.log(`✅ נמצאו ${branches.length} סניפים`);
    allBranches.push(...branches);
  } catch (err: any) {
    console.warn(`⚠️ שגיאה ב-${url}:`, err.message);
  }
}

if (stagehand) await stagehand.close();

// ─── שלב 3: שמירה לקובץ ───

const outputDir = path.join(__dirname, "output");
fs.mkdirSync(outputDir, { recursive: true });

const chainSlug = CHAIN.replace(/\s+/g, "_");
const csvPath = path.join(outputDir, `${chainSlug}_branches.csv`);
const csvContent =
  "שם סניף,כתובת,עיר\n" +
  allBranches.map((b) => `"${b.name}","${b.address}","${b.city}"`).join("\n");

fs.writeFileSync(csvPath, "\uFEFF" + csvContent, "utf8");

console.log(`\n✅ נמצאו ${allBranches.length} סניפים סה"כ – נשמר ב: ${csvPath}\n`);
for (const branch of allBranches) {
  console.log(`- ${branch.name} | ${branch.address} | ${branch.city}`);
}

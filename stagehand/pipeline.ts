import { GoogleGenAI } from "@google/genai";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

import { BrowserManager } from "./browser.js";
import {
  buildSearchQuery,
  BUSINESS_PROFILE_PLATFORMS,
  CSV_HEADERS,
  NUM_SEARCH_RESULTS,
  PROMPTS,
  SEARCH_TARGET,
  TRUSTED_AGGREGATORS,
} from "./config.js";

import type { ClassifiedUrl, ResultItem, SearchResult } from "./types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const resultSchema = z.object({
  items: z.array(z.object({
    name: z.string(),
    city: z.string(),
    address: z.string(),
  })),
});

export class ResearchPipeline {
  private readonly ai: GoogleGenAI;
  private readonly browser: BrowserManager;
  private readonly model: string;

  constructor(private readonly subject: string) {
    this.model   = process.env.GEMINI_MODEL!;
    this.ai      = new GoogleGenAI({
      vertexai: true,
      project:  process.env.GOOGLE_CLOUD_PROJECT!,
      location: process.env.LLM_LOCATION!,
    });
    this.browser = new BrowserManager(
      this.model,
      process.env.GOOGLE_CLOUD_PROJECT!,
      process.env.LLM_LOCATION!,
    );
  }

  async run(): Promise<void> {
    try {
      await this.browser.init();

      const searchResults = await this.search();
      if (searchResults.length === 0) {
        console.error("No search results found. Aborting.");
        return;
      }

      const classified = await this.classify(searchResults);
      const relevant   = classified.filter((u) => u.relevant);

      if (relevant.length === 0) {
        console.error("No relevant URLs found after classification.");
        return;
      }

      const items = await this.extract(relevant);
      this.save(items);
    } finally {
      await this.browser.close();
    }
  }

  // ─── שלב 1: חיפוש Google ────────────────────────────────────────────────────

  private async search(): Promise<SearchResult[]> {
    console.log(`\n🔍 שלב 1: חיפוש Google עבור "${this.subject}"...`);

    const query = buildSearchQuery(this.subject);
    await this.browser.page.goto(
      `https://www.google.com/search?q=${encodeURIComponent(query)}&num=${NUM_SEARCH_RESULTS}`,
      { waitUntil: "domcontentloaded" },
    );

    // שליפת hrefs ישירות מה-DOM למניעת קיצור URLs
    // מכסה מספר מבני עמוד שגוגל משתמש בהם
    const results: SearchResult[] = await this.browser.page.evaluate((n: number) => {
      const RESULT_SELECTORS = ["div.g", "[data-sokoban-container]", "[data-hveid]", "li.b_algo"];
      const seen = new Set<string>();
      const out: { url: string; title: string; snippet: string }[] = [];

      for (const sel of RESULT_SELECTORS) {
        for (const block of Array.from(document.querySelectorAll(sel))) {
          const a = block.querySelector("a[href]") as HTMLAnchorElement | null;
          if (!a) continue;
          const href = a.href ?? "";
          if (!href.startsWith("http") || href.includes("google.com") || seen.has(href)) continue;
          seen.add(href);
          out.push({
            url:     href,
            title:   (block.querySelector("h3")?.textContent ?? "").trim(),
            snippet: (block.querySelector(".VwiC3b, [data-sncf], [style*='line-clamp']")?.textContent ?? "").trim(),
          });
          if (out.length >= n) return out;
        }
        if (out.length >= n) break;
      }
      return out;
    }, NUM_SEARCH_RESULTS);

    if (results.length === 0) {
      console.warn("Search returned 0 results — Google DOM structure may have changed or CAPTCHA triggered.");
      // fallback: נסה לשלוף כל לינק חיצוני עם h3 (מבנה עתידי של גוגל)
      const fallback: SearchResult[] = await this.browser.page.evaluate((n: number) => {
        const seen = new Set<string>();
        const out: { url: string; title: string; snippet: string }[] = [];
        for (const a of Array.from(document.querySelectorAll("a[href]")) as HTMLAnchorElement[]) {
          const href = a.href ?? "";
          if (!href.startsWith("http") || href.includes("google.com") || seen.has(href)) continue;
          const h3 = a.querySelector("h3") ?? a.closest("*")?.querySelector("h3");
          if (!h3) continue;
          seen.add(href);
          out.push({ url: href, title: h3.textContent?.trim() ?? "", snippet: "" });
          if (out.length >= n) break;
        }
        return out;
      }, NUM_SEARCH_RESULTS);

      if (fallback.length === 0) return [];
      console.log(`Fallback selector found ${fallback.length} results`);
      return fallback;
    }

    console.log(`נמצאו ${results.length} תוצאות`);
    results.forEach((r) => console.log(`  ${r.url}`));
    return results;
  }

  // ─── שלב 2: סיווג URLs ──────────────────────────────────────────────────────

  private async classify(results: SearchResult[]): Promise<ClassifiedUrl[]> {
    console.log(`\n🏷️  שלב 2: סיווג ${results.length} URLs...`);

    const list = results
      .map((r, i) => `${i + 1}. ${r.url}\n   כותרת: ${r.title}\n   תיאור: ${r.snippet}`)
      .join("\n\n");

    const response = await this.ai.models.generateContent({
      model: this.model,
      contents: [{
        role: "user",
        parts: [{ text: PROMPTS.classify(this.subject, list, BUSINESS_PROFILE_PLATFORMS) }],
      }],
    });

    const match = (response.text ?? "").match(/\{[\s\S]*\}/);
    if (!match) throw new Error("classify: invalid response from Gemini");

    const classified: ClassifiedUrl[] = JSON.parse(match[0]).classified;
    classified.forEach((c) =>
      console.log(`  ${c.relevant ? "✅" : "❌"} [p${c.priority}][${c.type}] ${c.url}`)
    );
    return classified;
  }

  // ─── שלב 3: חילוץ ───────────────────────────────────────────────────────────

  private async extract(classified: ClassifiedUrl[]): Promise<ResultItem[]> {
    console.log(`\n📋 שלב 3: חילוץ לפי עדיפות...`);

    const group = (p: number) => classified.filter((u) => u.priority === p);

    const levels: Array<[string, () => Promise<ResultItem[]>]> = [
      ["p1 — אתר רשמי",        () => this.extractGroup(group(1))],
      ["p2 — דפים עסקיים",     () => this.extractGroup(group(2))],
      ["p3 — aggregators",      () => this.extractFromAggregators()],
      ["p4 — תוצאות נוספות",   () => this.extractGroup(group(4))],
    ];

    for (const [label, run] of levels) {
      console.log(`  🔄 מנסה ${label}...`);
      const items = await run();
      if (items.length > 0) return items;
    }
    return [];
  }

  private async extractGroup(group: ClassifiedUrl[]): Promise<ResultItem[]> {
    if (group.length === 0) return [];
    const all: ResultItem[] = [];
    for (const item of group) {
      try {
        const items = item.type === "pdf"
          ? await this.extractFromPdf(item.url)
          : await this.extractFromPage(item.url, item.type === "api");

        console.log(`    ✅ ${item.url} → ${items.length} פריטים`);
        all.push(...items);
      } catch (err: any) {
        console.warn(`    ⚠️ Failed to extract from ${item.url}:`, err.message);
      }
    }
    return all;
  }

  private async extractFromAggregators(): Promise<ResultItem[]> {
    for (const aggregator of TRUSTED_AGGREGATORS) {
      try {
        const url = aggregator.searchUrl
          ? aggregator.searchUrl(this.subject, SEARCH_TARGET)
          : `https://${aggregator.domain}`;

        await this.browser.page.goto(url, { waitUntil: "load", timeout: 30000 });

        // Append extra query params to the post-redirect URL (e.g. easy.co.il radius/order)
        if (aggregator.appendParams) {
          const finalUrl = this.browser.page.url();
          const sep = finalUrl.includes("?") ? "&" : "?";
          await this.browser.page.goto(`${finalUrl}${sep}${aggregator.appendParams}`, {
            waitUntil: "load",
            timeout: 30000,
          });
        }

        await this.browser.page.waitForTimeout(2000);

        // טען תוצאות נוספות בלולאה — עד שאין עוד כפתור "טען עוד" או עד 20 עמודים
        for (let page = 0; page < 20; page++) {
          try {
            await this.browser.stagehandInstance.act(PROMPTS.actLoadMore());
            await this.browser.page.waitForTimeout(1500);
          } catch {
            break; // אין כפתור "טען עוד" — עצור
          }
        }

        // אם הגענו לדף הבית (ללא searchUrl) — נבקש מ-Stagehand לנווט לעמוד הרלוונטי
        if (!aggregator.searchUrl) {
          try {
            await this.browser.stagehandInstance.act(
              PROMPTS.actOnAggregator(this.subject, aggregator.domain)
            );
            await this.browser.page.waitForTimeout(3000);
          } catch (actErr: any) {
            // act() נכשל — האתר כנראה לא נגיש דרך a11y (SPA כבד / lazy-loaded search)
            // נמשיך לנסות לחלץ ממה שנטען, ונדווח
            console.warn(`    ℹ️ act() unavailable on ${aggregator.domain} — attempting extract on current page`);
          }
        }

        const { items } = await this.browser.stagehandInstance.extract(
          PROMPTS.extractHtml(this.subject),
          resultSchema,
        );

        if (items.length > 0) {
          console.log(`    ✅ ${aggregator.domain} → ${items.length} פריטים`);
          return items;
        }
        console.log(`    ⚪ ${aggregator.domain} → 0 פריטים`);
      } catch (err: any) {
        console.warn(`    ⚠️ Failed on aggregator ${aggregator.domain}:`, err.message);
      }
    }
    return [];
  }

  private async extractFromPdf(url: string): Promise<ResultItem[]> {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status} fetching PDF: ${url}`);

    const base64 = Buffer.from(await resp.arrayBuffer()).toString("base64");
    const result = await this.ai.models.generateContent({
      model: this.model,
      contents: [{
        role: "user",
        parts: [
          { inlineData: { mimeType: "application/pdf", data: base64 } },
          { text: PROMPTS.extractPdf(this.subject) },
        ],
      }],
    });

    const match = (result.text ?? "").match(/\{[\s\S]*\}/);
    if (!match) return [];
    return JSON.parse(match[0]).items ?? [];
  }

  private async extractFromPage(url: string, isApi: boolean): Promise<ResultItem[]> {
    await this.browser.page.goto(url, { waitUntil: "load", timeout: 60000 });
    await this.browser.page.waitForTimeout(5000);

    if (isApi) {
      const rawText: string = await this.browser.page.evaluate(
        () => document.body?.innerText ?? ""
      );
      if (rawText.length < 100) return [];

      const result = await this.ai.models.generateContent({
        model: this.model,
        contents: [{ role: "user", parts: [{ text: PROMPTS.extractApi(this.subject, rawText) }] }],
      });

      const match = (result.text ?? "").match(/\{[\s\S]*\}/);
      if (!match) return [];
      return JSON.parse(match[0]).items ?? [];
    }

    await this.browser.stagehandInstance.act(PROMPTS.actHtml(this.subject));
    await this.browser.page.waitForTimeout(2000);

    const { items } = await this.browser.stagehandInstance.extract(
      PROMPTS.extractHtml(this.subject),
      resultSchema,
    );
    return items;
  }

  // ─── שלב 4: שמירה ───────────────────────────────────────────────────────────

  private save(items: ResultItem[]): void {
    console.log(`\n💾 שלב 4: שמירת ${items.length} פריטים...`);

    const outputDir = path.join(__dirname, "output");
    fs.mkdirSync(outputDir, { recursive: true });

    const csvPath = path.join(outputDir, `${this.subject.replace(/\s+/g, "_")}.csv`);
    const csv =
      CSV_HEADERS + "\n" +
      items.map((i) => `"${i.name}","${i.address}","${i.city}"`).join("\n");

    fs.writeFileSync(csvPath, "\uFEFF" + csv, "utf8");
    console.log(`✅ נשמר ב: ${csvPath}`);
    items.forEach((i) => console.log(`  - ${i.name} | ${i.address} | ${i.city}`));
  }
}

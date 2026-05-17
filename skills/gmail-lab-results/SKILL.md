---
name: gmail-lab-results
description: >
  Extracts lab test results from PDF attachments stored in a Gmail folder and saves them to CSV.
  Use when the user asks to collect lab results, blood tests, or medical test data from Gmail emails.
  Trigger phrases: "בדיקות מעבדה", "תוצאות בדיקות", "בדיקות דם", "בדיקות סוכר", "בדיקת סוכר",
  "תיק רפואי", "מיילים עם בדיקות", "lab results", "blood tests", "blood sugar", "medical results",
  "gmail folder", "תיקיה בגימייל", "מהמיילים שלי".
parameters:
  folder:
    type: string
    description: Gmail label/folder path where the emails are stored (e.g. מידע חשוב/תיק)
    extract_from_request: true
  test_filter:
    type: string
    description: >
      Specific test name(s) to collect (e.g. גלוקוז, סוכר, glucose).
      If the user did not specify a particular test — set to "all".
    extract_from_request: true
goal: 'Extract {test_filter} lab test results from PDF attachments in the Gmail folder "{folder}" and save to CSV.'
output_schema: LabResultList
---

## Strict navigation rule — read this before anything else

**Do NOT use the Gmail sidebar to navigate to any folder.** The sidebar shows folders as flat items that look separate even when they are nested — clicking a parent label navigates to it without entering the subfolder. This causes you to search in the wrong folder.

**The only permitted navigation method is the Gmail search bar.** Do not click on any label in the sidebar. Do not expand any sidebar section. Use the search bar exclusively.

---

## Overview

You will:
1. Search Gmail with a specific query to get the exact list of emails in the target folder — before opening any email.
2. Process each email exactly once, in order, by re-navigating to the same search results between emails.
3. For each email: download every PDF attachment, read it, and extract the relevant test results.
4. Call `done()` when all emails have been processed.

**Critical rule — iteration:** Never search for "the next unprocessed email" by inspecting the DOM. After processing each email, return to the search results and click the email at the next known position.

---

## Phase 1 — Discover all emails and collect their URLs

1. Navigate to `https://mail.google.com`.
2. Locate the Gmail search bar — it is the wide input field at the **top center** of the page, with a magnifying glass icon on its left side. It is always visible at the top of Gmail; do not look for it in the sidebar.
3. Click the search bar to focus it.
4. Type the following query **exactly as written** and press Enter:
   `in:"{folder}" has:attachment`
   This instructs Gmail to show only emails in the exact folder "{folder}" that have attachments. Do not modify this query. Do not replace it with a sidebar click.
5. Wait for the results list to load. Verify the page title shows search results (not an inbox or folder view).
6. Use `evaluate` to collect the direct URL of every email row now visible. Run this JavaScript:
   ```javascript
   Array.from(document.querySelectorAll('tr[data-legacy-thread-id]'))
     .map(tr => ({
       id: tr.getAttribute('data-legacy-thread-id'),
       url: 'https://mail.google.com/mail/u/0/#all/' + tr.getAttribute('data-legacy-thread-id')
     }))
   ```
   If that returns no results, try the fallback:
   ```javascript
   Array.from(document.querySelectorAll('tr[jslog]'))
     .map(tr => {
       const id = tr.getAttribute('data-legacy-thread-id') || tr.getAttribute('data-thread-id');
       return id ? { id, url: 'https://mail.google.com/mail/u/0/#all/' + id } : null;
     }).filter(Boolean)
   ```
7. Store the resulting list of URLs in memory — this is your **email queue**. Call the total count **N**.
   - Step budget: you have approximately 100 steps total. Reserve 2 steps to set up and 3 steps per email for downloading and extracting. This means you can process at most 30 emails. If N > 30, process the first 30 only.

---

## Phase 2 — Process each email by direct URL navigation

**Do not click emails in the list. Navigate to each email by URL.**

For each email at index i (1 to min(N, 30)):

**Step A — Navigate directly to the email:**
- Take the URL for email i from your queue (collected in Phase 1).
- Use `navigate` to go directly to that URL.
- Wait for the email to load.

**Step B — Find and download PDF attachments:**
- Scroll to the bottom of the email to reveal attachments.
- For each file that has a `.pdf` extension or a PDF icon:
  1. Hover over the attachment thumbnail to reveal the action icons.
  2. Click the **download arrow** (the downward-pointing arrow icon on the thumbnail) — do NOT click the thumbnail itself (that opens the PDF inside Gmail in a non-downloadable iframe).
  3. After clicking the download arrow, check `available_file_paths` in the next step — the file appears there once downloaded.
  4. Use `read_file` to read the downloaded PDF.
  5. Extract test results using the Extraction Rules below and **store them in memory**.
- If an email has no PDF attachment: skip to Step C.
- If a PDF download fails: try once more with the download arrow. If it still fails, note the email subject and continue to Step C.

**Step C — Move to next email:**
- Take the URL for email i+1 from your queue and navigate to it.
- Do NOT go back to the search results page between emails. Navigate directly URL to URL.

---

## Extraction Rules

From each PDF, extract **every individual lab test row** as a separate result item.

For each row:
- **test_name**: the name of the test as it appears in the document (e.g. גלוקוז, Glucose, המוגלובין)
- **value**: the numeric result value (as a string, e.g. "154", "5.6")
- **unit**: the unit of measurement (e.g. mg/dL, g/dL, mmol/L — empty string if not shown)
- **date**: the date of the test (format as found, e.g. 12.05.2026)
- **time**: the time of collection (empty string if not available)
- **reference_range**: the normal range shown next to the result (e.g. "70–100" — empty string if not shown)
- **source_email**: the subject line of the email this PDF came from

**Filter rule:** {test_filter}
- If `test_filter` is "all" or empty: include every test result found in every PDF.
- Otherwise: include only results where `test_name` matches or is closely related to the specified filter (e.g. if filter is "סוכר" or "גלוקוז", include only glucose/sugar rows).

**Duplicate rule:** A single PDF may contain multiple test results from the same date — include each one as a separate row. Two results with the same test name, date, time, and value are duplicates — include only once.

---

## Phase 3 — Done

After processing all emails in your queue (or when fewer than 10 steps remain):
Call `done()` with all collected lab results. Include in the `log` field a summary of which emails were processed and which PDFs were skipped.

**Critical rule — no intermediate files:** Do NOT write any data to files during the run. Do not create `lab_results.jsonl`, `todo.md`, or any other file. Accumulate all extracted results in memory only. The output is delivered entirely through the `done()` action's structured fields.

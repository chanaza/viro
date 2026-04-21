---
name: research-navigation
description: >
  Navigation rules for research agents browsing multiple web sources sequentially.
  This is a base skill — it is not matched directly but required by research skills.
---

**Navigation Rules — Identify the component type and determine how to act:**
1. **Combobox / dropdown** — All items are in DOM memory from the moment it opens: extract immediately and finish.
   If the page also contains a table or list with the same relevant data, prefer the combobox — extraction is simpler (no pagination or scrolling required).
   For a native `<select>` element with many options: use `evaluate` with `Array.from(element.options).map(o => o.text)` to read all options as plain text. Call `done()` in the **next step** using the data from the action result — not in the same step as the evaluate.
2. **List with a "Load more" button ("טען עוד" / "הצג עוד תוצאות")** — Click the button in a loop until it disappears, then extract.
3. **Infinite scroll** — Items load as you scroll: scroll down in a loop until no new items appear, then extract.
4. **Regular rendered list** (search results, already-loaded cards) — Extract directly from the existing DOM.
For paginated content ("הבא" button / page numbers): navigate in ascending order to the end, do not skip, do not go back.

**Switching between sites:** Navigate directly to the next site in the current tab (new_tab: False). Do not close tabs and open new ones — this may crash the browser.

**Extracting data from a page:**
- **Exception — combobox/dropdown present:** If a combobox or dropdown with relevant data is visible on the page, skip `extract` entirely and follow Navigation Rule #1 (combobox path) directly.
- Otherwise: Always try `extract` first — even when you already have information from find_elements about the DOM structure.
- If extract returned completely empty — one single `evaluate` attempt is allowed.
- `evaluate` returning `[]` or an error = move immediately to the next site. Any additional `evaluate` attempt is strictly forbidden, no exceptions.
- Partial result (some fields empty) = full success. Accumulate the data and move immediately to the next site. Do not attempt to improve a result that was already received. Do not combine data from different elements on the same page.

**Stop rule (after each site):**
- Failed, blocked, or no results → next site in the prescribed sequence.
- Results found → follow the collection policy in your system instructions.
- "Next site" = strictly the next item in the task's list. No alternatives, no skips, no invented sites.

**General rules:**
- Do not create todo.md, planning, or tracking files. If you tried to create a file and failed — ignore the failure and continue directly with the task.
- At the end of collection — call `done()` directly with all collected data. Do not save data to files during the run.

# Viro — Your Browser-Native Research Agent

Viro is an AI agent that researches the web the way a human researcher would. Instead of generating answers from memory, it opens a real browser, navigates to the relevant sites, reads through the pages, and extracts exactly the data you need — structured and ready to use.

Watch it work in real time. Pause it. Give it new instructions. Every result comes from a page it actually visited.

---

## What Viro Can Do

- **Navigate complex sites** — clicks buttons, fills forms, follows pagination, handles dropdowns and multi-step flows
- **Read everything** — scrolls long pages to the end, downloads and reads files (CSV, PDF), accesses sites where you're already logged in using your own browser session
- **Extract structured data** — saves results as CSV, not just free-text summaries
- **Follow repeatable workflows (Skills)** — define exactly which sources to check, in what order, and what to extract; get consistent results every time
- **Stay in your control** — pause anytime, inject new instructions, solve CAPTCHAs manually, approve or reject flagged actions

---

## Installation

1. Download `Viro_Setup.exe` from the [Releases](../../releases) page
2. Run the installer — it sets up everything automatically (first run takes a few minutes)
3. Launch Viro from the desktop shortcut

---

## First-Time Setup

On first launch, open **Settings** (⚙️, top right) and enter your AI model credentials:

| Provider | Cost | Where to get a key |
|---|---|---|
| **Google Gemini** | Free tier available | [aistudio.google.com](https://aistudio.google.com) |
| **Groq** | Free, no credit card | [console.groq.com](https://console.groq.com) |
| **OpenAI** | Paid | [platform.openai.com](https://platform.openai.com) |
| **Anthropic** | Paid | [console.anthropic.com](https://console.anthropic.com) |

**Recommended starting point:** Gemini 2.5 Flash — best balance of speed, capability, and cost.

---

## Using Viro

Type your research task in the chat box and press Enter. A browser window opens and Viro starts working.

**Example tasks:**
- `מצא את כל סניפי רמי לוי`
- `Find all branches of Rami Levy with addresses`

While Viro works, you can:
- **Pause** — stop the agent and type new instructions mid-task
- **Resume** — continue from where it stopped
- **Stop** — end the session immediately

Results are saved automatically when the task completes (see [Output Files](#output-files)).

---

## Settings

| Setting | Description |
|---|---|
| **Agent model** | The AI model used for browsing and extraction |
| **Orchestrator model** | AI model used for understanding your request and deciding the approach (defaults to agent model) |
| **Max steps** | Maximum number of browser actions per task |
| **Browser profile** | Which browser profile to use — gives Viro access to your logged-in sessions |
| **Flash mode** | Faster, lighter browsing for simpler tasks |
| **Headless** | Run the browser in the background without a visible window |
| **Keep browser open** | Leave the browser open after the task completes |
| **Save full results** | Save detailed action logs and URL lists in addition to results |
| **Allowed / Prohibited domains** | Restrict which sites Viro may visit |
| **Security Judge** | A second AI model that reviews each planned action before it runs |

---

## Skills

Skills are repeatable research workflows. Each skill tells Viro which sources to check, in what order, and exactly what to extract — so you get consistent results every time, not a different approach on every run.

Viro detects automatically which skill to use based on your request.

### Example Skill (pre-installed): Israeli Retail Branches

Viro comes with one example skill installed out of the box. Send a request like:

> `מצא את כל סניפי רמי לוי`

Viro will check the chain's official site, the government price transparency portal, Facebook/Instagram, aggregator sites, and Google — and save a CSV with every branch's name, address, and city.

### Build Your Own

Use the **Skills Builder** (📋 in the header) to create skills for your own use cases — no coding required:

| Example request | Output |
|---|---|
| `Track prices for iPhone 16 on 3 sites` | CSV: site, price, availability |
| `Find all open tenders on mr.gov.il` | CSV: tender name, deadline, issuing body |
| `Collect contact info for these 20 companies` | CSV: email, phone, address |

For each skill: describe what request triggers it, give Viro step-by-step instructions, and define which columns to save.

---

## Output Files

Results are saved to `C:\Users\<you>\.viro\sessions\` with a `{timestamp}_{skill}_{subject}` prefix.

| File | Contents |
|---|---|
| `_result.csv` | Extracted data (e.g. branch list) |
| `_sources.csv` | Log of sources visited — URL, found/not found, count |
| `_answer.md` | Final answer in plain text |
| `_steps.md` | Step-by-step log of what Viro did |

Additional files saved when **Save full results** is enabled in Settings:

| File | Contents |
|---|---|
| `_actions.csv` | Full action history |
| `_urls.txt` | All unique URLs visited |

---

## Security & Privacy

**Your data stays on your machine.** Viro runs entirely locally — no data is sent to any third party beyond the AI model API calls you configure.

| Feature | How it works |
|---|---|
| **Sensitive data vault** | Store credentials (passwords, tokens) in Viro's local vault. The agent receives only the key names, never the values — secrets are never written to logs or prompts. |
| **Security Judge** | Configure a second AI model to review every planned action before it executes. Actions are classified as OK, WARNING (paused for your approval), or CRITICAL (agent stopped immediately). You define the policy in plain text: what Viro may do and what it must never do. |
| **Allowed / Prohibited domains** | Whitelist or blacklist specific domains to keep Viro within your intended scope. |
| **Manual login** | For sites you'd rather Viro not log into on its own — handle the login yourself in the visible browser window, then let Viro continue from there. |

---
---

## For Developers

### Installation from Source

**Prerequisites:** Python 3.11+, an AI model API key, Playwright

```bash
git clone https://github.com/chanaza/viro.git
cd viro
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
playwright install chromium
```

**Configure credentials** — copy `.env.example` to `.env`:

```dotenv
# Option 1 — Gemini API key
GEMINI_API_KEY=AIza...

# Option 2 — Google Vertex AI
GOOGLE_CLOUD_PROJECT=my-project
LLM_LOCATION=europe-west3
```

---

### Running

**Chat UI:**
```bash
.venv\Scripts\python run_app.py
```

**CLI:**
```bash
.venv\Scripts\python cli\main.py
```

Configure via `cli/.env`:

```dotenv
SUBJECT=שופרסל
SKILLS=branches
TASK={subject}
COLLECT_ALL=false
BROWSER_PROFILE=
MAX_STEPS=100
```

CLI output is saved to `cli/output/`.

---

### Supported Models

| Provider | Models | Env var |
|---|---|---|
| **Google Gemini** | gemini-2.5-flash *(default)*, gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro/flash | `GEMINI_API_KEY` or Vertex AI |
| **Groq** | llama-3.3-70b, llama-4-scout, qwen3-32b, kimi-k2, llama-3.1-8b | `GROQ_API_KEY` |
| **OpenAI** | gpt-4o, gpt-4o-mini, o3-mini | `OPENAI_API_KEY` |
| **Anthropic** | claude-3.5-sonnet, claude-3.5-haiku, claude-3.7-sonnet | `ANTHROPIC_API_KEY` |

---

### Creating Skills in Code

Skills live in `skills/`. Each skill is a folder with a `SKILL.md`:

```
skills/
└── my-skill/
    ├── SKILL.md
    └── output_schema.py   # optional — enables CSV export
```

**Minimal `SKILL.md`:**

```markdown
---
name: my-skill
description: >
  What this skill does and when to use it.
  Keywords that trigger it: "keyword1", "keyword2".
parameters:
  subject:
    type: string
    description: The main subject to research
    extract_from_request: true
goal: 'Research {subject} and find ...'
---

Step-by-step instructions for the agent.
Tell it which sites to visit, in what order, and what to extract.
```

**With structured output** (for CSV export), add `output_schema.py`:

```python
from core.models import SkillOutputModel
from pydantic import BaseModel

class MyResult(BaseModel):
    name: str
    value: str | None = None
    source: str

class MyResultList(SkillOutputModel):
    items: list[MyResult]
```

Then reference it in the `SKILL.md` frontmatter: `output_schema: MyResultList`

---

### Project Structure

```
viro/
├── run_app.py              ← Start the chat UI
├── config.py               ← Agent behavior constants
├── requirements.txt
│
├── core/                   ← Shared utilities (LLM factory, profiles, prompts)
├── agent_service/          ← Agent orchestration, security judge, output saving
├── skills/                 ← Skill definitions and output schemas
│   ├── research-navigation/   ← Base navigation rules (used by all skills)
│   └── branches/              ← Israeli retail branches skill
├── app/                    ← Chat UI (FastAPI + vanilla JS + SSE)
├── cli/                    ← CLI entry point
└── installer/              ← Windows installer (Inno Setup)
```

### Architecture

```
core/           ← shared utilities — no app-level dependencies
skills/         ← skill definitions, output schemas, context renderers
agent_service/  ← business logic: browser-use Agent + orchestration
app/            ← UI layer: FastAPI server, chat adapter, settings
cli/            ← CLI consumer
```

**Responsibility boundaries:**
- `AgentService` — thin wrapper around browser-use Agent; emits: `step`, `done`, `stopped`, `error`
- `AgentOrchestrator` — routing (BROWSE/ANSWER), skill resolution, security judge, response saving; emits: `skill_matched`, `step`, `security_*`, `done`, `stopped`, `error`
- `ChatBrowserAgent` — UI adapter: conversation history, relays events to SSE queue

---

## License

MIT

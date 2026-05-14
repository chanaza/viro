# Viro — Your Browser-Native Researcher Agent

> Grounds every answer in real web data. Secure, transparent, and human-in-the-loop.

Viro is an AI-powered research agent that runs on **your own browser**. It navigates the web the way a human researcher would — clicking through complex pages, scrolling to the end, downloading files and reading them, filling in search forms, and following multi-step flows to reach the data that matters. Every result comes from a real page it visited.

Viro is available in two modes:
- **Windows installer** — for end users, no setup required
- **Python source** — for developers and automation pipelines (CLI + UI)

---

## Key Capabilities

- **Navigates complex sites** — clicks buttons, scrolls, follows pagination, handles dropdowns and multi-step flows
- **Reads everything** — scrolls to the end of long pages, downloads files (CSV, PDF) and reads their contents
- **Browser-native sessions** — uses your actual browser profile, so it can access sites where you're already logged in
- **Structured output** — extracts data into CSV / JSON via predefined schemas, not just free-text summaries
- **Skills** — repeatable, deterministic research workflows; the agent follows them step by step
- **Human-in-the-loop** — pause, inject instructions, approve/reject actions, or solve CAPTCHAs manually
- **Transparent** — watch the browser in real time; every step is logged
- **Local** — runs on your machine; your data never leaves

---

## Security

Viro is designed so you stay in control at all times:

- **Security Judge** — optionally configure an LLM that reviews every planned action before it executes. Actions are classified as OK, WARNING (paused for your approval), or CRITICAL (agent stopped immediately). You define the policy in plain text: what the agent may do and what it must never do.
- **Sensitive data vault** — store credentials and secrets in `core/config/sensitive_data.json` (never committed to git). The agent receives only the key names, never the values — secrets are injected at runtime and never exposed in logs or prompts.
- **Human-in-the-loop on sensitive sites** — for sites you don't want the agent to log into on its own, you can work alongside it: you handle the login manually in the visible browser window, and the agent continues from there.
- **Allowed / prohibited domains** — whitelist or blacklist specific domains so the agent never strays outside your intended scope.
- **No cloud** — the agent runs entirely on your machine. No data is sent to any third-party service beyond the LLM API calls you configure.

---

## Installation — End Users (Windows)

Download and run `Viro_Setup.exe` from the [Releases](../../releases) page.

The installer sets everything up automatically. When it finishes, double-click the **Viro** icon on your desktop to launch.

**First launch:** The Viro window opens and walks you through configuring your AI model credentials.

---

## Installation — Developers

### Prerequisites

- Python 3.11+
- An AI model API key (see [Supported Models](#supported-models))
- [Playwright](https://playwright.dev/) browsers installed

### Setup

```bash
git clone https://github.com/chanaza/viro.git
cd viro
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
playwright install chromium
```

### Configure credentials

Copy `.env.example` to `.env` and fill in your credentials:

```bash
copy .env.example .env
```

```dotenv
# Option 1 — Gemini API key (free tier available)
GEMINI_API_KEY=AIza...

# Option 2 — Google Vertex AI
GOOGLE_CLOUD_PROJECT=my-project
LLM_LOCATION=europe-west3
```

See [Supported Models](#supported-models) for other providers (Groq, OpenAI, Anthropic).

---

## Running Viro

### Chat UI (recommended for end users)

```bash
.venv\Scripts\python run_app.py
```

This starts the local server and opens the Viro window automatically in Microsoft Edge.

### CLI (for developers and automation)

```bash
.venv\Scripts\python cli\main.py
```

Configure the task via `cli/.env`:

```dotenv
SUBJECT=שופרסל
SKILLS=branches
TASK={subject}
COLLECT_ALL=false
BROWSER_PROFILE=
MAX_STEPS=100
```

Output files are saved to `cli/output/`.

---

## Skills — Research Workflows

Skills are the core of Viro. A Skill is a predefined research workflow that tells the agent **exactly where to look, in what order, and what to extract**. Instead of letting the model decide freely (which leads to inconsistent results), Skills give you repeatable, reliable research pipelines.

### How Skills Work

When you send a task, Viro automatically detects which Skill applies (based on keywords in your request) and activates it. The Skill provides:

- **A goal** — what to find
- **A step-by-step strategy** — which sources to check, in what order
- **An output schema** — the structured fields to extract (e.g. name, address, city)

### Skills Builder (UI)

Non-technical users can create, edit, and disable skills directly from the Viro interface — no coding required. Click the **Skills** button (📋) in the header to open the Skills Builder.

The form uses plain language:
- **Skill name** — a short name for the skill
- **When should Viro use this?** — describe what kind of request triggers it
- **What should Viro look for?** — the main subject (e.g. "the company name")
- **Step-by-step instructions** — tell Viro exactly what to do
- **What columns do you want in the results?** — define the output fields (saved to CSV)

Built-in skills are visible in the list but their core settings are fixed. Custom skills can be fully edited or disabled at any time.

### Built-in Skills

#### `branches` — Israeli Retail Chain Branches
Finds all branches of an Israeli retail chain (name, address, city) from up to 5 sources:
1. The chain's official website
2. Price transparency portal
3. Business platforms (Facebook, Instagram)
4. Aggregators (easy.co.il, Google Maps, d.co.il, etc.)
5. Google search results

**Example task:** `מצא את כל סניפי רמי לוי`

#### `research-navigation` (base skill)
Navigation rules used internally by all research skills. Not invoked directly.

### Creating Your Own Skills

Skills live in the `skills/` directory. Each skill is a folder containing a `SKILL.md` file:

```
skills/
└── my-skill/
    └── SKILL.md
```

**Minimal `SKILL.md` structure:**

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
Tell it exactly which sites to visit, in what order,
and what data to extract from each.
```

**With structured output** (for CSV export), add an `output_schema.py` alongside `SKILL.md`:

```python
from core.models import SkillOutputModel
from pydantic import BaseModel
from typing import Optional

class MyResult(BaseModel):
    name: str
    value: Optional[str] = None
    source: str

class MyResultList(SkillOutputModel):
    items: list[MyResult]
```

Then reference it in the SKILL.md frontmatter: `output_schema: MyResultList`

---

## Supported Models

Viro supports multiple AI providers. Configure credentials in Settings (UI) or `.env` (CLI).

| Provider | Models | Notes |
|---|---|---|
| **Google Gemini** | gemini-2.5-flash *(default)*, gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro/flash | Via API key or Vertex AI |
| **Groq** 🆓 | llama-3.3-70b, llama-4-scout, qwen3-32b, kimi-k2, llama-3.1-8b | Free tier available |
| **OpenAI** | gpt-4o, gpt-4o-mini, o3-mini | Requires API key |
| **Anthropic** | claude-3.5-sonnet, claude-3.5-haiku, claude-3.7-sonnet | Requires API key |

**Recommended starting point:** Gemini 2.5 Flash (best balance of speed, capability, and cost).

**Free option:** Any Groq model — no cost, just sign up at [console.groq.com](https://console.groq.com).

---

## Settings (UI)

Open Settings via the ⚙️ icon in the top-right corner.

| Setting | Description |
|---|---|
| **Agent model** | The LLM used for browsing and extraction |
| **Orchestrator model** | LLM used for routing and direct answers (defaults to agent model) |
| **Max steps** | Maximum number of browser actions per task |
| **Browser profile** | Which browser profile to use (uses your logged-in sessions) |
| **Flash mode** | Faster, lighter browsing for simple tasks |
| **Headless** | Run browser without a visible window |
| **Keep browser open** | Keep the browser open after the task completes |
| **Allowed / Prohibited domains** | Whitelist or blacklist specific domains |
| **Advanced Security** | Configure a Security Judge LLM to approve/reject agent actions |

---

## Human-in-the-Loop

Viro is designed for transparency and control:

- **Watch it work** — the browser window is visible by default; you can see every page the agent visits
- **Pause / Resume** — pause at any time and inject new instructions
- **Stop** — stop the agent immediately
- **Security Judge** — optionally configure an LLM that reviews each action before it's executed; you approve or reject flagged actions
- **CAPTCHA assistance** — if the agent hits a CAPTCHA it can't solve, you can solve it manually and the agent continues

---

## Output Files

Results are saved to `~/.viro/sessions/` (UI) or `cli/output/` (CLI).

Each run produces files with a `{timestamp}_{skill}_{subject}` prefix:

| File | Contents |
|---|---|
| `_result.csv` | Extracted data (e.g. branch list) |
| `_sources.csv` | Log of sources visited (URL, found/not found, count) |
| `_actions.csv` | Full action history of the agent |
| `_urls.txt` | All unique URLs visited |
| `_answer.md` | Final answer in human-readable Markdown |
| `_steps.md` | Step-by-step log of what the agent did |

---

## Project Structure

```
viro/
├── run_app.py              ← Start the chat UI
├── config.py               ← Agent behavior constants
├── requirements.txt
│
├── core/                   ← Shared utilities (LLM, profiles, prompts)
├── agent_service/          ← Agent orchestration, security, output saving
├── skills/                 ← Research skill definitions
│   ├── research-navigation/   ← Base navigation rules
│   └── branches/              ← Israeli retail branches skill
├── app/                    ← Chat UI (FastAPI + vanilla JS)
├── cli/                    ← CLI entry point
└── installer/              ← Windows installer (Inno Setup)
```

---

## License

MIT

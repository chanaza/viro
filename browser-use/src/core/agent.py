import asyncio
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import unquote

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.llm.google.chat import ChatGoogle

from src.config import LLM_MAX_OUTPUT_TOKENS
from src.core.models import SourceLog

_PROMPTS = Path(__file__).parent / "prompts"


class ResearchAgent(ABC):
    """Base class for all browser-based research agents.

    Subclasses must define:
        - research_type       (str property)
        - goal                (str property)
        - output_model_schema (Pydantic model class property)
        - build_task()        (returns the full task prompt)

    Run the research with:
        agent = YourResearchAgent(subject="your subject", output_dir="output")
        result = agent.run()
    """

    thinking_budget = 0
    browser_args    = ["--ignore-certificate-errors"]

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self, subject: str, output_dir: str):
        if sys.platform == "win32":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        self._subject    = subject
        self._output_dir = output_dir
        self._prefix     = f"{subject}_{self.research_type}"

        os.makedirs(output_dir, exist_ok=True)

        self._llm = ChatGoogle(
            model=os.getenv("GEMINI_MODEL"),
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("LLM_LOCATION"),
            vertexai=True,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            thinking_budget=self.thinking_budget,
        )
        self._browser_profile = BrowserProfile(args=self.browser_args)
        self._agent = Agent(
            task=self.build_task(),
            llm=self._llm,
            output_model_schema=self.output_model_schema,
            file_system_path=output_dir,
            browser_profile=self._browser_profile,
        )

    # ── Task assembly ─────────────────────────────────────────────────────────

    def _build_task(self, specific_instructions: str) -> str:
        """Assembles the full task prompt: preamble + navigation rules + specific instructions."""
        preamble   = (_PROMPTS / "preamble.txt").read_text(encoding="utf-8")
        navigation = (_PROMPTS / "navigation.txt").read_text(encoding="utf-8")
        return f"""{preamble.format(goal=self.goal)}
{navigation}

{specific_instructions}"""

    # ── Abstract interface ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def research_type(self) -> str: ...

    @property
    @abstractmethod
    def goal(self) -> str: ...

    @property
    @abstractmethod
    def output_model_schema(self): ...

    @abstractmethod
    def build_task(self) -> str: ...

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self):
        """Runs the full research pipeline and returns the result."""
        result = asyncio.run(self._agent.run())
        print(result.final_result() or "")
        self._save_log_csv(result)
        self._save_history(result)
        self._save_urls(result)
        self._save_domain_data(result)
        return result

    # ── Generic save methods ──────────────────────────────────────────────────

    def print_log(self, result) -> None:
        log = self._extract_log(result)
        if not log:
            return
        print("\n📋 Source log:")
        for entry in log:
            if not entry.visited:
                icon, status = "⬛", "not reached"
            elif entry.found:
                icon, status = "✅", f"found {entry.count} items"
            else:
                icon, status = "❌", "no results found"
            notes = f" — {entry.notes}" if entry.notes else ""
            print(f"  {icon} {entry.source:<35} {status}{notes}")

    def _save_domain_data(self, result) -> None:
        """Writes structured output items to CSV. Override for non-standard output formats."""
        structured = self._extract_structured_output(result)
        if not structured or not structured.items:
            print("\n⚠️  No structured data extracted")
            return
        path = os.path.join(self._output_dir, f"{self._prefix}.csv")
        with open(path, "w", encoding="utf-8-sig") as f:
            headers = list(structured.items[0].model_fields.keys())
            f.write(",".join(headers) + "\n")
            for item in structured.items:
                values = [str(getattr(item, h, "")).replace('"', '""') for h in headers]
                f.write(",".join(f'"{v}"' for v in values) + "\n")
        print(f"\n✅ Saved: {path} ({len(structured.items)} items)")

    def _save_log_csv(self, result) -> None:
        log = self._extract_log(result)
        if not log:
            return
        path = os.path.join(self._output_dir, f"{self._prefix}_log.csv")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("source,visited,found,count,notes\n")
            for entry in log:
                source = entry.source.replace('"', '""')
                notes  = entry.notes.replace('"', '""')
                f.write(f'"{source}",{entry.visited},{entry.found},{entry.count},"{notes}"\n')
        print(f"✅ Log saved: {path}")

    def _save_history(self, result) -> None:
        path = os.path.join(self._output_dir, f"{self._prefix}_history.csv")
        try:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("step,action,details,error,extracted\n")
                for step_i, step in enumerate(result.history, start=1):
                    actions = step.model_output.action if step.model_output else []
                    results = step.result or []
                    for act_i, (action, res) in enumerate(zip(actions, results)):
                        action_dict = action.model_dump(exclude_none=True)
                        action_name = next(iter(action_dict), "unknown")
                        details     = str(list(action_dict.values())[0]) if action_dict else ""
                        error       = (res.error or "").replace('"', '""')[:200]
                        extracted   = (res.extracted_content or "").replace('"', '""')[:300]
                        details_esc = details.replace('"', '""')[:200]
                        f.write(f'{step_i}.{act_i+1},"{action_name}","{details_esc}","{error}","{extracted}"\n')
            print(f"✅ History saved: {path} ({len(result.history)} steps)")
        except Exception as e:
            print(f"⚠️  Error saving history: {e}")

    def _save_urls(self, result) -> None:
        try:
            all_urls = [u for u in (result.urls() or []) if u]
            seen, unique_urls = set(), []
            for u in all_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)
            path = os.path.join(self._output_dir, f"{self._prefix}_urls.txt")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(unquote(u) for u in unique_urls))
            print(f"✅ URLs saved: {path} ({len(unique_urls)} unique)")
        except Exception as e:
            print(f"⚠️  Error saving URLs: {e}")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_structured_output(self, result):
        """Tries get_structured_output first; falls back to regex JSON parse from final_result."""
        try:
            output = result.get_structured_output(self.output_model_schema)
            if output:
                return output
        except Exception:
            pass
        final_text = result.final_result() or ""
        match = re.search(r'\{[\s\S]*\}', final_text)
        if match:
            try:
                return self.output_model_schema.model_validate_json(match.group())
            except Exception:
                pass
        return None

    def _extract_log(self, result) -> list[SourceLog] | None:
        structured = self._extract_structured_output(result)
        return structured.log if structured else None

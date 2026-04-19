"""SkillRegistry — discovers, loads, matches, and builds prompts for skills."""
import importlib.util
import json
import re
import types
from pathlib import Path

import yaml

from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage

from core.models import Skill, SkillMatch, SkillPreset
from core.prompts import SKILL_MATCH_PROMPT

_DEFAULT_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillRegistry:
    """Discovers all SKILL.md files, matches requests to skills, builds prompts, saves results."""

    def __init__(self, skills_dir: Path = _DEFAULT_SKILLS_DIR) -> None:
        self._skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}
        self.load_all()

    # ── Discovery ─────────────────────────────────────────────────────────────

    def load_all(self) -> None:
        """Scan the skills directory tree and load every SKILL.md found."""
        self._skills = {}
        for skill_md in sorted(self._skills_dir.rglob("SKILL.md")):
            try:
                skill = self._load_skill(skill_md.parent)
                self._skills[skill.name] = skill
            except Exception:
                pass  # malformed skill — skip silently

    def _load_skill(self, skill_dir: Path) -> Skill:
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)

        # Dynamically load output schema class (e.g. BranchList)
        output_schema_class = None
        output_schema_name  = fm.get("output_schema")
        if output_schema_name:
            schema_path = skill_dir / "output_schema.py"
            if schema_path.exists():
                mod = _load_module("output_schema", schema_path)
                output_schema_class = getattr(mod, output_schema_name, None)

        # Load public string variables from config.py as template context
        static_context: dict[str, str] = {}
        config_path = skill_dir / "config.py"
        if config_path.exists():
            mod = _load_module("config", config_path)
            static_context = {
                k: v for k, v in vars(mod).items()
                if not k.startswith("_") and isinstance(v, str)
            }

        skill = Skill(
            name            = fm["name"],
            description     = fm.get("description", "").strip(),
            parameters      = fm.get("parameters", {}) or {},
            goal_template   = fm.get("goal"),
            base_skills     = fm.get("requires", []) or [],
            prompt_template = body,
        )
        skill._output_schema_class = output_schema_class
        skill._static_context      = static_context
        return skill

    # ── Intent matching ───────────────────────────────────────────────────────

    async def find(
        self,
        request: str,
        llm: BaseChatModel,
        system_msg: SystemMessage | None = None,
    ) -> list[SkillMatch]:
        """Ask the LLM which skills are relevant to the request; extract params for each."""
        if not self._skills:
            return []

        lines = []
        for s in self._skills.values():
            line = f'- "{s.name}": {s.description}'
            if s.parameters:
                plist = ", ".join(
                    f'{k} ({v.get("description", k)})'
                    for k, v in s.parameters.items()
                )
                line += f"\n  Parameters: {plist}"
            lines.append(line)

        prompt = SKILL_MATCH_PROMPT.format(
            skill_list="\n".join(lines),
            request=request,
        )
        messages: list = []
        if system_msg:
            messages.append(system_msg)
        messages.append(UserMessage(content=prompt))

        try:
            response = await llm.ainvoke(messages)
            raw = response.completion.strip()
            m   = re.search(r'\[.*\]', raw, re.DOTALL)
            if not m:
                return []
            data: list = json.loads(m.group())
        except Exception:
            return []

        matches = []
        for entry in data:
            name = entry.get("skill")
            if name and name in self._skills:
                matches.append(
                    SkillMatch(skill=self._skills[name], params=entry.get("params") or {})
                )
        return matches

    # ── Prompt assembly ───────────────────────────────────────────────────────

    def build_prompt(self, matches: list[SkillMatch]) -> str:
        """Assemble combined task prompt from all matched skills.

        Structure: all goals → shared base skills (deduplicated) → all skill bodies.
        """
        parts: list[str] = []
        seen_base: set[str] = set()

        for match in matches:
            skill  = match.skill
            context: dict = dict(match.params)
            context.update(skill._static_context)

            if skill.goal_template:
                parts.append(_render(skill.goal_template, context))

            for base_name in skill.base_skills:
                if base_name in seen_base:
                    continue
                seen_base.add(base_name)
                base = self._skills.get(base_name)
                if base:
                    parts.append(_render(base.prompt_template, context))

            parts.append(_render(skill.prompt_template, context))

        return "\n\n".join(parts)

    def output_schema(self, matches: list[SkillMatch]) -> type | None:
        """Return output schema class of the first match that has one, or None."""
        for match in matches:
            if match.skill._output_schema_class is not None:
                return match.skill._output_schema_class
        return None

    def resolve_presets(self, presets: list[SkillPreset]) -> list[SkillMatch]:
        """Resolve SkillPreset (name + params) to SkillMatch using the loaded skills."""
        return [
            SkillMatch(skill=self._skills[p.name], params=p.params)
            for p in presets
            if p.name in self._skills
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter (between --- delimiters) from markdown body."""
    if text.startswith("---"):
        end = text.index("---", 3)
        fm   = yaml.safe_load(text[3:end]) or {}
        body = text[end + 3:].strip()
    else:
        fm   = {}
        body = text.strip()
    return fm, body


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _render(template: str, context: dict) -> str:
    """format_map with safe fallback: unknown {keys} are left as-is."""
    try:
        return template.format_map(_SafeDict(context))
    except Exception:
        return template


class _SafeDict(dict):
    """Returns '{key}' for any missing key so unknown placeholders survive rendering."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"

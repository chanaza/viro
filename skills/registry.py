"""SkillRegistry — discovers, loads, matches, and builds prompts for skills."""
import importlib.util
import json
import re
from pathlib import Path

import yaml

from skills.models import Skill, SkillMatch
from browser_use.llm.messages import SystemMessage, UserMessage

_SKILLS_DIR = Path(__file__).parent

_MATCH_PROMPT = """\
Available specialized skills:
{skill_list}

Does the following user request match one of the skills above?
- If yes: identify the skill name and extract the required parameters from the request.
- If no: return null for skill.

Reply with JSON only — no other text:
Match:    {{"skill": "skill-name", "params": {{"param_name": "value"}}}}
No match: {{"skill": null}}

User request: {request}
"""


class SkillRegistry:
    """Discovers all SKILL.md files, matches requests to skills, builds prompts, saves results."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self.load_all()

    # ── Discovery ─────────────────────────────────────────────────────────────

    def load_all(self) -> None:
        """Scan the skills directory tree and load every SKILL.md found."""
        self._skills = {}
        for skill_md in sorted(_SKILLS_DIR.rglob("SKILL.md")):
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

        # Dynamically load render_context.py if present
        render_context_fn = None
        ctx_path = skill_dir / "render_context.py"
        if ctx_path.exists():
            mod = _load_module("render_context", ctx_path)
            render_context_fn = getattr(mod, "get_context", None)

        skill = Skill(
            name               = fm["name"],
            description        = fm.get("description", "").strip(),
            skill_type         = fm.get("type", "research"),
            requires           = fm.get("requires", []) or [],
            parameters         = fm.get("parameters", {}) or {},
            goal_template      = fm.get("goal"),
            stop_rule          = fm.get("stop_rule"),
            output_schema_name = output_schema_name,
            body               = body,
            path               = skill_dir,
        )
        skill._output_schema_class = output_schema_class
        skill._render_context_fn   = render_context_fn
        return skill

    # ── Intent matching ───────────────────────────────────────────────────────

    async def find(self, request: str, llm, system_msg=None) -> SkillMatch | None:
        """Ask the LLM whether the request matches a known skill; extract params if yes."""
        active = {name: s for name, s in self._skills.items() if s.skill_type != "base"}
        if not active:
            return None

        lines = []
        for s in active.values():
            line = f'- "{s.name}": {s.description}'
            if s.parameters:
                plist = ", ".join(
                    f'{k} ({v.get("description", k)})'
                    for k, v in s.parameters.items()
                )
                line += f"\n  Parameters: {plist}"
            lines.append(line)

        prompt = _MATCH_PROMPT.format(
            skill_list="\n".join(lines),
            request=request,
        )
        messages = []
        if system_msg:
            messages.append(system_msg)
        messages.append(UserMessage(content=prompt))

        try:
            response = await llm.ainvoke(messages)
            raw = response.completion.strip()
            m   = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group())
        except Exception:
            return None

        skill_name = data.get("skill")
        if not skill_name or skill_name not in self._skills:
            return None

        return SkillMatch(skill=self._skills[skill_name], params=data.get("params") or {})

    # ── Prompt assembly ───────────────────────────────────────────────────────

    def build_prompt(self, match: SkillMatch, collect_all: bool = False) -> str:
        """Assemble full task prompt: goal + required base skills + skill body (all rendered)."""
        skill  = match.skill
        params = match.params

        # Build render context: start with params, add dynamic vars from render_context.py
        context: dict = dict(params)
        if skill._render_context_fn:
            context.update(skill._render_context_fn(params))

        # Resolve stop_rule text and add to context (used in research-navigation body)
        stop_rule_text = ""
        if skill.stop_rule:
            key = "collect_all" if collect_all else "stop_first"
            stop_rule_text = skill.stop_rule.get(key, "")
        context["stop_rule"] = stop_rule_text

        parts: list[str] = []

        # 1. Goal statement
        if skill.goal_template:
            parts.append(_render(skill.goal_template, context))

        # 2. Required base skills (e.g. research-navigation) — rendered in order
        for req_name in skill.requires:
            req = self._skills.get(req_name)
            if req:
                parts.append(_render(req.body, context))

        # 3. Skill body
        parts.append(_render(skill.body, context))

        return "\n\n".join(parts)

    def output_schema(self, match: SkillMatch):
        return match.skill._output_schema_class



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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
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



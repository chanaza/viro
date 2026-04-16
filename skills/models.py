"""Data models for the skill system."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class Skill:
    name:                str
    description:         str
    skill_type:          str              # "research" | "base"
    requires:            list[str]        # names of required base skills (loaded first)
    parameters:          dict             # {param_name: {type, description, extract_from_request}}
    goal_template:       str | None       # e.g. 'מצא את כל הסניפים של "{subject}"...'
    stop_rule:           dict | None      # {collect_all: "...", stop_first: "..."}
    output_schema_name:  str | None       # e.g. "BranchList"
    body:                str              # raw markdown body (after frontmatter, NOT yet rendered)
    path:                Path             # skill directory

    # Loaded at runtime — not part of the SKILL.md definition
    _output_schema_class: Any      = field(default=None, repr=False)
    _render_context_fn:   Callable = field(default=None, repr=False)


@dataclass
class SkillMatch:
    skill:  Skill
    params: dict   # extracted from the user request, e.g. {"subject": "שופרסל"}

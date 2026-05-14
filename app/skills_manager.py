"""Skills Manager — CRUD operations for skill files.

Handles reading and writing SKILL.md files in the skills/ directory.
User-created skills are stored in skills/{name}/SKILL.md.
Built-in skills (those that ship with the repo) are marked as read-only in the API
but can still be edited — they are flagged with `builtin: true` in their frontmatter
or detected by the absence of `user_created: true`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Skills that are base/utility skills — not shown as standalone in the UI
_BASE_SKILLS = {"research-navigation"}


def _skills_dir() -> Path:
    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return _SKILLS_DIR


# ── Read ──────────────────────────────────────────────────────────────────────

def list_skills() -> list[dict[str, Any]]:
    """Return all skills as a list of dicts, excluding base/utility skills."""
    result = []
    for skill_md in sorted(_skills_dir().rglob("SKILL.md")):
        try:
            skill = _read_skill(skill_md)
            if skill["name"] in _BASE_SKILLS:
                continue
            result.append(skill)
        except Exception:
            pass
    return result


def get_skill(name: str) -> dict[str, Any] | None:
    """Return a single skill by name, or None if not found."""
    path = _skill_path(name)
    if not path.exists():
        return None
    try:
        return _read_skill(path)
    except Exception:
        return None


def _read_skill(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    # Detect if this is a user-created skill
    user_created = bool(fm.get("user_created", False))

    # Parse output fields from frontmatter (user-created skills store them there)
    output_fields: list[dict[str, str]] = fm.get("output_fields", []) or []

    # Parse parameters
    raw_params = fm.get("parameters", {}) or {}
    parameters: list[dict[str, str]] = []
    for pname, pdef in raw_params.items():
        if isinstance(pdef, dict):
            parameters.append({
                "name": pname,
                "type": pdef.get("type", "string"),
                "description": pdef.get("description", ""),
            })

    return {
        "name": fm.get("name", skill_md.parent.name),
        "description": (fm.get("description") or "").strip(),
        "parameters": parameters,
        "output_fields": output_fields,
        "instructions": body,
        "active": fm.get("active", True),
        "user_created": user_created,
    }


# ── Write ─────────────────────────────────────────────────────────────────────

def create_skill(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new user skill. Raises ValueError if name already exists."""
    name = _validate_name(data["name"])
    path = _skill_path(name)
    if path.exists():
        raise ValueError(f"Skill '{name}' already exists.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_skill(path, data, user_created=True)
    return _read_skill(path)


def update_skill(name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update an existing skill (user-created or built-in)."""
    path = _skill_path(name)
    if not path.exists():
        raise ValueError(f"Skill '{name}' not found.")
    existing = _read_skill(path)
    _write_skill(path, data, user_created=existing["user_created"])
    return _read_skill(path)


def delete_skill(name: str) -> None:
    """Deactivate a skill by setting active: false. Does not delete the file."""
    path = _skill_path(name)
    if not path.exists():
        raise ValueError(f"Skill '{name}' not found.")
    skill = _read_skill(path)
    skill["active"] = False
    _write_skill(path, skill, user_created=skill["user_created"])


def _write_skill(path: Path, data: dict[str, Any], *, user_created: bool) -> None:
    name        = _validate_name(data["name"])
    description = (data.get("description") or "").strip()
    instructions = (data.get("instructions") or "").strip()
    active      = data.get("active", True)
    parameters  = data.get("parameters") or []
    output_fields = data.get("output_fields") or []

    # Build frontmatter dict
    fm: dict[str, Any] = {
        "name": name,
        "description": description,
        "active": active,
    }
    if user_created:
        fm["user_created"] = True

    # Parameters
    if parameters:
        fm["parameters"] = {
            p["name"]: {
                "type": p.get("type", "string"),
                "description": p.get("description", ""),
                "extract_from_request": True,
            }
            for p in parameters
            if p.get("name")
        }

    # Output fields (stored in frontmatter for user skills)
    if output_fields:
        fm["output_fields"] = [
            {"name": f["name"], "type": f.get("type", "text")}
            for f in output_fields
            if f.get("name")
        ]

    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    content = f"---\n{yaml_str}---\n\n{instructions}\n"
    path.write_text(content, encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _skill_path(name: str) -> Path:
    return _skills_dir() / name / "SKILL.md"


def _validate_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9\-_]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        raise ValueError("Skill name cannot be empty.")
    return name


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.index("---", 3)
        fm  = yaml.safe_load(text[3:end]) or {}
        body = text[end + 3:].strip()
    else:
        fm   = {}
        body = text.strip()
    return fm, body

# Legacy — do not use

This directory (`browser-use/src/`) is no longer active.

All logic has been migrated:

| Was here | Now in |
|----------|--------|
| `core/models.py` | `app/skills/research_models.py` |
| `core/prompts.yaml` | `app/skills/research-navigation/SKILL.md` + `app/skills/branches/SKILL.md` |
| `core/agent.py` (ResearchAgent) | `app/agent_service.py` (AgentService) + `app/skills/registry.py` |
| `branches/models.py` | `app/skills/branches/output_schema.py` |
| `branches/config.py` | `app/skills/branches/config.py` |
| `branches/task.py` | `app/skills/branches/SKILL.md` + `render_context.py` |
| `branches/agent.py` | `app/skills/registry.py` (SkillRegistry) |
| `config.py` (COLLECT_ALL) | `app/config.py` |

The CLI entry point `browser-use/main.py` now uses `app/agent_service.py` directly.

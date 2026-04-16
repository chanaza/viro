"""Generates dynamic template variables for the branches SKILL.md."""
from skills.branches.config import BUSINESS_PROFILE_PLATFORMS, TRUSTED_AGGREGATORS


def get_context(params: dict) -> dict:
    """Returns extra template vars to be merged into the render context."""
    platforms_block = ", ".join(
        f"{p['name']} ({p['domain']})" for p in BUSINESS_PROFILE_PLATFORMS
    )

    aggregators_lines = []
    for agg in TRUSTED_AGGREGATORS:
        line = f"   - {agg['domain']}"
        if agg["instructions"]:
            line += f": {agg['instructions']}"
        aggregators_lines.append(line)
    aggregators_block = "\n".join(aggregators_lines) + "\n"

    return {
        "platforms_block":   platforms_block,
        "aggregators_block": aggregators_block,
    }

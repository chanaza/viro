"""Shared data models for the core layer."""
import copy
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, Field
from pydantic.json_schema import GenerateJsonSchema


class LLMSettings(Protocol):
    """Required settings for LLM instantiation — any object with these attributes qualifies."""
    gemini_api_key:       str
    google_cloud_project: str
    llm_location:         str
    groq_api_key:         str
    openai_api_key:       str
    anthropic_api_key:    str


class ProfileDict(TypedDict):
    """Browser profile as a plain dict — returned by profile detection."""
    id:                str
    label:             str
    user_data_dir:     str
    profile_directory: str
    browser:           str
    executable:        str | None


class SourceLog(BaseModel):
    """Log entry for a single source visited during a multi-source browsing run."""
    source:  str  = Field(description="Source name or URL")
    visited: bool = Field(description="Whether the agent attempted to browse this source")
    found:   bool = Field(description="Whether usable results were found")
    count:   int  = Field(default=0,  description="Number of items found (0 if none)")
    notes:   str  = Field(default="", description="Notes: error, block, login wall, popup, reason for skipping")


# ── Skill data classes ────────────────────────────────────────────────────────

class SkillParameter(TypedDict):
    type:                 str   # e.g. "string", "int"
    description:          str   # what to extract, shown to the LLM during skill matching
    extract_from_request: bool  # True = LLM should extract this from the user's message


@dataclass
class Skill:
    name:            str
    description:     str                       # shown to LLM for skill matching
    parameters:      dict[str, SkillParameter] # params the LLM should extract from the user request
    goal_template:   str | None                # first line of the task prompt; may contain {param} placeholders
    base_skills:     list[str]                 # base skill names whose bodies are prepended to the prompt
    prompt_template: str                       # raw SKILL.md body (after frontmatter), rendered at build time

    # Loaded at runtime — not part of the SKILL.md definition
    _output_schema_class: type[Any] | None = field(default=None,         repr=False)
    _static_context:      dict[str, str]   = field(default_factory=dict, repr=False)


@dataclass
class SkillMatch:
    skill:  Skill
    params: dict[str, str]


@dataclass
class SkillPreset:
    """Caller-supplied skill selection — resolved to SkillMatch by the orchestrator."""
    name:   str
    params: dict[str, str]


# ── Skill output base model ───────────────────────────────────────────────────

def _inline_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolves all $ref/$defs in a JSON schema by inlining definitions.

    Pydantic generates $defs for nested models; browser-use requires a flat schema.
    """
    schema = copy.deepcopy(schema)
    defs   = schema.pop("$defs", {})

    def resolve(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                return resolve(copy.deepcopy(defs[ref_name]))
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(i) for i in obj]
        return obj

    return resolve(schema)


class SkillOutputModel(BaseModel):
    """Base class for all skill output schemas.

    Every skill output automatically includes a source visit log.
    Overrides model_json_schema to return an inlined schema (no $defs),
    which is required by browser-use for structured output parsing.
    """
    log: list[SourceLog] = Field(
        default=[],
        description="Log of all sources attempted — including those that failed or were blocked",
    )

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: Literal["validation", "serialization"] = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        return _inline_defs(
            super().model_json_schema(
                by_alias=by_alias,
                ref_template=ref_template,
                schema_generator=schema_generator,
                mode=mode,
                union_format=union_format,
            )
        )

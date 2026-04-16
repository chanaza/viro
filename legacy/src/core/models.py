import copy

from pydantic import BaseModel, Field


def _inline_defs(schema: dict) -> dict:
    """Resolves all $ref/$defs in a JSON schema by inlining definitions."""
    schema = copy.deepcopy(schema)
    defs   = schema.pop("$defs", {})

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                return resolve(copy.deepcopy(defs[ref_name]))
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(i) for i in obj]
        return obj

    return resolve(schema)


class ResearchModel(BaseModel):
    """Base for all research output models. Returns inlined JSON schema (no $defs)."""

    @classmethod
    def model_json_schema(cls, **kwargs):
        return _inline_defs(super().model_json_schema(**kwargs))


class SourceLog(ResearchModel):
    source:  str  = Field(description="שם המקור או URL")
    visited: bool = Field(description="האם ניסה לגלוש למקור זה")
    found:   bool = Field(description="האם נמצאו תוצאות שמישות")
    count:   int  = Field(default=0, description="מספר פריטים שנמצאו (0 אם לא נמצא)")
    notes:   str  = Field(default="", description="הערות: שגיאה, חסימה, סיסמה, popup, סיבת מעבר לאתר הבא")

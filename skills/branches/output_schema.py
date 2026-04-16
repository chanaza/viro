"""Output schema for the branches skill."""
from pydantic import Field

from skills.research_models import ResearchModel, SourceLog


class Branch(ResearchModel):
    name:    str = Field(description="שם הסניף")
    address: str = Field(default="", description="כתובת (רחוב ומספר) — ריק אם לא נמצא")
    city:    str = Field(default="", description="עיר — ריק אם לא נמצא")
    source:  str = Field(description="שם האתר שממנו נלקח הפריט")


class BranchList(ResearchModel):
    items: list[Branch]
    log:   list[SourceLog] = Field(
        default=[],
        description="לוג של כל האתרים שנוסו — כולל אלה שנכשלו",
    )

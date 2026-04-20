"""Output schema for the branches skill."""
from pydantic import BaseModel, Field

from core.models import SkillOutputModel


class Branch(BaseModel):
    name:    str = Field(description="Branch name")
    address: str = Field(default="", description="Street address — empty if not found")
    city:    str = Field(default="", description="City — empty if not found")
    source:  str = Field(description="Name of the website this item was collected from")


class BranchList(SkillOutputModel):
    items: list[Branch]

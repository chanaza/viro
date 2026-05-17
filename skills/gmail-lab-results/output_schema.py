"""Output schema for the gmail-lab-results skill."""
from pydantic import BaseModel, Field

from core.models import SkillOutputModel


class LabResult(BaseModel):
    test_name:       str = Field(description="Name of the lab test (e.g. גלוקוז, Glucose, המוגלובין)")
    value:           str = Field(description="Measured result value as a string (e.g. '154', '5.6')")
    unit:            str = Field(default="", description="Unit of measurement (e.g. mg/dL, g/dL) — empty if not shown")
    date:            str = Field(description="Date of the test as it appears in the document (e.g. 12.05.2026)")
    time:            str = Field(default="", description="Time of collection — empty if not available")
    reference_range: str = Field(default="", description="Normal reference range shown in document (e.g. 70–100) — empty if not shown")
    source_email:    str = Field(description="Subject line of the email this PDF came from")


class LabResultList(SkillOutputModel):
    items: list[LabResult]

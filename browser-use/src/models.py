from pydantic import BaseModel, Field


class Branch(BaseModel):
    name:    str = Field(description="שם הסניף")
    address: str = Field(default="", description="כתובת (רחוב ומספר) — ריק אם לא נמצא")
    city:    str = Field(default="", description="עיר — ריק אם לא נמצא")
    source:  str = Field(description="שם האתר שממנו נלקח הפריט")


class SourceLog(BaseModel):
    source:  str  = Field(description="שם המקור או URL")
    visited: bool = Field(description="האם ניסה לגלוש למקור זה")
    found:   bool = Field(description="האם נמצאו תוצאות שמישות")
    count:   int  = Field(default=0, description="מספר פריטים שנמצאו (0 אם לא נמצא)")
    notes:   str  = Field(default="", description="הערות: שגיאה, חסימה, סיסמה, popup, סיבת מעבר למקור הבא")


class BranchList(BaseModel):
    items: list[Branch]
    log:   list[SourceLog] = Field(default=[], description="לוג של כל המקורות שנוסו — כולל אלה שנכשלו")

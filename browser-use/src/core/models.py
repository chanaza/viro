from pydantic import BaseModel, Field


class SourceLog(BaseModel):
    source:  str  = Field(description="שם המקור או URL")
    visited: bool = Field(description="האם ניסה לגלוש למקור זה")
    found:   bool = Field(description="האם נמצאו תוצאות שמישות")
    count:   int  = Field(default=0, description="מספר פריטים שנמצאו (0 אם לא נמצא)")
    notes:   str  = Field(default="", description="הערות: שגיאה, חסימה, סיסמה, popup, סיבת מעבר לאתר הבא")

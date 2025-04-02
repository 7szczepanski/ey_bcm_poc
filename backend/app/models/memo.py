from typing import List, Dict, Any
from pydantic import BaseModel

class Evidence(BaseModel):
    """Evidence supporting a section of the memo."""
    source_type: str  # "standard" or "agreement"
    document_name: str
    snippet: str
    page_number: int | None = None
    relevance_score: float | None = None

class Section(BaseModel):
    """A section of the generated memo."""
    id: str
    title: str
    content: str
    evidence: List[Evidence]
    standard_topic: str | None = None
    is_complete: bool = False  # Flag indicating if the section is complete

class GeneratedMemo(BaseModel):
    """The complete generated memo."""
    title: str
    sections: List[Section]
    iteration: int = 1  # Track which iteration of the memo this is
    metadata: Dict[str, Any] = {}
    is_accepted: bool = False  # Flag indicating if memo has been accepted by user

class MemoResponse(BaseModel):
    """API response containing the generated memo and evidence."""
    memo: GeneratedMemo
    evidence: List[Evidence]
    follow_up_questions: List[str] = []  # Questions to ask the user for missing info 
from typing import List, Dict, Any
from pydantic import BaseModel

class Evidence(BaseModel):
    """Evidence supporting a section of the memo."""
    source: str  # "standard" or "agreement"
    page: int
    text: str
    relevance_score: float

class Section(BaseModel):
    """A section of the generated memo."""
    id: str
    title: str
    content: str
    evidence: List[Evidence]
    standard_topic: str | None = None

class GeneratedMemo(BaseModel):
    """The complete generated memo."""
    title: str
    sections: List[Section]
    metadata: Dict[str, Any] = {}

class MemoResponse(BaseModel):
    """API response containing the generated memo and evidence."""
    memo: GeneratedMemo
    evidence: List[Evidence] 
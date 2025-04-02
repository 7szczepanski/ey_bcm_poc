from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class ConfidenceValue(BaseModel):
    """Value with confidence level"""
    value: str = Field(..., description="The extracted value")
    confidence: str = Field(..., description="Confidence level: low, medium, or high")

class StructuredMergerData(BaseModel):
    """Structured data model for business combination memos"""
    acquisition_date: Optional[ConfidenceValue] = Field(None, description="When the acquisition occurred (specific date)")
    acquirer: Optional[ConfidenceValue] = Field(None, description="The entity acquiring control")
    acquiree: Optional[ConfidenceValue] = Field(None, description="The entity being acquired")
    consideration: Optional[ConfidenceValue] = Field(None, description="Details about payment (amount, type of consideration)")
    goodwill: Optional[ConfidenceValue] = Field(None, description="Value of goodwill recognized")
    fair_value: Optional[ConfidenceValue] = Field(None, description="Fair values of assets or liabilities")
    identifiable_assets: Optional[ConfidenceValue] = Field(None, description="Details about specific assets identified")
    liabilities: Optional[ConfidenceValue] = Field(None, description="Details about specific liabilities assumed")

class SectionCompleteness(BaseModel):
    """Model for section completeness evaluation"""
    is_complete: bool = Field(..., description="Whether the section is complete or has important gaps")
    follow_up_questions: List[str] = Field(default_factory=list, description="Specific follow-up questions to help complete this section") 
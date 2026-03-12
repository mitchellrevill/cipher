from pydantic import BaseModel, Field, model_validator
from enum import Enum

class PageProcessingStage(str, Enum):
    """Pipeline stages for a page."""
    ANALYZING_LAYOUT = "analyzing_layout"
    PII_DETECTION = "pii_detection"
    MATCHING_COORDINATES = "matching"
    COMPLETE = "complete"
    ERROR = "error"

class PageStatusEvent(BaseModel):
    """SSE event for page processing status update."""
    page_num: int
    status: PageProcessingStage
    stage_label: str  # Human-readable label
    error_message: str | None = None

    @model_validator(mode='after')
    def error_requires_message(self):
        """Require error_message when status is ERROR."""
        if self.status == PageProcessingStage.ERROR and not self.error_message:
            raise ValueError("error_message is required when status=ERROR")
        return self

class SuggestionFoundEvent(BaseModel):
    """SSE event for newly discovered or updated suggestion."""
    id: str
    text: str
    category: str
    reasoning: str
    page_nums: list[int] = Field(min_length=1)  # All pages where this suggestion was found
    first_found_on: int   # Page where first discovered

class StreamingEventPayload(BaseModel):
    """Union type for SSE event data."""
    event_type: str  # "page_status" or "suggestion_found"
    data: PageStatusEvent | SuggestionFoundEvent

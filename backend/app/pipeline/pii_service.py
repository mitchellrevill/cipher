import logging
from azure.ai.textanalytics.aio import TextAnalyticsClient
from azure.ai.textanalytics import PiiEntityCategory
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)

UK_PII_CATEGORIES = [
    PiiEntityCategory.PERSON,
    PiiEntityCategory.PHONE_NUMBER,
    PiiEntityCategory.EMAIL,
    PiiEntityCategory.ADDRESS,
    PiiEntityCategory.DATE,
    PiiEntityCategory.AGE,
    PiiEntityCategory.UK_NATIONAL_INSURANCE_NUMBER,
    PiiEntityCategory.UK_NATIONAL_HEALTH_NUMBER,
    PiiEntityCategory.ORGANIZATION,
]


class PIIServiceClient:
    """Azure Language Service client for UK-specific PII detection."""

    def __init__(self, endpoint: str, key: str):
        self._endpoint = endpoint
        self._key = key

    async def get_pii(self, text_chunk: str) -> list[dict]:
        """Extract UK PII entities. Returns [{text, category, offset, length}]."""
        try:
            async with TextAnalyticsClient(
                endpoint=self._endpoint,
                credential=AzureKeyCredential(self._key)
            ) as client:
                results = await client.recognize_pii_entities(
                    [text_chunk],
                    categories_filter=UK_PII_CATEGORIES
                )
                return [
                    {"text": e.text, "category": e.category, "offset": e.offset, "length": e.length}
                    for doc in results if not doc.is_error
                    for e in doc.entities
                ]
        except Exception:
            logger.exception("PII service error")
            return []

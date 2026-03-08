from azure.ai.textanalytics import TextAnalyticsClient, PiiEntityCategory
from azure.core.credentials import AzureKeyCredential

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
        self._client = TextAnalyticsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )

    def get_pii(self, text_chunk: str) -> list[dict]:
        """
        Extract PII entities from a text chunk.
        Returns list of {text, category, offset, length}.
        offset and length are character positions within text_chunk.
        """
        try:
            results = self._client.recognize_pii_entities(
                [text_chunk],
                categories_filter=UK_PII_CATEGORIES
            )
            return [
                {
                    "text": e.text,
                    "category": e.category,
                    "offset": e.offset,
                    "length": e.length
                }
                for doc in results if not doc.is_error
                for e in doc.entities
            ]
        except Exception as ex:
            print(f"PII service error: {ex}")
            return []

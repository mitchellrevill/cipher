from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential


class DocIntelligenceClient:
    """Async wrapper around Azure Document Intelligence for PDF layout analysis."""

    def __init__(self, endpoint: str, key: str):
        self._endpoint = endpoint
        self._key = key

    async def analyse(self, pdf_bytes: bytes):
        """
        Analyse a PDF document using the prebuilt-layout model.
        Returns an AnalyzeResult with paragraphs, pages, and word polygons.
        Makes a single API call for the entire document.
        """
        async with DocumentIntelligenceClient(
            endpoint=self._endpoint,
            credential=AzureKeyCredential(self._key)
        ) as client:
            poller = await client.begin_analyze_document(
                "prebuilt-layout",
                body=pdf_bytes,
                content_type="application/octet-stream"
            )
            return await poller.result()

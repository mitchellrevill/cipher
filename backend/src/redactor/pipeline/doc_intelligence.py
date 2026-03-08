import logging
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient as _AsyncClient
from azure.core.credentials import AzureKeyCredential

logger = logging.getLogger(__name__)


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
        try:
            async with _AsyncClient(
                endpoint=self._endpoint,
                credential=AzureKeyCredential(self._key)
            ) as client:
                poller = await client.begin_analyze_document(
                    "prebuilt-layout",
                    body=pdf_bytes,
                    content_type="application/octet-stream"
                )
                return await poller.result()
        except Exception:
            logger.exception("Document Intelligence analysis failed")
            raise  # Re-raise — caller needs to know the document couldn't be processed

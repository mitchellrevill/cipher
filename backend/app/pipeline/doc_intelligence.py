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
            logger.info(f"Starting Document Intelligence analysis: endpoint={self._endpoint}, pdf_size={len(pdf_bytes)} bytes")
            async with _AsyncClient(
                endpoint=self._endpoint,
                credential=AzureKeyCredential(self._key)
            ) as client:
                logger.info("Document Intelligence client created, beginning analysis...")
                poller = await client.begin_analyze_document(
                    "prebuilt-layout",
                    body=pdf_bytes,
                    content_type="application/octet-stream"
                )
                logger.info("Waiting for analysis result...")
                result = await poller.result()
                logger.info(f"Analysis completed: {len(result.pages or [])} pages, {len(result.paragraphs or [])} paragraphs")
                return result
        except Exception as e:
            logger.exception(f"Document Intelligence analysis failed: {type(e).__name__}: {str(e)}")
            raise  # Re-raise — caller needs to know the document couldn't be processed

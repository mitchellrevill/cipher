import json
import logging
from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)

# Prompts ported verbatim from contextual-redactor/src/redactor/azure_client.py

_INSTRUCTION_PARSE_PROMPT = """
        You are a configuration parser. Your task is to analyze the user's instructions for a document redaction tool and convert them into a structured JSON object.
        The JSON object should have two optional keys:
        1. "exceptions": A list of exact strings that the user wants to PREVENT from being redacted.
        2. "sensitive_content_rules": A single string describing any new, subjective content the user wants to find and redact.

        **CRITICAL RULE:** If you identify a multi-word person's name in the "exceptions" (e.g., "Oliver Hughes"), you MUST add BOTH the full name AND the first name to the exceptions list (e.g., ["Oliver Hughes", "Oliver"]). Do this only for names that look like people's names.

        If a category is not mentioned, omit its key from the JSON. Respond ONLY with the valid JSON object.

        --- EXAMPLES ---
        User Input: "keep sarah linton and oliver hughes, but also redact any mention of bullying"
        Your Output:
        {
        "exceptions": ["Sarah Linton", "Sarah", "Oliver Hughes", "Oliver"],
        "sensitive_content_rules": "Redact any mention of bullying."
        }
        ---
        User Input: "Don't remove the name Oliver Hughes"
        Your Output:
        {
        "exceptions": ["Oliver Hughes", "Oliver"]
        }
        ---
        User Input: "The company 'Hughes Construction' is fine to keep."
        Your Output:
        {
        "exceptions": ["Hughes Construction"]
        }
        ---
        User Input: "Find any quotes that are critical of the parents"
        Your Output:
        {
        "sensitive_content_rules": "Find any quotes that are critical of the parents"
        }
        """

_CONTEXTUAL_PROMPT_TEMPLATE = """
        You are a highly advanced document analysis tool. Your task is to analyze a specific block of text based on a user's rule, using the surrounding text for context only.

        **USER'S SENSITIVE CONTENT RULE:** "{rule}"

        --- YOUR THOUGHT PROCESS ---
        1. First, I will read the full text to understand the full context.
        2. Second, I will ONLY extract passages, sentences, or quotations from the "TARGET TEXT" that strictly match the user's rule. I will not extract anything from the context block.

        For each match, use the category `SensitiveContent`. In your reasoning, you MUST explain how the extracted text specifically relates to the user's rule.

        CRITICAL: Only extract text that directly matches the user's rule. Do not extract anything else.

        **Output Format:**
        Respond ONLY with a valid JSON object with a single key "redactions", which is an array of objects.
        Each object must have "text", "category", and "reasoning". If nothing is found, return an empty "redactions" array.
        """

_ENTITY_LINK_PROMPT = """
            You are an entity-linking specialist. Below is a block of text and a list of PII entities found within it.
            Your task is to link each PII entity to the primary person it belongs to in the text.
            Return a JSON object where the keys are the exact text of each PII entity, and the value is the name of the person it is associated with.
            - If an entity IS a person's name, the value should be the name itself.
            - If an entity clearly belongs to a person mentioned in the text, the value should be that person's name.
            - If an entity does not belong to any specific person, use the value 'None'.

            --- EXAMPLE ---
            Text: "Oliver (DOB: 14 March 2015) was quiet. He attends Bridgwater Primary School. Sarah Linton is the case worker."
            PII Entities: ["Oliver", "14 March 2015", "Bridgwater Primary School", "Sarah Linton"]

            Your Output:
            {
            "Oliver": "Oliver",
            "14 March 2015": "Oliver",
            "Bridgwater Primary School": "Oliver",
            "Sarah Linton": "Sarah Linton"
            }
            """

_PII_VIA_LLM_PROMPT = """
You are a UK PII detection tool. Identify all PII in the text.
Return JSON: {"entities": [{"text": "...", "category": "Person|Address|PhoneNumber|Email|Age|DateOfBirth|NationalInsuranceNumber|Organization", "offset": 0, "length": 0}]}
Estimate offsets from the text. If nothing found, return {"entities": []}.
"""


class OpenAIRedactionClient:
    """Async Azure OpenAI client using the Responses API for redaction tasks."""

    def __init__(self, endpoint: str, key: str, deployment: str, api_version: str):
        self._client = AsyncAzureOpenAI(
            api_key=key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        self._deployment = deployment

    async def _respond(self, instructions: str, input_text: str) -> str:
        """Make a Responses API call and return output_text."""
        # Avoid using the `text.format: json_object` option because some
        # Responses API clients require the input messages to explicitly
        # contain the word "json" when that mode is used. Rely on the
        # instructions/request content to ask for JSON and parse the
        # returned text instead.
        response = await self._client.responses.create(
            model=self._deployment,
            instructions=instructions,
            input=input_text,
            temperature=0.0,
        )
        return response.output_text

    async def parse_instructions(self, user_text: str) -> dict:
        """Parse free-text user instructions into a structured JSON configuration."""
        if not user_text or not user_text.strip():
            return {}
        try:
            raw = await self._respond(_INSTRUCTION_PARSE_PROMPT, user_text)
            return json.loads(raw)
        except Exception:
            logger.exception("Instruction parsing error")
            return {}

    async def get_contextual_redactions(self, page_text: str, rule: str) -> list[dict]:
        """Apply a user-defined sensitive content rule to a page of text."""
        try:
            system = _CONTEXTUAL_PROMPT_TEMPLATE.replace("{rule}", rule)
            raw = await self._respond(system, page_text)
            return json.loads(raw).get("redactions", [])
        except Exception:
            logger.exception("Contextual redaction error")
            return []

    async def link_entities(self, context_block: str, entities: list[dict]) -> dict:
        """Link PII entities to the primary person they belong to in the text."""
        if not entities:
            return {}
        try:
            entity_list = ", ".join(f'"{e["text"]}"' for e in entities)
            user = f'Text: "{context_block}"\nPII Entities: [{entity_list}]'
            raw = await self._respond(_ENTITY_LINK_PROMPT, user)
            return json.loads(raw)
        except Exception:
            logger.exception("Entity linking error")
            return {}

    async def get_pii_via_llm(self, page_text: str) -> list[dict]:
        """GPT-based PII detection — used when ENABLE_PII_SERVICE=false."""
        try:
            raw = await self._respond(_PII_VIA_LLM_PROMPT, page_text)
            return json.loads(raw).get("entities", [])
        except Exception:
            logger.exception("GPT PII error")
            return []

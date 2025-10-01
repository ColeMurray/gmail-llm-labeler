"""LLM service for email categorization."""

import json
import logging
import time
from datetime import datetime
from typing import List, Tuple

from openai import OpenAI

from .config import (
    ERROR_LOG_FILE,
    GPT_OSS_REASONING,
    LLM_LOG_FILE,
    LLM_SERVICE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


class LLMService:
    """Handles email categorization using LLM (OpenAI or Ollama)."""

    def __init__(
        self,
        categories: List[str],
        max_content_length: int = 4000,
        llm_client: OpenAI = None,
        model: str = None,
        lazy_init: bool = False,
    ):
        """Initialize the LLM client.

        Args:
            categories: List of category labels for email classification.
            max_content_length: Maximum length of email content before truncation.
            llm_client: Optional OpenAI client instance. If not provided, creates based on config.
            model: Optional model name. If not provided, uses config defaults.
            lazy_init: If True, delay LLM client initialization until first use.
        """
        self.categories = categories
        self.max_content_length = max_content_length
        self._lazy_init = lazy_init
        if llm_client is not None:
            self.llm_client = llm_client
            self.model = model or (OLLAMA_MODEL if LLM_SERVICE == "Ollama" else OPENAI_MODEL)
        elif not lazy_init:
            self.llm_client = self._get_llm_client()
            self.model = OLLAMA_MODEL if LLM_SERVICE == "Ollama" else OPENAI_MODEL
        else:
            self.llm_client = None
            self.model = model or (OLLAMA_MODEL if LLM_SERVICE == "Ollama" else OPENAI_MODEL)

    def _ensure_llm_client(self):
        """Ensure LLM client is initialized (for lazy initialization)."""
        if self.llm_client is None and self._lazy_init:
            self.llm_client = self._get_llm_client()
            if not self.model:
                self.model = OLLAMA_MODEL if LLM_SERVICE == "Ollama" else OPENAI_MODEL

    def _get_llm_client(self) -> OpenAI:
        """Get the appropriate LLM client based on configuration."""
        if LLM_SERVICE == "Ollama":
            logging.info(f"Using Ollama at {OLLAMA_BASE_URL} with model {OLLAMA_MODEL}")
            return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")  # Dummy key for Ollama
        else:
            logging.info(f"Using OpenAI with model {OPENAI_MODEL}")
            return OpenAI(api_key=OPENAI_API_KEY)

    def categorize_email(self, email_content: str) -> Tuple[str, str]:
        """
        Categorizes an email using the configured LLM.
        Returns tuple of (category, explanation)
        """
        self._ensure_llm_client()
        # Truncate very long emails
        if len(email_content) > self.max_content_length:
            email_content = (
                email_content[: self.max_content_length] + "\n[Email truncated for processing]"
            )
            logging.debug(f"Truncated email content to {self.max_content_length} characters")

        # Build messages
        messages = self._build_messages(email_content)

        try:
            # Make API call
            response = self._call_llm(messages)

            # Parse and validate response
            category, explanation = self._parse_response(response)

            return category, explanation

        except Exception as e:
            logging.error(f"Error in LLM categorization with {self.model}: {str(e)}")
            logging.exception("Full exception details:")
            self._log_error(email_content, str(e))
            return "Other", f"Error: {str(e)}"

    def _build_messages(self, email_content: str) -> list:
        """Build messages for the LLM based on the service type."""
        messages = []

        if LLM_SERVICE == "Ollama" and "gpt-oss" in self.model:
            # Special handling for gpt-oss models
            system_content = f"Reasoning: {GPT_OSS_REASONING}\n"
            system_content += (
                "You are an email categorization assistant."
                "An email that is a notification should always be categorized as 'Notifications'."
                "Always respond with a valid JSON object containing 'category' and 'explanation' fields."
            )
            messages.append({"role": "system", "content": system_content})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": "You are an email categorization assistant. Always respond with a valid JSON object containing 'category' and 'explanation' fields.",
                }
            )

        # User prompt
        user_prompt = f"""Categorize this email into exactly ONE of these categories:

{", ".join(self.categories)}

Email content:
{email_content}

Respond with a JSON object:
{{
    "explanation": "<brief reason for this categorization>",
    "category": "<exact category name from the list>",

}}"""

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _call_llm(self, messages: list) -> str:
        """Make the API call to the LLM."""
        start_time = time.time()

        # Prepare completion kwargs
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }

        # Add response_format for OpenAI (not supported by Ollama)
        if LLM_SERVICE == "OpenAI":
            completion_kwargs["response_format"] = {"type": "json_object"}

        logging.debug(f"Calling {LLM_SERVICE} API with model {self.model}")
        response = self.llm_client.chat.completions.create(**completion_kwargs)

        end_time = time.time()

        # Log the interaction
        self._log_interaction(start_time, end_time, response.choices[0].message.content)

        return response.choices[0].message.content

    def _parse_response(self, response_text: str) -> Tuple[str, str]:
        """Parse and validate the LLM response."""
        response_text = response_text.strip()
        logging.info(f"LLM response: {response_text[:500]}")

        # Try to parse as JSON
        try:
            response_json = json.loads(response_text)
            category = response_json.get("category", "").strip()
            explanation = response_json.get("explanation", "")
            logging.debug(f"Categorized as: {category} - {explanation}")
        except json.JSONDecodeError:
            logging.warning("Failed to parse JSON response, attempting text extraction")
            # Fallback: try to extract category from text
            for label in self.categories:
                if label.lower() in response_text.lower():
                    logging.info(f"Extracted category '{label}' from non-JSON response")
                    return label, "Extracted from response"
            return "Other", "Failed to parse response"

        # Validate category
        if category in self.categories:
            return category, explanation
        else:
            # Try fuzzy matching
            category_lower = category.lower()
            for label in self.categories:
                if label.lower() in category_lower or category_lower in label.lower():
                    logging.info(f"Fuzzy matched '{category}' to '{label}'")
                    return label, explanation
            logging.warning(f"Category '{category}' not in predefined list")
            return "Other", f"Unknown category: {category}"

    def _log_interaction(self, start_time: float, end_time: float, response: str):
        """Log the LLM interaction for debugging."""
        log_entry = {
            "request_timestamp": start_time,
            "response_timestamp": end_time,
            "duration": end_time - start_time,
            "model": self.model,
            "service": LLM_SERVICE,
            "response": response,
        }
        with open(LLM_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _log_error(self, email_content: str, error: str):
        """Log categorization errors for debugging."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "error": error,
            "email_preview": email_content[:500] if email_content else "No content",
        }
        with open(ERROR_LOG_FILE, "a") as f:
            f.write(json.dumps(error_entry) + "\n")

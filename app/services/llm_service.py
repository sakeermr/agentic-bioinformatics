"""
services/llm_service.py
-----------------------
Unified LLM interface supporting OpenAI (primary) and Gemini (fallback).
All agents call this service — never call LLM APIs directly from agents.
"""

import logging
from typing import Optional
from app.config.settings import (
    LLM_PROVIDER, LLM_MODEL, OPENAI_API_KEY, GEMINI_API_KEY
)

logger = logging.getLogger(__name__)


class LLMService:
    """
    Wraps OpenAI and Gemini APIs behind a single interface.
    Falls back to Gemini if OpenAI fails or is unconfigured.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = LLM_MODEL
        self._openai_client = None
        self._gemini_model = None
        self._init_clients()

    def _init_clients(self):
        """Initialize whichever LLM clients are available."""
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("OpenAI client initialized (model: %s)", self.model)
            except ImportError:
                logger.warning("openai package not installed")

        if GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("Gemini client initialized")
            except ImportError:
                logger.warning("google-generativeai package not installed")

    # ── Public API ────────────────────────────────────────────

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send a prompt to the configured LLM and return the response text.

        Tries OpenAI first; falls back to Gemini if OpenAI fails.
        Raises RuntimeError if no provider is available.
        """
        if self._openai_client:
            try:
                return self._call_openai(system_prompt, user_prompt, temperature, max_tokens)
            except Exception as exc:
                logger.warning("OpenAI call failed (%s), trying Gemini fallback", exc)

        if self._gemini_model:
            try:
                return self._call_gemini(system_prompt, user_prompt)
            except Exception as exc:
                logger.error("Gemini fallback also failed: %s", exc)
                raise RuntimeError(f"All LLM providers failed. Last error: {exc}") from exc

        raise RuntimeError(
            "No LLM provider configured. Set OPENAI_API_KEY or GEMINI_API_KEY in .env"
        )

    # ── Private Helpers ───────────────────────────────────────

    def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call OpenAI chat completion."""
        response = self._openai_client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Call Google Gemini generation."""
        combined = f"{system_prompt}\n\n{user_prompt}"
        response = self._gemini_model.generate_content(combined)
        return response.text.strip()


# ── Module-level singleton ────────────────────────────────────
# Import this instance wherever LLM calls are needed.
llm_service = LLMService()

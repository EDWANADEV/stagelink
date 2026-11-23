"""Small OpenAI Responses API adapter using StageLink's existing requests dependency."""

import requests
from django.conf import settings


class OpenAIAdapter:
    """Call OpenAI's Responses API without persisting response state."""

    endpoint = "https://api.openai.com/v1/responses"

    def generate(self, *, system_prompt, user_prompt, timeout, max_output_tokens):
        response = requests.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.AI_OPENAI_MODEL,
                "instructions": system_prompt,
                "input": user_prompt,
                "max_output_tokens": max_output_tokens,
                "store": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "completed" or payload.get("error"):
            raise ValueError

        text_parts = [
            content["text"]
            for item in payload.get("output", [])
            if item.get("type") == "message"
            for content in item.get("content", [])
            if content.get("type") == "output_text"
            and isinstance(content.get("text"), str)
        ]
        usage = payload.get("usage") or {}
        return {
            "text": "\n".join(text_parts),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        }

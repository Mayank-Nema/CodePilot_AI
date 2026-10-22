"""
LLM — Modular Ollama LLM Client with Diagnostic Fallback.

Responsibilities:
    - Connect to local Ollama API (http://localhost:11434).
    - Support configurable model names via environment variable (OLLAMA_MODEL) or runtime parameters.
    - Provide connection health check (test_connection).
    - Handle timeouts and connection errors gracefully without crashing the application.
"""

import json
import os
from typing import Optional, Tuple
import requests

DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")


class OllamaLLM:
    """Ollama API Client with configurable model selection and diagnostic fallback."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to the Ollama server.

        Returns:
            Tuple of (is_connected, status_message).
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                model_str = ", ".join(models) if models else "No models installed"
                return True, f"Connected to Ollama ({self.base_url}). Models: {model_str}"
            return False, f"Ollama returned HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, f"Could not connect to Ollama at {self.base_url}. Is Ollama running?"
        except Exception as e:
            return False, f"Ollama connection check failed: {e}"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Tuple[str, bool]:
        """Generate a completion from Ollama.

        Args:
            prompt: Main prompt containing context and user question.
            system_prompt: Optional system instruction prompt.
            temperature: Generation temperature (0.0 to 1.0).

        Returns:
            Tuple of (response_text, success_flag).
            If success_flag is False, response_text contains a helpful diagnostic message.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                answer = data.get("response", "").strip()
                if not answer:
                    return "Ollama returned an empty response.", False
                return answer, True
            else:
                diag = (
                    f"⚠️ Ollama returned error status {response.status_code}.\n"
                    f"Message: {response.text}\n"
                    f"Configured model: `{self.model}`"
                )
                return diag, False

        except requests.exceptions.ConnectionError:
            diag = (
                f"⚠️ **Ollama is offline or unreachable.**\n\n"
                f"Could not connect to `{self.base_url}`. "
                f"Please ensure Ollama is installed and running (`ollama serve`), "
                f"and that model `{self.model}` is available (`ollama pull {self.model}`)."
            )
            return diag, False

        except requests.exceptions.Timeout:
            diag = (
                f"⚠️ **Ollama request timed out** after {self.timeout}s.\n"
                f"The model `{self.model}` may still be loading or generating."
            )
            return diag, False

        except Exception as e:
            diag = f"⚠️ **LLM Generation Error:** {e}"
            return diag, False

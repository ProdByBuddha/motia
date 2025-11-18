"""
Ollama Cloud Client

Direct client for Ollama Cloud API with proper authentication.
Bypasses litellm to use massive cloud-hosted models.

Available Models:
- deepseek-v3.1:671b (671B params - reasoning)
- qwen3-coder:480b (480B params - code)
- qwen3-vl:235b (235B params - vision)
- glm-4.6 (696GB - multilingual)
- gpt-oss:120b/20b (general purpose)
"""

import os
import asyncio
import httpx
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class OllamaCloudClient:
    """
    Client for Ollama Cloud API.

    Features:
    - Access to 100+ models including 671B parameter models
    - Proper Authorization header authentication
    - Streaming and non-streaming support
    - Free tier with usage-based pricing after limits
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://ollama.com/api",
        timeout: int = 120
    ):
        """
        Initialize Ollama Cloud client.

        Args:
            api_key: Ollama Cloud API key (or from OLLAMA_API_KEY env)
            base_url: Base URL for Ollama Cloud
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv('OLLAMA_API_KEY')
        if not self.api_key:
            raise ValueError("OLLAMA_API_KEY environment variable or api_key parameter required")

        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth headers"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.timeout
            )
        return self._client

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models.

        Returns:
            List of model metadata dicts
        """
        try:
            client = await self._get_client()
            response = await client.get("/tags")

            if response.status_code == 200:
                data = response.json()
                return data.get('models', [])
            else:
                logger.error(f"Failed to list models: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate response from Ollama Cloud model.

        Args:
            model: Model name (e.g., "deepseek-v3.1:671b")
            prompt: Input prompt
            system: System message/context
            stream: Stream responses
            temperature: Sampling temperature (0-2)
            max_tokens: Max tokens to generate

        Returns:
            Response dict with 'response', 'thinking', 'done', etc.
        """
        try:
            client = await self._get_client()

            data = {
                "model": model,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                }
            }

            if system:
                data["system"] = system

            if max_tokens:
                data["options"]["num_predict"] = max_tokens

            logger.info(f"Generating with {model}")

            response = await client.post("/generate", json=data)

            if response.status_code == 200:
                return response.json()
            else:
                error_text = response.text
                logger.error(f"Generation failed: {response.status_code} - {error_text}")
                return {"error": error_text, "status_code": response.status_code}

        except Exception as e:
            logger.error(f"Generation error: {e}")
            return {"error": str(e)}

    async def generate_stream(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Stream generation from Ollama Cloud.

        Args:
            model: Model name
            prompt: Input prompt
            system: System message
            temperature: Sampling temperature

        Yields:
            Response tokens
        """
        try:
            client = await self._get_client()

            data = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": temperature}
            }

            if system:
                data["system"] = system

            async with client.stream("POST", "/generate", json=data) as response:
                if response.status_code != 200:
                    yield f"Error: {response.status_code}"
                    return

                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                yield chunk['response']
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"Error: {str(e)}"

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Chat completion with message history.

        Args:
            model: Model name
            messages: List of {"role": "user/assistant", "content": "..."}
            stream: Stream responses
            temperature: Sampling temperature

        Returns:
            Response dict
        """
        try:
            client = await self._get_client()

            data = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "options": {"temperature": temperature}
            }

            response = await client.post("/chat", json=data)

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text, "status_code": response.status_code}

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ============================================================================
# Model Selection Helpers
# ============================================================================

class ModelSelector:
    """Helper for selecting optimal model for task"""

    # Model registry with capabilities
    MODELS = {
        'code': {
            'best': 'qwen3-coder:480b',
            'fast': 'gpt-oss:120b',
            'vision': 'qwen3-vl:235b',
        },
        'reasoning': {
            'best': 'deepseek-v3.1:671b',
            'fast': 'gpt-oss:120b',
        },
        'vision': {
            'best': 'qwen3-vl:235b',
        },
        'general': {
            'best': 'gpt-oss:120b',
            'fast': 'gpt-oss:20b',
        }
    }

    @classmethod
    def get_model(cls, task_type: str, prefer_fast: bool = False) -> str:
        """
        Get optimal model for task type.

        Args:
            task_type: 'code', 'reasoning', 'vision', 'general'
            prefer_fast: Use faster model if True

        Returns:
            Model name
        """
        models = cls.MODELS.get(task_type, cls.MODELS['general'])

        if prefer_fast and 'fast' in models:
            return models['fast']

        return models.get('best', 'gpt-oss:120b')


# ============================================================================
# Factory Functions
# ============================================================================

def create_ollama_cloud_client(api_key: Optional[str] = None) -> OllamaCloudClient:
    """Create Ollama Cloud client instance"""
    return OllamaCloudClient(api_key=api_key)


async def quick_generate(
    model: str,
    prompt: str,
    api_key: Optional[str] = None
) -> str:
    """Quick one-off generation"""
    client = create_ollama_cloud_client(api_key)
    try:
        result = await client.generate(model, prompt)
        return result.get('response', '')
    finally:
        await client.close()


# ============================================================================
# Constants
# ============================================================================

# Best models for each category
MODEL_CODE_BEST = "qwen3-coder:480b"
MODEL_REASONING_BEST = "deepseek-v3.1:671b"
MODEL_VISION_BEST = "qwen3-vl:235b"
MODEL_GENERAL_BEST = "gpt-oss:120b"
MODEL_FAST_BEST = "gpt-oss:20b"

import logging
from typing import AsyncGenerator
from openai import AsyncOpenAI
from src.config.settings import settings

logger = logging.getLogger(__name__)

class VllmClient:
    """
    Client for the self-hosted vLLM engine via OpenAI-compatible API.
    Connects to meta-llama/Meta-Llama-3.1-8B-Instruct.
    """
    def __init__(self):
        self.model = settings.llm_model
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
        
    async def generate_response_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """
        Streams back the LLM response token by token.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.3,
                max_tokens=256
            )
            
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
                    
        except Exception as e:
            logger.error(f"vLLM API error: {e}", exc_info=True)
            yield "Sorry, I am having trouble connecting to my brain right now."

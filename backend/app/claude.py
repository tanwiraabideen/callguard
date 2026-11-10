"""The one Claude API client, shared by the risk check and the agent."""

from anthropic import AsyncAnthropic

from app.config import settings

client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global client
    if client is None:
        client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=0,  # a late answer is no use during a live call
        )
    return client

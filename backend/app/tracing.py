"""Turns on LangSmith tracing for the agent when a key is set."""

import asyncio
import logging
import os
from types import SimpleNamespace
from uuid import UUID

from langsmith import Client

from app.config import settings

logger = logging.getLogger("uvicorn.error")


def configure_tracing() -> None:
    """LangGraph reads these environment variables when it runs."""
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


async def run_url(run_id: UUID) -> str | None:
    if not settings.langsmith_api_key:
        return None

    def look_up() -> str:
        client = Client(api_key=settings.langsmith_api_key)
        run = SimpleNamespace(id=run_id, session_id=None, app_path=None)
        return client.get_run_url(run=run, project_name=settings.langsmith_project)

    try:
        return await asyncio.to_thread(look_up)
    except Exception as error:
        logger.warning("Could not get the LangSmith link: %s", error)
        return None

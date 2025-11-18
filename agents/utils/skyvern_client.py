"""
Skyvern Client Wrapper

Provides interface to self-hosted Skyvern instance for intelligent web scraping.
Handles task creation, polling, and result extraction.

Skyvern Location: /opt/skyvern
API Endpoint: http://localhost:8000
UI Dashboard: http://localhost:8081
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SkyvernClient:
    """
    Client for interacting with self-hosted Skyvern instance.

    Features:
    - AI-powered web navigation
    - Intelligent data extraction
    - Form filling
    - Multi-step workflows
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 300
    ):
        """
        Initialize Skyvern client.

        Args:
            base_url: Skyvern API URL
            api_key: API key (if required)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout
            )
        return self._client

    async def health_check(self) -> bool:
        """
        Check if Skyvern is available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get("/")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Skyvern health check failed: {e}")
            return False

    async def create_task(
        self,
        url: str,
        navigation_goal: str,
        data_extraction_goal: Optional[str] = None,
        navigation_payload: Optional[Dict[str, Any]] = None,
        max_steps: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Skyvern task for web navigation and data extraction.

        Args:
            url: Target URL to navigate
            navigation_goal: What to do on the page (natural language)
            data_extraction_goal: What data to extract (optional)
            navigation_payload: Data for form filling (optional)
            max_steps: Maximum browser steps

        Returns:
            Task response dict or None if failed
        """
        try:
            client = await self._get_client()

            task_data = {
                "url": url,
                "navigation_goal": navigation_goal,
                "max_steps_per_run": max_steps,
            }

            if data_extraction_goal:
                task_data["data_extraction_goal"] = data_extraction_goal

            if navigation_payload:
                task_data["navigation_payload"] = navigation_payload

            logger.info(f"Creating Skyvern task: {url}")

            response = await client.post("/v1/run/tasks", json=task_data)

            if response.status_code >= 400:
                error_detail = response.json().get('detail', 'Unknown error')
                logger.error(f"Skyvern task creation failed: {error_detail}")
                return None

            result = response.json()
            logger.info(f"Skyvern task created: {result.get('run_id')}")

            return result

        except Exception as e:
            logger.error(f"Skyvern task creation error: {e}")
            return None

    async def wait_for_task(
        self,
        run_id: str,
        poll_interval: int = 2,
        max_wait: int = 300
    ) -> Optional[Dict[str, Any]]:
        """
        Poll for task completion.

        Args:
            run_id: Task run ID
            poll_interval: Seconds between polls
            max_wait: Maximum wait time in seconds

        Returns:
            Task result or None if timeout/error
        """
        try:
            client = await self._get_client()
            start_time = datetime.now()

            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_wait:
                    logger.warning(f"Skyvern task timeout: {run_id}")
                    return None

                # Poll status
                response = await client.get(f"/v1/runs/{run_id}")

                if response.status_code >= 400:
                    logger.error(f"Skyvern status check failed: {run_id}")
                    return None

                result = response.json()
                status = result.get('status')

                logger.debug(f"Skyvern task {run_id} status: {status}")

                # Check if completed
                if status in ['completed', 'failed', 'terminated']:
                    logger.info(f"Skyvern task finished: {run_id} ({status})")
                    return result

                # Wait before next poll
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Skyvern polling error: {e}")
            return None

    async def extract_data_from_url(
        self,
        url: str,
        extraction_goal: str,
        max_steps: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        High-level method: Create task and wait for extraction.

        Args:
            url: URL to scrape
            extraction_goal: What data to extract (natural language)
            max_steps: Max browser steps

        Returns:
            Extracted data dict or None
        """
        logger.info(f"Skyvern extraction: {url}")

        # Create task
        task = await self.create_task(
            url=url,
            navigation_goal=f"Navigate and extract: {extraction_goal}",
            data_extraction_goal=extraction_goal,
            max_steps=max_steps
        )

        if not task:
            logger.warning("Skyvern task creation failed")
            return None

        run_id = task.get('run_id')
        if not run_id:
            logger.error("No run_id in Skyvern response")
            return None

        # Wait for completion
        result = await self.wait_for_task(run_id)

        if not result:
            return None

        # Extract data from result
        extracted_data = result.get('extracted_information', {})

        return {
            'run_id': run_id,
            'status': result.get('status'),
            'url': url,
            'extracted_data': extracted_data,
            'steps_taken': result.get('steps_count', 0),
            'duration_ms': result.get('duration_ms', 0),
        }

    async def search_and_extract(
        self,
        search_query: str,
        search_engine: str = "duckduckgo",
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Use Skyvern to search and extract from multiple pages.

        Args:
            search_query: Search query
            search_engine: Search engine to use
            num_results: Number of results to extract

        Returns:
            List of extracted results
        """
        logger.info(f"Skyvern multi-search: {search_query}")

        # Build search URL
        search_urls = {
            "duckduckgo": f"https://duckduckgo.com/?q={search_query.replace(' ', '+')}",
            "google": f"https://www.google.com/search?q={search_query.replace(' ', '+')}",
        }

        search_url = search_urls.get(search_engine, search_urls["duckduckgo"])

        # Extract search results
        result = await self.extract_data_from_url(
            url=search_url,
            extraction_goal=f"Extract top {num_results} search results including title, URL, and snippet",
            max_steps=20
        )

        if not result:
            return []

        # Parse extracted data
        extracted = result.get('extracted_data', {})

        # Convert to structured format
        results = []
        if isinstance(extracted, list):
            for item in extracted[:num_results]:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'snippet': item.get('snippet', ''),
                    'relevance': 0.8,  # Default relevance
                })

        return results

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ============================================================================
# Factory Function
# ============================================================================

def create_skyvern_client(
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None
) -> SkyvernClient:
    """
    Create Skyvern client instance.

    Args:
        base_url: Skyvern API URL
        api_key: API key (optional)

    Returns:
        SkyvernClient instance
    """
    return SkyvernClient(base_url=base_url, api_key=api_key)


# ============================================================================
# Convenience Functions
# ============================================================================

async def skyvern_is_available() -> bool:
    """Check if Skyvern is available and healthy"""
    client = create_skyvern_client()
    healthy = await client.health_check()
    await client.close()
    return healthy


async def quick_extract(url: str, extraction_goal: str) -> Optional[Dict[str, Any]]:
    """
    Quick one-off extraction using Skyvern.

    Args:
        url: URL to extract from
        extraction_goal: What to extract

    Returns:
        Extracted data or None
    """
    client = create_skyvern_client()
    try:
        result = await client.extract_data_from_url(url, extraction_goal)
        return result
    finally:
        await client.close()

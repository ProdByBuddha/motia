"""
Web Scraper Utility

Fallback web scraping when Skyvern is unavailable.
Uses httpx for HTTP requests and basic HTML parsing.
"""

import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class SimpleWebScraper:
    """
    Simple web scraper for fallback when Skyvern unavailable.

    Features:
    - Basic HTML fetching
    - Text extraction
    - Link extraction
    - Metadata extraction
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize scraper.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch page HTML.

        Args:
            url: URL to fetch

        Returns:
            HTML content or None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (compatible; ResearchBot/1.0)'
                    },
                    follow_redirects=True
                )

                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    return None

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def extract_text(self, html: str, max_length: int = 5000) -> str:
        """
        Extract main text content from HTML.

        Args:
            html: HTML content
            max_length: Max text length

        Returns:
            Extracted text
        """
        # Remove script and style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text[:max_length]

    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract links from HTML.

        Args:
            html: HTML content
            base_url: Base URL for relative links

        Returns:
            List of absolute URLs
        """
        # Find all href attributes
        links = re.findall(r'href=["\']([^"\']+)["\']', html)

        # Convert to absolute URLs
        absolute_links = []
        for link in links:
            absolute_url = urljoin(base_url, link)

            # Filter valid HTTP(S) URLs
            if absolute_url.startswith(('http://', 'https://')):
                absolute_links.append(absolute_url)

        # Deduplicate
        return list(set(absolute_links))[:50]

    def extract_title(self, html: str) -> str:
        """
        Extract page title.

        Args:
            html: HTML content

        Returns:
            Page title or empty string
        """
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    async def search_duckduckgo(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, str]]:
        """
        Search DuckDuckGo and extract results.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of search results with title, url, snippet
        """
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"

            html = await self.fetch_page(search_url)
            if not html:
                return []

            # Extract search result links and titles
            # DuckDuckGo HTML structure: class="result__a" contains title and href
            results = []

            # Pattern for result links
            link_pattern = r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(link_pattern, html, re.DOTALL)

            for i, (url, title) in enumerate(matches[:num_results]):
                # Clean URL (DuckDuckGo wraps URLs)
                url = url.replace('/l/?kh=-1&uddg=', '')

                # Clean title (remove HTML)
                title = re.sub(r'<[^>]+>', '', title).strip()

                results.append({
                    'title': title,
                    'url': url,
                    'snippet': f"Search result {i+1} for: {query}",
                    'relevance': 0.9 - (i * 0.05),  # Decrease relevance by position
                })

            logger.info(f"DuckDuckGo search found {len(results)} results for: {query}")

            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return []

    async def extract_page_summary(
        self,
        url: str,
        max_sentences: int = 3
    ) -> Dict[str, Any]:
        """
        Extract summary information from a page.

        Args:
            url: URL to summarize
            max_sentences: Max sentences in summary

        Returns:
            Page summary dict
        """
        html = await self.fetch_page(url)
        if not html:
            return {'error': 'Failed to fetch page'}

        title = self.extract_title(html)
        text = self.extract_text(html, max_length=1000)

        # Extract first few sentences
        sentences = re.split(r'[.!?]+', text)
        summary = '. '.join(sentences[:max_sentences]).strip() + '.'

        return {
            'url': url,
            'title': title,
            'summary': summary,
            'fetched_at': datetime.now().isoformat(),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_web_scraper() -> SimpleWebScraper:
    """Create web scraper instance"""
    return SimpleWebScraper()

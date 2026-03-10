"""
Confluence Reader

Reads and processes eShop application documentation from Confluence
using the Atlassian MCP client.
"""

import logging
from dataclasses import dataclass, field

from .mcp_client import AtlassianMCPClient

logger = logging.getLogger(__name__)


@dataclass
class ConfluencePage:
    """Represents a retrieved Confluence page."""

    page_id: str
    title: str
    body: str
    space: str = ""
    version: int = 1
    url: str = ""


@dataclass
class ConfluenceSearchResult:
    """A single search result from Confluence."""

    page_id: str
    title: str
    url: str
    excerpt: str = ""
    space: str = ""


@dataclass
class ApplicationDocumentation:
    """Structured documentation collected from Confluence."""

    pages: list[ConfluencePage] = field(default_factory=list)
    raw_content: str = ""

    def combined_text(self) -> str:
        """Return all page bodies joined into one string."""
        parts = [f"### {p.title}\n\n{p.body}" for p in self.pages]
        return "\n\n---\n\n".join(parts)


class ConfluenceReader:
    """
    Reads eShop application documentation from Confluence.

    Uses the Atlassian MCP client to fetch pages and search for
    relevant documentation.
    """

    def __init__(self, mcp_client: AtlassianMCPClient):
        self.client = mcp_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_page(self, page_id: str) -> ConfluencePage | None:
        """Fetch a single Confluence page by ID."""
        logger.info("Reading Confluence page %s …", page_id)
        response = self.client.get_confluence_page(page_id)
        if not response.success:
            logger.error("Failed to fetch page %s: %s", page_id, response.error)
            return None
        data = response.data
        return ConfluencePage(
            page_id=data.get("id", page_id),
            title=data.get("title", ""),
            body=data.get("body", ""),
            space=data.get("space", ""),
            version=data.get("version", 1),
            url=data.get("url", ""),
        )

    def search_documentation(
        self, query: str, space_key: str | None = None
    ) -> list[ConfluenceSearchResult]:
        """Search for pages matching *query* and return a result list."""
        logger.info("Searching Confluence for %r …", query)
        response = self.client.search_confluence(query, space_key=space_key)
        if not response.success:
            logger.error("Confluence search failed: %s", response.error)
            return []
        results = []
        for item in response.data.get("results", []):
            results.append(
                ConfluenceSearchResult(
                    page_id=item.get("id", ""),
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    excerpt=item.get("excerpt", ""),
                    space=item.get("space", ""),
                )
            )
        logger.info("Found %d Confluence result(s).", len(results))
        return results

    def read_application_documentation(
        self, space_key: str = "ENG", page_id: str | None = None
    ) -> ApplicationDocumentation:
        """
        Collect all relevant eShop documentation from Confluence.

        Strategy:
        1. If *page_id* is provided, fetch that page directly.
        2. Otherwise, search for eShop documentation in *space_key*.
        3. Fetch each found page and assemble an :class:`ApplicationDocumentation`.
        """
        doc = ApplicationDocumentation()

        if page_id:
            page = self.read_page(page_id)
            if page:
                doc.pages.append(page)
        else:
            search_queries = [
                "eShop application architecture",
                "eShop modernization requirements",
                "eShop Azure migration",
            ]
            seen_ids: set[str] = set()
            for query in search_queries:
                results = self.search_documentation(query, space_key=space_key)
                for result in results:
                    if result.page_id not in seen_ids:
                        seen_ids.add(result.page_id)
                        page = self.read_page(result.page_id)
                        if page:
                            doc.pages.append(page)

        doc.raw_content = doc.combined_text()
        logger.info(
            "Collected documentation: %d page(s), %d total characters.",
            len(doc.pages),
            len(doc.raw_content),
        )
        return doc

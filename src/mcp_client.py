"""
Atlassian Rovo MCP Client

Provides a client interface for interacting with Atlassian services
(Confluence and Jira) via the Model Context Protocol (MCP).

In demo mode (DEMO_MODE=true), simulates MCP responses using local
sample data so the demo works without live Atlassian credentials.
"""

import os
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Tool call / response types
# ---------------------------------------------------------------------------

class MCPResponse:
    """Represents a response from an MCP tool call."""

    def __init__(self, success: bool, data: Any, error: str | None = None):
        self.success = success
        self.data = data
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover
        return f"MCPResponse(success={self.success}, error={self.error!r})"


# ---------------------------------------------------------------------------
# Demo fixtures (returned when DEMO_MODE=true)
# ---------------------------------------------------------------------------

_DEMO_CONFLUENCE_CONTENT = """
eShop Application Documentation

Overview:
The eShop application is a legacy e-commerce platform built on .NET Framework 4.7
running on Windows Server 2016. It handles product catalog, order processing,
customer management, and payment processing.

Current Stack:
- Frontend: ASP.NET WebForms + jQuery 1.x
- Backend: .NET Framework 4.7, C#
- Database: SQL Server 2014 (on-premises)
- Cache: Windows Memory Cache (in-process)
- Authentication: Custom Forms Authentication with SQL membership
- File Storage: Local disk
- Messaging: MSMQ for order processing queue
- Deployment: IIS 8.5 on Windows Server 2016 VMs

Known Issues:
1. Performance: Product search is slow (full table scans on 2M+ rows)
2. Scalability: Cannot scale horizontally due to in-proc session and local storage
3. Security: MD5 password hashing is deprecated and insecure
4. Reliability: MSMQ failures cause lost orders with no recovery
5. Observability: Minimal logging, no distributed tracing, no metrics
6. Maintenance: .NET Framework 4.7 and SQL Server 2014 near end of support
7. Deployment: Manual deployments, no CI/CD pipeline
8. Cost: VMs running at 15-20% average CPU utilization (over-provisioned)

Business Requirements:
- 99.9% uptime SLA
- Support for 10x traffic spikes during sales events
- PCI and GDPR compliance
- Same-day order processing
- Mobile-friendly experience
"""

_DEMO_JIRA_SEARCH_RESULTS = [
    {
        "id": "ESHOP-1",
        "key": "ESHOP-1",
        "summary": "Azure Migration Epic",
        "status": "In Progress",
        "type": "Epic",
        "description": "Migrate eShop application to Azure cloud platform",
    },
    {
        "id": "ESHOP-10",
        "key": "ESHOP-10",
        "summary": "Migrate SQL Server to Azure SQL Database",
        "status": "To Do",
        "type": "Story",
        "description": "Migrate on-premises SQL Server 2014 to Azure SQL Database",
    },
    {
        "id": "ESHOP-11",
        "key": "ESHOP-11",
        "summary": "Set up CI/CD pipeline",
        "status": "To Do",
        "type": "Story",
        "description": "Create Azure DevOps pipeline for automated deployments",
    },
]


# ---------------------------------------------------------------------------
# MCP Client
# ---------------------------------------------------------------------------

class AtlassianMCPClient:
    """
    Client for Atlassian Rovo MCP tools.

    Wraps Confluence and Jira MCP tool calls.  When ``demo_mode=True`` the
    client returns pre-baked fixture data so the demo works without live
    Atlassian credentials.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        user_email: str | None = None,
        demo_mode: bool | None = None,
    ):
        self.base_url = base_url or os.environ.get("ATLASSIAN_BASE_URL", "")
        self.api_token = api_token or os.environ.get("ATLASSIAN_API_TOKEN", "")
        self.user_email = user_email or os.environ.get("ATLASSIAN_USER_EMAIL", "")
        # Explicit demo_mode parameter takes priority over the env var
        if demo_mode is not None:
            self.demo_mode = demo_mode
        else:
            self.demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"

        if not self.demo_mode and not all([self.base_url, self.api_token, self.user_email]):
            raise ValueError(
                "ATLASSIAN_BASE_URL, ATLASSIAN_API_TOKEN, and ATLASSIAN_USER_EMAIL "
                "must be set (or use DEMO_MODE=true)"
            )

        if self.demo_mode:
            logger.info("MCP client running in DEMO MODE – no real Atlassian calls will be made.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_mcp_call(self, tool_name: str, params: dict) -> MCPResponse:
        """
        Execute an MCP tool call against the Atlassian Rovo MCP server.

        In demo mode this method is never called – callers should return
        fixture data before reaching here.
        """
        try:
            import httpx  # optional live dependency

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"tool": tool_name, "parameters": params}
            response = httpx.post(
                f"{self.base_url}/mcp/tools/call",
                json=payload,
                headers=headers,
                auth=(self.user_email, self.api_token),
                timeout=30,
            )
            response.raise_for_status()
            return MCPResponse(success=True, data=response.json())
        except Exception as exc:
            logger.error("MCP call failed for tool %s: %s", tool_name, exc)
            return MCPResponse(success=False, data=None, error=str(exc))

    # ------------------------------------------------------------------
    # Confluence tools
    # ------------------------------------------------------------------

    def get_confluence_page(self, page_id: str) -> MCPResponse:
        """Retrieve a Confluence page by ID."""
        if self.demo_mode:
            logger.info("[DEMO] confluence_get_page(%s)", page_id)
            return MCPResponse(
                success=True,
                data={
                    "id": page_id,
                    "title": "eShop Application Documentation",
                    "body": _DEMO_CONFLUENCE_CONTENT,
                    "space": "ENG",
                    "version": 3,
                },
            )
        return self._make_mcp_call("confluence_get_page", {"page_id": page_id})

    def search_confluence(self, query: str, space_key: str | None = None) -> MCPResponse:
        """Search Confluence pages using CQL."""
        if self.demo_mode:
            logger.info("[DEMO] confluence_search(%r, space=%r)", query, space_key)
            return MCPResponse(
                success=True,
                data={
                    "results": [
                        {
                            "id": "123456",
                            "title": "eShop Application Documentation",
                            "url": "https://demo.atlassian.net/wiki/spaces/ENG/pages/123456",
                            "excerpt": "eShop legacy .NET application architecture and migration plan",
                            "space": space_key or "ENG",
                        }
                    ],
                    "total": 1,
                },
            )
        params: dict = {"query": query}
        if space_key:
            params["space_key"] = space_key
        return self._make_mcp_call("confluence_search", params)

    def create_confluence_page(
        self, space_key: str, title: str, body: str, parent_id: str | None = None
    ) -> MCPResponse:
        """Create a new Confluence page."""
        if self.demo_mode:
            new_id = "999001"
            logger.info("[DEMO] confluence_create_page(%r in %s)", title, space_key)
            return MCPResponse(
                success=True,
                data={
                    "id": new_id,
                    "title": title,
                    "url": f"https://demo.atlassian.net/wiki/spaces/{space_key}/pages/{new_id}",
                },
            )
        params: dict = {"space_key": space_key, "title": title, "body": body}
        if parent_id:
            params["parent_id"] = parent_id
        return self._make_mcp_call("confluence_create_page", params)

    def update_confluence_page(
        self, page_id: str, title: str, body: str, version: int
    ) -> MCPResponse:
        """Update an existing Confluence page."""
        if self.demo_mode:
            logger.info("[DEMO] confluence_update_page(%s)", page_id)
            return MCPResponse(
                success=True,
                data={"id": page_id, "title": title, "version": version + 1},
            )
        return self._make_mcp_call(
            "confluence_update_page",
            {"page_id": page_id, "title": title, "body": body, "version": version},
        )

    # ------------------------------------------------------------------
    # Jira tools
    # ------------------------------------------------------------------

    def search_jira_issues(self, jql: str, max_results: int = 50) -> MCPResponse:
        """Search Jira issues using JQL."""
        if self.demo_mode:
            logger.info("[DEMO] jira_search_issues(%r)", jql)
            return MCPResponse(success=True, data={"issues": _DEMO_JIRA_SEARCH_RESULTS})
        return self._make_mcp_call(
            "jira_search_issues", {"jql": jql, "max_results": max_results}
        )

    def get_jira_issue(self, issue_key: str) -> MCPResponse:
        """Get a specific Jira issue."""
        if self.demo_mode:
            logger.info("[DEMO] jira_get_issue(%s)", issue_key)
            match = next(
                (i for i in _DEMO_JIRA_SEARCH_RESULTS if i["key"] == issue_key), None
            )
            if match:
                return MCPResponse(success=True, data=match)
            return MCPResponse(success=False, data=None, error=f"Issue {issue_key} not found")
        return self._make_mcp_call("jira_get_issue", {"issue_key": issue_key})

    def create_jira_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Story",
        priority: str = "Medium",
        labels: list[str] | None = None,
        epic_link: str | None = None,
    ) -> MCPResponse:
        """Create a new Jira issue."""
        if self.demo_mode:
            new_key = f"{project_key}-{100 + id(summary) % 900}"
            logger.info("[DEMO] jira_create_issue(%r in %s)", summary, project_key)
            return MCPResponse(
                success=True,
                data={
                    "key": new_key,
                    "id": new_key,
                    "summary": summary,
                    "url": f"https://demo.atlassian.net/browse/{new_key}",
                },
            )
        params: dict = {
            "project_key": project_key,
            "summary": summary,
            "description": description,
            "issue_type": issue_type,
            "priority": priority,
        }
        if labels:
            params["labels"] = labels
        if epic_link:
            params["epic_link"] = epic_link
        return self._make_mcp_call("jira_create_issue", params)

    def update_jira_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
    ) -> MCPResponse:
        """Update an existing Jira issue."""
        if self.demo_mode:
            logger.info("[DEMO] jira_update_issue(%s)", issue_key)
            return MCPResponse(
                success=True,
                data={
                    "key": issue_key,
                    "updated": True,
                    "url": f"https://demo.atlassian.net/browse/{issue_key}",
                },
            )
        params: dict = {"issue_key": issue_key}
        if summary is not None:
            params["summary"] = summary
        if description is not None:
            params["description"] = description
        if status is not None:
            params["status"] = status
        if priority is not None:
            params["priority"] = priority
        if labels is not None:
            params["labels"] = labels
        return self._make_mcp_call("jira_update_issue", params)

    def add_jira_comment(self, issue_key: str, comment: str) -> MCPResponse:
        """Add a comment to a Jira issue."""
        if self.demo_mode:
            logger.info("[DEMO] jira_add_comment(%s)", issue_key)
            return MCPResponse(success=True, data={"issue_key": issue_key, "added": True})
        return self._make_mcp_call(
            "jira_add_comment", {"issue_key": issue_key, "comment": comment}
        )

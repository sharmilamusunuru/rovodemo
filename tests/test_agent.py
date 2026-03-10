"""
Tests for the Rovo MCP Demo project.

All tests run in demo mode so no real Atlassian credentials are needed.
"""

import os
import pytest

# Ensure demo mode is on for all tests
os.environ.setdefault("DEMO_MODE", "true")

from src.mcp_client import AtlassianMCPClient, MCPResponse
from src.confluence_reader import ConfluenceReader, ApplicationDocumentation
from src.analyzer import (
    ModernizationAnalyzer,
    ModernizationPlan,
    MigrationCategory,
    Priority,
)
from src.jira_manager import JiraTaskManager
from src.agent import RovoMCPAgent, AgentRunResult


# ---------------------------------------------------------------------------
# MCP Client tests
# ---------------------------------------------------------------------------

class TestAtlassianMCPClient:
    def setup_method(self):
        self.client = AtlassianMCPClient(demo_mode=True)

    def test_demo_mode_enabled(self):
        assert self.client.demo_mode is True

    def test_get_confluence_page_returns_success(self):
        response = self.client.get_confluence_page("123456")
        assert response.success is True
        assert response.data["id"] == "123456"
        assert "body" in response.data
        assert len(response.data["body"]) > 0

    def test_search_confluence_returns_results(self):
        response = self.client.search_confluence("eShop architecture")
        assert response.success is True
        results = response.data["results"]
        assert len(results) >= 1
        assert results[0]["title"] != ""

    def test_create_confluence_page_returns_id(self):
        response = self.client.create_confluence_page(
            space_key="ENG",
            title="Test Page",
            body="Hello world",
        )
        assert response.success is True
        assert "id" in response.data
        assert "url" in response.data

    def test_update_confluence_page(self):
        response = self.client.update_confluence_page(
            page_id="123", title="Updated", body="New body", version=2
        )
        assert response.success is True
        assert response.data["version"] == 3  # bumped

    def test_search_jira_issues_returns_list(self):
        response = self.client.search_jira_issues("project = ESHOP")
        assert response.success is True
        issues = response.data["issues"]
        assert len(issues) >= 1

    def test_get_jira_issue_found(self):
        response = self.client.get_jira_issue("ESHOP-1")
        assert response.success is True
        assert response.data["key"] == "ESHOP-1"

    def test_get_jira_issue_not_found(self):
        response = self.client.get_jira_issue("ESHOP-9999")
        assert response.success is False
        assert response.error is not None

    def test_create_jira_issue(self):
        response = self.client.create_jira_issue(
            project_key="ESHOP",
            summary="Test story",
            description="Some description",
        )
        assert response.success is True
        assert "key" in response.data
        assert "ESHOP" in response.data["key"]

    def test_update_jira_issue(self):
        response = self.client.update_jira_issue(
            issue_key="ESHOP-10",
            description="Updated description",
        )
        assert response.success is True
        assert response.data["updated"] is True

    def test_add_jira_comment(self):
        response = self.client.add_jira_comment("ESHOP-1", "Hello!")
        assert response.success is True

    def test_requires_credentials_without_demo_mode(self):
        # Should raise when demo_mode=False and no credentials
        with pytest.raises(ValueError, match="ATLASSIAN_BASE_URL"):
            AtlassianMCPClient(demo_mode=False)

    def test_demo_mode_via_env(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        client = AtlassianMCPClient()
        assert client.demo_mode is True


# ---------------------------------------------------------------------------
# Confluence Reader tests
# ---------------------------------------------------------------------------

class TestConfluenceReader:
    def setup_method(self):
        self.client = AtlassianMCPClient(demo_mode=True)
        self.reader = ConfluenceReader(self.client)

    def test_read_page_returns_page(self):
        page = self.reader.read_page("123456")
        assert page is not None
        assert page.page_id == "123456"
        assert page.title != ""
        assert len(page.body) > 0

    def test_search_documentation_returns_results(self):
        results = self.reader.search_documentation("eShop")
        assert len(results) >= 1
        assert results[0].page_id != ""
        assert results[0].title != ""

    def test_read_application_documentation_with_page_id(self):
        doc = self.reader.read_application_documentation(page_id="123456")
        assert len(doc.pages) == 1
        assert doc.raw_content != ""

    def test_read_application_documentation_search(self):
        doc = self.reader.read_application_documentation(space_key="ENG")
        assert len(doc.pages) >= 1
        assert doc.raw_content != ""

    def test_combined_text_includes_all_pages(self):
        doc = self.reader.read_application_documentation(space_key="ENG")
        combined = doc.combined_text()
        for page in doc.pages:
            assert page.title in combined


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------

class TestModernizationAnalyzer:
    def setup_method(self):
        self.analyzer = ModernizationAnalyzer()

    def _make_doc(self, text: str) -> ApplicationDocumentation:
        doc = ApplicationDocumentation()
        doc.raw_content = text
        return doc

    def test_empty_documentation_returns_plan(self):
        doc = self._make_doc("")
        plan = self.analyzer.analyze(doc)
        assert isinstance(plan, ModernizationPlan)
        assert "No documentation" in plan.summary

    def test_detects_security_issue_md5(self):
        doc = self._make_doc("Passwords stored as MD5 hashes (legacy security risk)")
        plan = self.analyzer.analyze(doc)
        titles = [t.title for t in plan.tasks]
        assert any("Authentication" in t or "Password" in t or "Security" in t for t in titles)

    def test_detects_database_migration(self):
        doc = self._make_doc("Using SQL Server 2014 on-premises with ADO.NET direct queries")
        plan = self.analyzer.analyze(doc)
        categories = [t.category for t in plan.tasks]
        assert MigrationCategory.MODERNIZATION in categories

    def test_detects_msmq(self):
        doc = self._make_doc("Order processing uses MSMQ queue")
        plan = self.analyzer.analyze(doc)
        azure_services = [t.azure_service for t in plan.tasks]
        assert any("Service Bus" in s for s in azure_services)

    def test_detects_scalability_issues(self):
        doc = self._make_doc("In-proc session and local file storage prevent horizontal scaling")
        plan = self.analyzer.analyze(doc)
        categories = [t.category for t in plan.tasks]
        assert MigrationCategory.SCALABILITY in categories

    def test_tasks_by_priority_order(self):
        doc = self._make_doc(
            "MD5 password hashing. MSMQ queue. SQL Server 2014. monitoring missing."
        )
        plan = self.analyzer.analyze(doc)
        ordered = plan.tasks_by_priority()
        priorities = [t.priority for t in ordered]
        order_index = {p: i for i, p in enumerate([
            Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW
        ])}
        for i in range(len(priorities) - 1):
            assert order_index[priorities[i]] <= order_index[priorities[i + 1]]

    def test_task_jira_description_format(self):
        doc = self._make_doc("MD5 password hashing is a legacy security risk")
        plan = self.analyzer.analyze(doc)
        assert len(plan.tasks) >= 1
        description = plan.tasks[0].to_jira_description()
        assert "*Category:*" in description
        assert "*Priority:*" in description
        assert "*Azure Service:*" in description
        assert "*Estimated Effort:*" in description

    def test_full_sample_doc_produces_multiple_tasks(self):
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "eshop_documentation.md"
        )
        with open(sample_path, encoding="utf-8") as fh:
            content = fh.read()
        doc = self._make_doc(content)
        plan = self.analyzer.analyze(doc)
        assert len(plan.tasks) >= 5


# ---------------------------------------------------------------------------
# Jira Manager tests
# ---------------------------------------------------------------------------

class TestJiraTaskManager:
    def setup_method(self):
        self.client = AtlassianMCPClient(demo_mode=True)
        self.manager = JiraTaskManager(self.client, project_key="ESHOP", epic_key="ESHOP-1")
        self.analyzer = ModernizationAnalyzer()

    def _sample_plan(self) -> ModernizationPlan:
        doc = ApplicationDocumentation()
        doc.raw_content = (
            "MD5 password hashing. MSMQ. SQL Server 2014. in-proc session. "
            "local file storage. no CI/CD. missing logging."
        )
        return self.analyzer.analyze(doc)

    def test_sync_plan_returns_results(self):
        plan = self._sample_plan()
        results = self.manager.sync_plan(plan)
        assert len(results) == len(plan.tasks)

    def test_sync_plan_all_succeed(self):
        plan = self._sample_plan()
        results = self.manager.sync_plan(plan)
        for r in results:
            assert r.succeeded, f"Task failed: {r.summary} – {r.error}"

    def test_sync_plan_creates_or_updates(self):
        plan = self._sample_plan()
        results = self.manager.sync_plan(plan)
        actions = {r.action for r in results}
        assert actions <= {"created", "updated", "skipped"}

    def test_epic_summary_comment(self):
        plan = self._sample_plan()
        results = self.manager.sync_plan(plan)
        success = self.manager.create_epic_summary_comment("ESHOP-1", plan, results)
        assert success is True


# ---------------------------------------------------------------------------
# Full agent integration test
# ---------------------------------------------------------------------------

class TestRovoMCPAgent:
    def test_full_run_demo_mode(self):
        agent = RovoMCPAgent(
            confluence_space="ENG",
            jira_project_key="ESHOP",
            jira_epic_key="ESHOP-1",
            demo_mode=True,
        )
        result = agent.run()
        assert result.succeeded, f"Agent failed: {result.errors}"
        assert result.documentation is not None
        assert result.plan is not None
        assert len(result.plan.tasks) >= 1
        assert result.tasks_created + result.tasks_updated > 0

    def test_agent_result_summary(self):
        agent = RovoMCPAgent(demo_mode=True)
        result = agent.run()
        summary = result.summary()
        assert "Agent Run Summary" in summary
        assert "created" in summary

    def test_agent_default_demo_mode(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        agent = RovoMCPAgent()
        assert agent.demo_mode is True

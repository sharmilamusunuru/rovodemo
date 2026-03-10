"""
Rovo MCP Demo Agent

Orchestrates the full AI-assisted modernization planning workflow:

1. Read eShop application documentation from Confluence
2. Analyse modernization requirements
3. Create / update Jira tasks for the Azure migration

Run with:
    python -m src.agent          # uses DEMO_MODE=true by default
    DEMO_MODE=false python -m src.agent   # requires real Atlassian credentials
"""

import logging
import os
import sys
from dataclasses import dataclass, field

from .analyzer import ModernizationAnalyzer, ModernizationPlan
from .confluence_reader import ApplicationDocumentation, ConfluenceReader
from .jira_manager import JiraTaskManager, JiraTaskResult
from .mcp_client import AtlassianMCPClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent result
# ---------------------------------------------------------------------------

@dataclass
class AgentRunResult:
    """Summary of a completed agent run."""

    documentation: ApplicationDocumentation | None = None
    plan: ModernizationPlan | None = None
    task_results: list[JiraTaskResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors

    @property
    def tasks_created(self) -> int:
        return sum(1 for r in self.task_results if r.action == "created")

    @property
    def tasks_updated(self) -> int:
        return sum(1 for r in self.task_results if r.action == "updated")

    def summary(self) -> str:
        lines = ["=== Agent Run Summary ==="]
        if self.documentation:
            lines.append(
                f"  Documentation: {len(self.documentation.pages)} page(s) read"
            )
        if self.plan:
            lines.append(
                f"  Analysis:      {len(self.plan.tasks)} migration task(s) identified"
            )
        lines += [
            f"  Jira:          {self.tasks_created} created, "
            f"{self.tasks_updated} updated",
        ]
        if self.errors:
            lines += [f"  Errors ({len(self.errors)}):"]
            for e in self.errors:
                lines.append(f"    - {e}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class RovoMCPAgent:
    """
    AI agent that uses Atlassian Rovo MCP to plan eShop Azure migration.

    Parameters
    ----------
    confluence_space:
        The Confluence space key to search for documentation.
    confluence_page_id:
        Optional specific page ID to read instead of searching.
    jira_project_key:
        Jira project key where tasks are managed.
    jira_epic_key:
        Optional epic key to link new stories to.
    demo_mode:
        When True, no real Atlassian API calls are made.
    """

    def __init__(
        self,
        confluence_space: str = "ENG",
        confluence_page_id: str | None = None,
        jira_project_key: str = "ESHOP",
        jira_epic_key: str | None = None,
        demo_mode: bool | None = None,
    ):
        if demo_mode is None:
            demo_mode = os.environ.get("DEMO_MODE", "true").lower() != "false"

        self.demo_mode = demo_mode
        self.confluence_space = confluence_space
        self.confluence_page_id = confluence_page_id
        self.jira_project_key = jira_project_key
        self.jira_epic_key = jira_epic_key

        self.mcp_client = AtlassianMCPClient(demo_mode=demo_mode)
        self.confluence_reader = ConfluenceReader(self.mcp_client)
        self.analyzer = ModernizationAnalyzer()
        self.jira_manager = JiraTaskManager(
            self.mcp_client,
            project_key=jira_project_key,
            epic_key=jira_epic_key,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> AgentRunResult:
        """Execute the full modernization planning workflow."""
        result = AgentRunResult()
        mode_label = "DEMO" if self.demo_mode else "LIVE"
        logger.info("Starting Rovo MCP Demo Agent [%s MODE]", mode_label)
        _print_banner(mode_label)

        # Step 1 – Read documentation from Confluence
        print("\n[Step 1/3] Reading eShop documentation from Confluence …")
        try:
            documentation = self.confluence_reader.read_application_documentation(
                space_key=self.confluence_space,
                page_id=self.confluence_page_id,
            )
            result.documentation = documentation
            print(
                f"  ✓ {len(documentation.pages)} page(s) retrieved "
                f"({len(documentation.raw_content)} characters)"
            )
        except Exception as exc:
            msg = f"Failed to read Confluence documentation: {exc}"
            result.errors.append(msg)
            logger.exception(msg)
            return result

        # Step 2 – Analyse modernization requirements
        print("\n[Step 2/3] Analysing modernization requirements …")
        try:
            # Supplement with local sample data if pages returned empty content
            if not documentation.raw_content.strip():
                logger.info("Supplementing with local sample documentation.")
                documentation.raw_content = _load_local_sample()

            plan = self.analyzer.analyze(documentation)
            result.plan = plan
            print(f"  ✓ {len(plan.tasks)} migration task(s) identified")
            _print_plan_summary(plan)
        except Exception as exc:
            msg = f"Failed to analyse documentation: {exc}"
            result.errors.append(msg)
            logger.exception(msg)
            return result

        # Step 3 – Sync tasks to Jira
        print("\n[Step 3/3] Syncing migration tasks to Jira …")
        try:
            task_results = self.jira_manager.sync_plan(plan)
            result.task_results = task_results
            print(
                f"  ✓ {result.tasks_created} task(s) created, "
                f"{result.tasks_updated} task(s) updated"
            )
            _print_task_results(task_results)

            # Post summary comment on epic if one was provided
            epic = self.jira_epic_key or os.environ.get("JIRA_EPIC_KEY")
            if epic:
                self.jira_manager.create_epic_summary_comment(epic, plan, task_results)
                print(f"  ✓ Summary comment added to epic {epic}")
        except Exception as exc:
            msg = f"Failed to sync Jira tasks: {exc}"
            result.errors.append(msg)
            logger.exception(msg)

        print(f"\n{result.summary()}")
        return result


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _print_banner(mode: str) -> None:
    width = 60
    print("=" * width)
    print(f"  Atlassian Rovo MCP – eShop Modernization Agent [{mode}]")
    print("=" * width)


def _print_plan_summary(plan: ModernizationPlan) -> None:
    print(f"\n  Summary: {plan.summary[:120]}{'…' if len(plan.summary) > 120 else ''}")
    if plan.recommended_phases:
        print("\n  Recommended Phases:")
        for phase in plan.recommended_phases:
            print(f"    • {phase}")
    print()
    print(f"  {'Priority':<10} {'Category':<22} Task")
    print(f"  {'-'*10} {'-'*22} {'-'*40}")
    for task in plan.tasks_by_priority():
        print(
            f"  {task.priority.value:<10} {task.category.value:<22} {task.title}"
        )


def _print_task_results(results: list[JiraTaskResult]) -> None:
    print()
    for r in results:
        icon = "✅" if r.succeeded else "❌"
        action = r.action.upper()
        url_part = f" → {r.url}" if r.url else ""
        error_part = f" ({r.error})" if r.error else ""
        print(f"  {icon} [{action}] {r.issue_key or '???'}: {r.summary}{url_part}{error_part}")


def _load_local_sample() -> str:
    """Load the bundled sample documentation as a fallback."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample_path = os.path.join(here, "data", "eshop_documentation.md")
    if os.path.exists(sample_path):
        with open(sample_path, encoding="utf-8") as fh:
            return fh.read()
    return ""


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    confluence_space = os.environ.get("CONFLUENCE_SPACE_KEY", "ENG")
    confluence_page_id = os.environ.get("CONFLUENCE_PAGE_ID")
    jira_project = os.environ.get("JIRA_PROJECT_KEY", "ESHOP")
    jira_epic = os.environ.get("JIRA_EPIC_KEY", "ESHOP-1")

    agent = RovoMCPAgent(
        confluence_space=confluence_space,
        confluence_page_id=confluence_page_id,
        jira_project_key=jira_project,
        jira_epic_key=jira_epic,
    )

    run_result = agent.run()
    return 0 if run_result.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())

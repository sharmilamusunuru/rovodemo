"""
Modernization Analyzer

Analyzes eShop application documentation and produces a structured
modernization plan for Azure migration.  When an OpenAI or Anthropic
API key is configured the analyzer calls the LLM; otherwise it falls
back to a deterministic rule-based analysis that is always available.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum

from .confluence_reader import ApplicationDocumentation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class MigrationCategory(str, Enum):
    SECURITY = "Security"
    SCALABILITY = "Scalability"
    RELIABILITY = "Reliability"
    PERFORMANCE = "Performance"
    OBSERVABILITY = "Observability"
    MODERNIZATION = "Modernization"
    COST_OPTIMIZATION = "Cost Optimization"
    COMPLIANCE = "Compliance"
    DEVOPS = "DevOps"


@dataclass
class MigrationTask:
    """A single actionable migration task derived from analysis."""

    title: str
    description: str
    category: MigrationCategory
    priority: Priority
    azure_service: str
    estimated_effort: str  # e.g. "2 weeks"
    acceptance_criteria: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    def to_jira_description(self) -> str:
        """Format the task as a Jira issue description."""
        lines = [
            f"*Category:* {self.category.value}",
            f"*Priority:* {self.priority.value}",
            f"*Azure Service:* {self.azure_service}",
            f"*Estimated Effort:* {self.estimated_effort}",
            "",
            "*Description:*",
            self.description,
        ]
        if self.acceptance_criteria:
            lines += ["", "*Acceptance Criteria:*"]
            lines += [f"* {c}" for c in self.acceptance_criteria]
        return "\n".join(lines)


@dataclass
class ModernizationPlan:
    """The complete modernization plan produced by the analyzer."""

    summary: str
    tasks: list[MigrationTask] = field(default_factory=list)
    risk_assessment: str = ""
    recommended_phases: list[str] = field(default_factory=list)

    def tasks_by_priority(self) -> list[MigrationTask]:
        order = [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW]
        return sorted(self.tasks, key=lambda t: order.index(t.priority))


# ---------------------------------------------------------------------------
# Rule-based keyword detection helpers
# ---------------------------------------------------------------------------

_KEYWORD_CATEGORIES: list[tuple[list[str], MigrationCategory, Priority, str, str, str, list[str]]] = [
    (
        ["md5", "password", "hash", "auth"],
        MigrationCategory.SECURITY,
        Priority.CRITICAL,
        "Modernize Authentication and Password Security",
        "Replace MD5 password hashing with bcrypt/Argon2 and migrate "
        "authentication to Azure Active Directory B2C.",
        "Azure Active Directory B2C",
        "3 weeks",
    ),
    (
        ["sql server 2014", "sql server", "database", "ado.net"],
        MigrationCategory.MODERNIZATION,
        Priority.HIGH,
        "Migrate Database to Azure SQL Database",
        "Migrate the on-premises SQL Server 2014 instance to Azure SQL Database "
        "(General Purpose tier) to gain managed patches, high availability, and "
        "elastic scaling.",
        "Azure SQL Database",
        "4 weeks",
    ),
    (
        ["msmq", "queue", "order processing", "messaging"],
        MigrationCategory.RELIABILITY,
        Priority.HIGH,
        "Replace MSMQ with Azure Service Bus",
        "Replace MSMQ with Azure Service Bus for durable, scalable, and "
        "cloud-native message queuing with built-in dead-letter support.",
        "Azure Service Bus",
        "2 weeks",
    ),
    (
        ["local disk", "file server", "file storage", "upload"],
        MigrationCategory.SCALABILITY,
        Priority.HIGH,
        "Migrate File Storage to Azure Blob Storage",
        "Move product images and user uploads from local disk / file server to "
        "Azure Blob Storage with Azure CDN for global delivery.",
        "Azure Blob Storage + Azure CDN",
        "1 week",
    ),
    (
        ["session", "in-proc", "inproc", "scale", "horizontal"],
        MigrationCategory.SCALABILITY,
        Priority.HIGH,
        "Externalize Session State with Azure Cache for Redis",
        "Move ASP.NET session state from in-process memory to Azure Cache for "
        "Redis to enable horizontal scaling of web tier.",
        "Azure Cache for Redis",
        "1 week",
    ),
    (
        ["search", "full table scan", "like query", "performance"],
        MigrationCategory.PERFORMANCE,
        Priority.MEDIUM,
        "Implement Azure AI Search for Product Catalog",
        "Replace SQL LIKE-based product search with Azure AI Search for "
        "full-text, faceted, and relevance-ranked search at scale.",
        "Azure AI Search",
        "3 weeks",
    ),
    (
        ["ci/cd", "deployment", "manual deploy", "pipeline"],
        MigrationCategory.DEVOPS,
        Priority.MEDIUM,
        "Establish CI/CD Pipeline with Azure DevOps",
        "Create Azure DevOps pipelines (build + release) to automate testing "
        "and deployment, eliminating manual deployment steps.",
        "Azure DevOps",
        "2 weeks",
    ),
    (
        ["logging", "tracing", "metrics", "observability", "monitor"],
        MigrationCategory.OBSERVABILITY,
        Priority.MEDIUM,
        "Implement Observability with Azure Monitor and Application Insights",
        "Integrate Application Insights SDK for distributed tracing, structured "
        "logging, and custom metrics; set up Azure Monitor dashboards and alerts.",
        "Azure Monitor + Application Insights",
        "1 week",
    ),
    (
        ["vm", "virtual machine", "over-prov", "cost", "utilization"],
        MigrationCategory.COST_OPTIMIZATION,
        Priority.MEDIUM,
        "Right-Size and Containerize Application Workloads",
        "Containerize the application using Docker and deploy to Azure Kubernetes "
        "Service (AKS) with auto-scaling to reduce over-provisioning costs.",
        "Azure Kubernetes Service (AKS)",
        "6 weeks",
    ),
    (
        ["pci", "gdpr", "compliance"],
        MigrationCategory.COMPLIANCE,
        Priority.HIGH,
        "Implement PCI-DSS and GDPR Compliance Controls",
        "Leverage Azure Policy, Azure Key Vault, and Microsoft Defender for Cloud "
        "to enforce PCI-DSS and GDPR controls across the migrated platform.",
        "Azure Policy + Azure Key Vault + Microsoft Defender for Cloud",
        "3 weeks",
    ),
    (
        [".net framework", "webforms", "asp.net", "legacy", "moderniz"],
        MigrationCategory.MODERNIZATION,
        Priority.MEDIUM,
        "Modernize Application to .NET 8 and Microservices",
        "Incrementally re-platform eShop from .NET Framework 4.7 WebForms to "
        ".NET 8 with a microservices architecture deployed on Azure App Service "
        "or AKS.",
        "Azure App Service / AKS",
        "12 weeks",
    ),
    (
        ["smtp", "email", "notification"],
        MigrationCategory.MODERNIZATION,
        Priority.LOW,
        "Modernize Notifications with Azure Communication Services",
        "Replace legacy SMTP relay with Azure Communication Services for email, "
        "SMS, and push notifications with delivery tracking.",
        "Azure Communication Services",
        "1 week",
    ),
    (
        ["payment", "soap", "gateway", "tokeniz"],
        MigrationCategory.SECURITY,
        Priority.HIGH,
        "Modernize Payment Processing with Tokenization",
        "Replace legacy SOAP-based payment gateway with a PCI-compliant "
        "tokenized payment provider (e.g. Stripe, Adyen) integrated via secure "
        "Azure API Management.",
        "Azure API Management + Tokenized Payment Provider",
        "4 weeks",
    ),
]


def _detect_tasks_from_text(content: str) -> list[MigrationTask]:
    """Apply keyword matching to *content* and return detected tasks."""
    content_lower = content.lower()
    tasks: list[MigrationTask] = []
    seen_titles: set[str] = set()

    for keywords, category, priority, title, description, azure_service, effort in _KEYWORD_CATEGORIES:
        if title in seen_titles:
            continue
        if any(kw in content_lower for kw in keywords):
            seen_titles.add(title)
            tasks.append(
                MigrationTask(
                    title=title,
                    description=description,
                    category=category,
                    priority=priority,
                    azure_service=azure_service,
                    estimated_effort=effort,
                    labels=["azure-migration", "eshop", category.value.lower().replace(" ", "-")],
                    acceptance_criteria=_default_acceptance_criteria(category),
                )
            )
    return tasks


def _default_acceptance_criteria(category: MigrationCategory) -> list[str]:
    base = ["All existing functionality verified via regression tests"]
    extras: dict[MigrationCategory, list[str]] = {
        MigrationCategory.SECURITY: [
            "Penetration test passes with no critical findings",
            "Security review approved",
        ],
        MigrationCategory.SCALABILITY: [
            "Load test validates 10x baseline traffic with no degradation",
            "Horizontal scale-out verified",
        ],
        MigrationCategory.RELIABILITY: [
            "No message loss under simulated failure scenarios",
            "Dead-letter queue processing verified",
        ],
        MigrationCategory.PERFORMANCE: [
            "P95 search latency < 200 ms under load",
        ],
        MigrationCategory.OBSERVABILITY: [
            "Dashboards live in Azure Monitor",
            "Alerting configured for error rate and latency SLOs",
        ],
        MigrationCategory.DEVOPS: [
            "Zero-downtime blue/green deployment demonstrated",
            "Pipeline gates include automated test pass",
        ],
        MigrationCategory.COST_OPTIMIZATION: [
            "Infrastructure cost reduced by ≥ 30% vs baseline",
        ],
        MigrationCategory.COMPLIANCE: [
            "Azure Policy compliance score ≥ 95%",
            "Data protection impact assessment completed",
        ],
        MigrationCategory.MODERNIZATION: [
            "Feature parity with legacy system verified",
            ".NET 8 target framework confirmed",
        ],
    }
    return base + extras.get(category, [])


# ---------------------------------------------------------------------------
# LLM-based analysis (optional)
# ---------------------------------------------------------------------------

def _analyze_with_llm(content: str) -> ModernizationPlan | None:
    """
    Try to use an LLM (Anthropic Claude or OpenAI GPT-4o) for analysis.
    Returns *None* if no API key is configured.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not anthropic_key and not openai_key:
        return None

    prompt = (
        "You are a senior cloud architect specializing in Azure migrations.\n\n"
        "Analyse the following eShop application documentation and produce a "
        "structured Azure modernization plan.  Return valid JSON with this "
        "exact schema:\n"
        '{"summary": "...", "risk_assessment": "...", '
        '"recommended_phases": ["Phase 1: ...", "Phase 2: ..."]}\n\n'
        "Do not include the migration tasks in the JSON – only the three fields "
        "above.\n\nDocumentation:\n\n" + content[:8000]
    )

    try:
        if anthropic_key:
            import anthropic  # optional dependency

            client = anthropic.Anthropic(api_key=anthropic_key)
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
        else:
            import openai  # optional dependency

            client = openai.OpenAI(api_key=openai_key)
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            raw = completion.choices[0].message.content or ""

        # Extract JSON from the response
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            import json
            data = json.loads(json_match.group())
            return ModernizationPlan(
                summary=data.get("summary", ""),
                risk_assessment=data.get("risk_assessment", ""),
                recommended_phases=data.get("recommended_phases", []),
            )
    except Exception as exc:
        logger.warning("LLM analysis failed, falling back to rule-based: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class ModernizationAnalyzer:
    """
    Analyses eShop documentation and produces an Azure migration plan.

    Uses an LLM when API keys are present; falls back to keyword-based
    heuristics so the demo always produces meaningful output.
    """

    def analyze(self, documentation: ApplicationDocumentation) -> ModernizationPlan:
        content = documentation.raw_content or documentation.combined_text()
        if not content.strip():
            logger.warning("No documentation content to analyze.")
            return ModernizationPlan(summary="No documentation provided.")

        logger.info("Analyzing documentation (%d chars) …", len(content))

        # Attempt LLM-driven high-level plan
        plan = _analyze_with_llm(content)

        if plan is None:
            logger.info("Using rule-based analysis (no LLM API key configured).")
            plan = ModernizationPlan(
                summary=(
                    "The eShop application requires a comprehensive modernization to move "
                    "from a legacy on-premises .NET Framework 4.7 stack to a cloud-native "
                    "Azure architecture.  Key areas include security hardening, scalability "
                    "improvements, reliability via managed messaging, and operational maturity "
                    "through CI/CD and observability."
                ),
                risk_assessment=(
                    "HIGH: MD5 password hashing is an active security vulnerability. "
                    "MEDIUM: MSMQ single point of failure risks order loss. "
                    "MEDIUM: SQL Server 2014 end-of-support increases compliance risk. "
                    "LOW: Over-provisioned VMs inflate operating costs."
                ),
                recommended_phases=[
                    "Phase 1 – Security & Quick Wins (Weeks 1-4): "
                    "Fix MD5 hashing, externalize sessions, migrate file storage, "
                    "add Application Insights.",
                    "Phase 2 – Data & Messaging (Weeks 5-10): "
                    "Migrate to Azure SQL Database, replace MSMQ with Service Bus, "
                    "modernize payment processing.",
                    "Phase 3 – Scalability & Performance (Weeks 11-16): "
                    "Containerize to AKS, implement Azure AI Search, set up CI/CD.",
                    "Phase 4 – Full Modernization (Weeks 17-28): "
                    "Re-platform to .NET 8 microservices, implement compliance controls, "
                    "modernize notifications.",
                ],
            )

        # Always use rule-based task detection (comprehensive regardless of LLM)
        plan.tasks = _detect_tasks_from_text(content)
        logger.info("Analysis complete: %d migration task(s) identified.", len(plan.tasks))
        return plan

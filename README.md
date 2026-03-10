# Atlassian Rovo MCP – eShop Modernization Agent

A working demo that shows how an AI agent uses the **Atlassian Rovo Model Context Protocol (MCP)** to:

1. 📄 **Read** eShop application documentation from **Confluence**
2. 🧠 **Analyse** modernization requirements for an Azure migration
3. 📋 **Create / update** Jira tasks for every identified migration work item

> **Demo mode** is enabled by default – no real Atlassian credentials are required
> to run the demo locally.

---

## Project Structure

```
rovodemo/
├── src/
│   ├── agent.py            # Main orchestrator / CLI entry-point
│   ├── mcp_client.py       # Atlassian Rovo MCP client (Confluence + Jira)
│   ├── confluence_reader.py# Reads & searches Confluence pages
│   ├── analyzer.py         # Analyses docs → migration plan (rule-based + LLM)
│   └── jira_manager.py     # Creates / updates Jira stories & comments
├── tests/
│   └── test_agent.py       # 33 unit + integration tests (all in demo mode)
├── data/
│   └── eshop_documentation.md   # Sample eShop app docs (used as fallback)
├── config/
│   └── mcp_config.example.json  # MCP server configuration template
├── .env.example            # Environment variable reference
├── requirements.txt
└── pytest.ini
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    RovoMCPAgent                             │
│                                                             │
│  Step 1: ConfluenceReader                                   │
│    └─ AtlassianMCPClient.search_confluence(...)             │
│    └─ AtlassianMCPClient.get_confluence_page(...)           │
│          │                                                  │
│          ▼                                                  │
│  Step 2: ModernizationAnalyzer                              │
│    └─ Keyword rules (always)  +  LLM summary (optional)     │
│    └─ Produces ModernizationPlan with MigrationTask list    │
│          │                                                  │
│          ▼                                                  │
│  Step 3: JiraTaskManager                                    │
│    └─ AtlassianMCPClient.search_jira_issues(...)  ← find   │
│    └─ AtlassianMCPClient.create_jira_issue(...)   ← new    │
│    └─ AtlassianMCPClient.update_jira_issue(...)   ← exist  │
│    └─ AtlassianMCPClient.add_jira_comment(...)    ← epic   │
└─────────────────────────────────────────────────────────────┘
```

### MCP Tool calls used

| Tool | Purpose |
|---|---|
| `confluence_search` | Find eShop documentation pages |
| `confluence_get_page` | Retrieve page content |
| `confluence_create_page` | Publish new documentation |
| `confluence_update_page` | Update existing pages |
| `jira_search_issues` | Look up existing migration stories |
| `jira_create_issue` | Create new Jira stories |
| `jira_update_issue` | Refresh descriptions & labels |
| `jira_add_comment` | Post AI analysis summaries |

---

## Quick Start

### 1 – Install dependencies

```bash
pip install -r requirements.txt
```

### 2 – Run in demo mode (no credentials needed)

```bash
python -m src.agent
```

The agent will:
- Simulate Confluence MCP calls with bundled sample data
- Identify 12 Azure migration tasks from the eShop documentation
- Simulate creating Jira stories with prioritised descriptions

### 3 – Run with real Atlassian credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# edit .env with your Atlassian URL, API token, email, and project keys
```

Set `DEMO_MODE=false` and source your env:

```bash
export $(grep -v '^#' .env | xargs)
python -m src.agent
```

### 4 – Optional: LLM-enhanced analysis

Add an LLM API key for AI-powered narrative summaries alongside the rule-based task detection:

```bash
# Anthropic Claude (recommended)
export ANTHROPIC_API_KEY=sk-ant-...

# or OpenAI GPT-4o
export OPENAI_API_KEY=sk-...

python -m src.agent
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DEMO_MODE` | `true` | `true` = no real API calls; `false` = live mode |
| `ATLASSIAN_BASE_URL` | *(required in live mode)* | e.g. `https://yourorg.atlassian.net` |
| `ATLASSIAN_API_TOKEN` | *(required in live mode)* | Atlassian API token |
| `ATLASSIAN_USER_EMAIL` | *(required in live mode)* | Your Atlassian account email |
| `CONFLUENCE_SPACE_KEY` | `ENG` | Confluence space to search |
| `CONFLUENCE_PAGE_ID` | *(optional)* | Specific page ID (skips search) |
| `JIRA_PROJECT_KEY` | `ESHOP` | Jira project for migration tasks |
| `JIRA_EPIC_KEY` | `ESHOP-1` | Epic to link stories to & comment on |
| `ANTHROPIC_API_KEY` | *(optional)* | Enables Claude-powered analysis |
| `OPENAI_API_KEY` | *(optional)* | Enables GPT-4o-powered analysis |

---

## MCP Server Setup

For live mode you need the Atlassian MCP servers running. Copy the config template:

```bash
cp config/mcp_config.example.json config/mcp_config.json
# substitute your credentials in the env section
```

The MCP servers are started via `npx` (Node.js required):

```bash
# Confluence MCP
npx -y @atlassian/mcp-confluence

# Jira MCP
npx -y @atlassian/mcp-jira
```

See `config/mcp_config.example.json` for the full server configuration.

---

## Running Tests

```bash
pytest
```

All 33 tests run in demo mode without any Atlassian credentials:

```
tests/test_agent.py::TestAtlassianMCPClient   (13 tests)
tests/test_agent.py::TestConfluenceReader     (5 tests)
tests/test_agent.py::TestModernizationAnalyzer (8 tests)
tests/test_agent.py::TestJiraTaskManager      (4 tests)
tests/test_agent.py::TestRovoMCPAgent         (3 tests)
```

---

## Migration Tasks Detected

The analyser identifies migration tasks in the following categories from the documentation:

| Category | Example Azure Service |
|---|---|
| 🔐 Security | Azure Active Directory B2C |
| 🗄 Modernization | Azure SQL Database, .NET 8 |
| 📨 Reliability | Azure Service Bus |
| 📈 Scalability | Azure Blob Storage, Azure Cache for Redis |
| 🔍 Performance | Azure AI Search |
| ⚙ DevOps | Azure DevOps CI/CD |
| 📊 Observability | Azure Monitor + Application Insights |
| 💰 Cost Optimization | Azure Kubernetes Service (AKS) |
| 📜 Compliance | Azure Policy + Key Vault |
| 💳 Payment | Azure API Management + Tokenized Provider |

---

## Extending the Demo

- **Add more MCP tools**: extend `AtlassianMCPClient` with additional tool methods
- **Custom detection rules**: add entries to `_KEYWORD_CATEGORIES` in `analyzer.py`
- **New data sources**: add more readers alongside `confluence_reader.py`
- **Different Jira workflows**: customise `JiraTaskManager.sync_plan()`

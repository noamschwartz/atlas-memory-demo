# Elastic Agent Builder MCP Server - Research Notes

> **Research Date**: December 10, 2025\
> **Purpose**: Understanding how to use MCP with Elastic Agent Builder

______________________________________________________________________

## Executive Summary

The **Model Context Protocol (MCP) server** is a new Elastic Agent Builder feature (9.2.0+) that exposes Agent Builder tools to external AI clients like Cursor IDE, Claude Desktop, and VS Code. This is **complementary** to (not replacing) the A2A protocol - they serve different use cases.

| Protocol | Use Case                      | Who Uses It                       |
| -------- | ----------------------------- | --------------------------------- |
| **MCP**  | Expose tools to IDE AI agents | Developers in Cursor/VS Code      |
| **A2A**  | Agent-to-agent delegation     | Multi-agent orchestration systems |
| **API**  | Full programmatic control     | Custom applications               |

______________________________________________________________________

## 1. What is MCP?

**Model Context Protocol (MCP)** is an open standard that allows an AI model or agent to discover and use external tools. It's the "bring your own tools" approach - you augment the IDE's AI assistant with specialized, data-aware tools from Elastic.

### Key Benefits

- Give IDE AI agents (Cursor, Claude Desktop) access to your **private Elasticsearch data**
- Tools execute with **API key permissions**, respecting access control
- No need to build custom integrations - just configure the MCP client

### MCP Server Endpoint

```text
{KIBANA_URL}/api/agent_builder/mcp
```

For custom Kibana spaces:

```text
{KIBANA_URL}/s/{SPACE_NAME}/api/agent_builder/mcp
```

> ⚠️ **Known Issue (9.2)**: The "Copy MCP server URL" button in Tools UI omits the space name. Add it manually if using custom spaces.

______________________________________________________________________

## 2. MCP vs A2A - When to Use Which

| Scenario                                                 | Use     | Why                                      |
| -------------------------------------------------------- | ------- | ---------------------------------------- |
| Developer querying internal docs from Cursor             | **MCP** | IDE agent needs tools, not another agent |
| Multi-agent system where agents delegate tasks           | **A2A** | Agent-to-agent communication protocol    |
| Building a custom chat application                       | **API** | Full control over UI, streaming, state   |
| AI code editor accessing Elasticsearch data              | **MCP** | Direct tool access for IDE workflows     |
| Google Gemini Enterprise coordinating with Elastic agent | **A2A** | Peer agent delegation                    |

### Our Current Architecture

We currently use the **API approach** with a Backend Proxy pattern:

```text
Frontend (React) <-> Backend (FastAPI) <-> Elastic Agent Builder (Kibana)
```

MCP would add a **second access path** for developers:

```text
Cursor IDE <-> MCP Server <-> Elastic Agent Builder Tools
```

They can coexist! The app for end-users uses the API; developers can use MCP for their own workflows.

______________________________________________________________________

## 3. What Tools are Exposed via MCP?

### Built-in Tools (platform.core.\*)

| Tool                  | Description                               |
| --------------------- | ----------------------------------------- |
| `.execute_esql`       | Execute ES                                |
| `.generate_esql`      | Generate ES                               |
| `.get_document_by_id` | Retrieve full document by ID and index    |
| `.get_index_mapping`  | Get index mappings                        |
| `.index_explorer`     | List indices with mappings based on query |
| `.list_indices`       | List accessible indices                   |
| `.search`             | Search and analyze data in an index       |

### Custom Tools

- **Index search tools**: Scoped semantic search over specific indices
- **ES|QL tools**: Pre-defined queries with parameters

All tools created in Agent Builder are automatically exposed via MCP!

______________________________________________________________________

## 4. Authentication & Security

### API Key Privileges

MCP requires special Kibana application privileges:

#### Development API Key (unrestricted)

```json
POST /_security/api_key
{
  "name": "mcp-dev-key",
  "expiration": "1d",
  "role_descriptors": {
    "unrestricted": {
      "cluster": ["all"],
      "indices": [{"names": ["*"], "privileges": ["all"]}]
    }
  }
}
```

#### Production API Key (restricted)

```json
POST /_security/api_key
{
  "name": "mcp-prod-key",
  "expiration": "30d",
  "role_descriptors": {
    "mcp-access": {
      "cluster": ["all"],
      "indices": [
        {"names": ["*"], "privileges": ["read", "view_index_metadata"]}
      ],
      "applications": [
        {
          "application": "kibana-.kibana",
          "privileges": ["read_onechat", "space_read"],
          "resources": ["space:default"]
        }
      ]
    }
  }
}
```

**Critical privileges:**

- `read_onechat` - Required for MCP endpoint access
- `space_read` - Required for Kibana space access
- Without these → 403 Forbidden

______________________________________________________________________

## 5. Cursor IDE Configuration

### Configuration File Location

```text
~/.cursor/mcp.json
```

### Configuration Template

```json
{
  "mcpServers": {
    "elastic-agent-builder": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-kibana.kb.company.io/api/agent_builder/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "ApiKey YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Using Environment Variables

```json
{
  "mcpServers": {
    "elastic-agent-builder": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "${KIBANA_URL}/api/agent_builder/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "KIBANA_URL": "https://your-kibana.kb.company.io",
        "AUTH_HEADER": "ApiKey ${ELASTIC_MCP_API_KEY}"
      }
    }
  }
}
```

### Verification

After configuring, Cursor should show the Elastic Agent Builder MCP server in its tools list. You can then:

1. Ask questions that require Elasticsearch data
2. The AI will automatically select and invoke appropriate tools
3. Results are returned and incorporated into the AI's response

______________________________________________________________________

## 6. Example Workflow

From the Elastic Labs blog, a practical example:

**Use Case**: Developer needs internal engineering docs from Elasticsearch while coding

1. **Create Custom Tool** in Agent Builder:

   - Type: Index search
   - Index: `elastic-dev-docs`
   - Description: "Performs semantic search on internal engineering documentation"

2. **Configure Cursor** with MCP endpoint

3. **Ask Cursor**:

   > "Lookup steps to release crawler service from engineering internal documentation"

4. **Behind the scenes**:

   - Cursor agent analyzes the question
   - Decides to call `engineering_documentation_internal_search` tool
   - Tool executes semantic search against `elastic-dev-docs`
   - Returns relevant, up-to-date procedures
   - Cursor presents the answer

______________________________________________________________________

## 7. Comparison with Our Current Architecture

### Current: Backend Proxy Pattern

```text
┌─────────────────┐     ┌─────────────────┐     ┌────────────────────┐
│   React App     │────▶│  FastAPI Proxy  │────▶│  Agent Builder API │
│   (End Users)   │◀────│  (Auth, Stream) │◀────│  (Chat, Streaming) │
└─────────────────┘     └─────────────────┘     └────────────────────┘
```

### New: MCP for Developer Tools

```text
┌─────────────────┐                            ┌────────────────────┐
│   Cursor IDE    │───────────────────────────▶│  MCP Server        │
│   (Developers)  │◀───────────────────────────│  (Tools Only)      │
└─────────────────┘                            └────────────────────┘
```

### Key Difference

- **API/Chat**: Full agent conversations with streaming, history, multi-turn
- **MCP**: Direct tool invocation - no chat history, no agent orchestration
- **A2A**: Agent-to-agent delegation with agent cards

______________________________________________________________________

## 8. Integration Opportunities

### For This Project

1. **Developer Experience**: Configure Cursor to access Elasticsearch data via MCP
2. **Testing**: Use MCP to test tool outputs directly from IDE
3. **Documentation**: Document MCP setup for team onboarding

### For Template/Hive-Mind

1. Create `MCP_SERVER_INTEGRATION.md` pattern
2. Add MCP config examples to CLAUDE.md/.cursorrules
3. Document API key privilege requirements
4. Add troubleshooting section for common MCP issues

______________________________________________________________________

## 9. Comparison with Existing Hive-Mind Patterns

### How MCP Relates to Our Documented Patterns

| Pattern                           | Purpose                          | MCP Relevance                                    |
| --------------------------------- | -------------------------------- | ------------------------------------------------ |
| `AGENT_BUILDER_INTEGRATION.md`    | Backend proxy for streaming chat | MCP is orthogonal - direct tool access, not chat |
| `A2A_COORDINATOR_PATTERN.md`      | Multi-agent orchestration        | MCP complements A2A - different use cases        |
| `STREAMING_CHAT_UI_PATTERNS.md`   | Frontend SSE consumption         | Not applicable - MCP handled by IDE              |
| `AGENT_BUILDER_API_MANAGEMENT.md` | API key setup, tool creation     | **Directly relevant** - same tools exposed       |

### Key Insights from Comparison

1. **Same Tools, Different Access Pattern**

   - Our API pattern: `POST /api/agent_builder/converse/async` → SSE streaming
   - MCP pattern: Direct tool invocation via standard MCP protocol
   - Both access the SAME underlying tools

2. **Authentication Alignment**

   - We already use API keys with `ELASTIC_API_KEY`
   - MCP needs same key BUT may need additional privileges (`read_onechat`)
   - Check: `cat backend/.env | grep ELASTIC_API_KEY` - need to verify privileges

3. **No Streaming in MCP**

   - Our chat UI relies on SSE streaming for UX
   - MCP is request/response - tool results returned directly
   - This is expected - IDE agents handle their own streaming

4. **Complementary Workflows**

   - End users: Continue using our React app with streaming
   - Developers: Use MCP in Cursor for quick data queries during coding
   - Both can coexist with same Elasticsearch data

### Pattern Gap: MCP Not Yet Documented

The hive-mind is missing a pattern for MCP integration. This research supports creating:

- `hive-mind/patterns/agent-builder/MCP_SERVER_INTEGRATION.md`

______________________________________________________________________

## 10. Testing Results (December 10, 2025)

### ✅ MCP IS WORKING(!)

| Check             | Result         | Notes                     |
| ----------------- | -------------- | ------------------------- |
| Kibana Version    | ✅ 9.3.0       | Meets 9.2.0+ requirement  |
| Agent Builder API | ✅ Working     | Found 2 agents            |
| MCP Server        | ✅ **Working** | elastic-mcp-server v0.0.1 |
| Tools Available   | ✅ 14 tools    | 7 built-in + 7 custom     |

### Key Finding: MCP Uses JSON-RPC 2.0 Protocol

**Important**: A simple GET request to `/api/agent_builder/mcp` returns 404. This is expected because **MCP uses JSON-RPC 2.0 over HTTP POST**.

### Test Command

```bash
python backend/scripts/test_mcp_endpoint.py
```

### MCP Protocol Details

MCP requires:

1. **HTTP POST** (not GET)
2. **JSON-RPC 2.0** request format
3. **Accept: application/json** header (critical!)
4. **Authorization: ApiKey** header

### Example: Initialize Connection

```bash
curl -X POST "${KIBANA_URL}/api/agent_builder/mcp" \
  -H "Authorization: ApiKey ${ELASTIC_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0.0"}
    }
  }'
```

### Example: List Tools

```bash
curl -X POST "${KIBANA_URL}/api/agent_builder/mcp" \
  -H "Authorization: ApiKey ${ELASTIC_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 2, "params": {}}'
```

### Example: Call a Tool

```bash
curl -X POST "${KIBANA_URL}/api/agent_builder/mcp" \
  -H "Authorization: ApiKey ${ELASTIC_API_KEY}" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "your-custom-tool-name",
      "arguments": {"query": "your search query"}
    }
  }'
```

### Tools Available via MCP

**Built-in (7):**

- `platform_core_search` - Semantic search across indices
- `platform_core_get_document_by_id` - Get document by ID
- `platform_core_execute_esql` - Run ES|QL queries
- `platform_core_generate_esql` - Generate ES|QL from natural language
- `platform_core_get_index_mapping` - Get index mappings
- `platform_core_list_indices` - List all indices
- `platform_core_index_explorer` - Find relevant indices

**Custom Tools:**
Custom tools will vary based on your Agent Builder configuration. Examples might include:

- Semantic search tools for your indices
- Document retrieval tools
- Custom ES|QL query tools

### Indices Available

Your available indices will depend on your Elasticsearch deployment and API key permissions.

______________________________________________________________________

## 11. Open Questions (For Future Testing)

Now that MCP is confirmed working, these can be tested:

- [ ] How do custom tools appear in Cursor's tool list? (Configure Cursor to test)
- [ ] Can we scope MCP access to specific tools/indices? (Test with restricted API key)
- [ ] How does tool selection work with multiple similar tools?
- [ ] What's the latency compared to direct API calls?
- [x] ~~Can MCP handle streaming responses?~~ → MCP is request/response, not streaming

______________________________________________________________________

## 12. References

- [Elastic MCP Server Documentation](https://www.elastic.co/docs/solutions/search/agent-builder/mcp-server)
- [Elastic Search Labs Blog - MCP Server](https://www.elastic.co/search-labs/blog/elastic-mcp-server-agent-builder-tools)
- [Tools in Agent Builder](https://www.elastic.co/docs/solutions/search/agent-builder/tools)
- [A2A Server Documentation](https://www.elastic.co/docs/solutions/search/agent-builder/a2a-server)
- [Kibana API Reference](https://www.elastic.co/docs/api/doc/kibana/group/endpoint-agent-builder)

______________________________________________________________________

## 13. Next Steps

1. ✅ Research complete - documented in this file
2. ✅ MCP endpoint tested - **WORKING** with JSON-RPC 2.0 protocol
3. ✅ 14 tools discovered (7 built-in + 7 custom)
4. ⏳ Configure Cursor IDE with MCP - **READY**
5. ⏳ Test real workflow using MCP tools
6. ⏳ Create `MCP_SERVER_INTEGRATION.md` pattern for hive-mind

### Created Resources

- `backend/scripts/test_mcp_endpoint.py` - Full MCP test script with JSON-RPC
- `MCP_RESEARCH_NOTES.md` - This research document

### Cursor Configuration (Ready to Use)

```json
{
  "mcpServers": {
    "elastic-agent-builder": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-deployment.kb.region.gcp.elastic-cloud.com/api/agent_builder/mcp",
        "--header",
        "Authorization:ApiKey YOUR_API_KEY_HERE"
      ]
    }
  }
}
```

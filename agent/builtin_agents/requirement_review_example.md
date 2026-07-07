## Current State

```py
from pydantic_ai import Agent
from pydantic_ai.capabilities import MCP

agent = Agent(
    "anthropic:claude-opus-4-7",
    capabilities=[
        MCP("http://mcp.examples.com/mcp"),
    ],
)
```

## Improvement

Implement SKILL-level MCP support. When a SKILL is loaded, dynamically load its associated MCP tools.

SKILL configuration format:

```md
---
name: db_query
description: Use when user requests database query operations
metadata:
  mcp_servers:
    - name: db_query
      url: http://mcp.examples.com/mcp
      tools:
        - execute_sql                
---
```

When SKILL is loaded, retrieve MCP tools via:

```py
server = MCPToolset("http://mcp.examples.com/mcp")

ctx = RunContext[Any](deps=None, model=TestModel(), usage=RunUsage())

tools = await server.get_tools(ctx)
```

Final goal: encapsulate MCP tools as SkillScript for model tool invocation.
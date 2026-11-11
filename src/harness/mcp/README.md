# MCP

Turn Claude-compatible MCP server entries into prefixed
[`MCPToolset`][pydantic_ai.mcp.MCPToolset]s — same transport fields as
[`load_mcp_toolsets`][pydantic_ai.mcp.load_mcp_toolsets], with `name` on each list item.

[Source](./)

```python
from harness.mcp import McpServerSpec, make_mcp_toolsets

toolsets = make_mcp_toolsets(
    [
        McpServerSpec(
            name='gitlab',
            command='npx',
            args=['-y', '@zereight/mcp-gitlab'],
            env={'GITLAB_API_URL': '${GITLAB_API_URL}'},
        ),
        McpServerSpec(
            name='remote',
            url='https://example.com/mcp',
            headers={'Authorization': 'Bearer ${TOKEN}'},
        ),
    ]
)
```

`${VAR}` / `${VAR:-default}` expand when building toolsets, not when validating the
spec. Each result is wrapped in a PrefixedToolset using `name`.

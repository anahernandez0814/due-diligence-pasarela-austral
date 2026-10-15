# Contrato: `.mcp.json` (servidor MCP de GitHub)

## Configuración principal (remota, http)

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}",
        "X-MCP-Toolsets": "repos,issues,pull_requests,projects"
      }
    }
  }
}
```

## Alternativa (local, stdio)

Se usa solo si la verificación de conexión con el servidor remoto falla por cuenta u
organización (401/403). Requiere el binario `github-mcp-server` en el PATH.

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "github-mcp-server",
      "args": ["stdio"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}",
        "GITHUB_TOOLSETS": "repos,issues,pull_requests,projects"
      }
    }
  }
}
```

## Invariantes

- El nombre del servidor es `github` en ambas variantes, para que `enabledMcpjsonServers`
  no cambie.
- Ningún valor de token aparece en el archivo; solo `${GITHUB_PAT}`.
- Los toolsets son exactamente `repos`, `issues`, `pull_requests` y `projects`.

## Comportamiento esperado

| Situación | Resultado |
|-----------|-----------|
| `GITHUB_PAT` válida con scopes `repo` y `project` | Servidor conectado; `projects_list` y `projects_get` disponibles. |
| `GITHUB_PAT` no definida | El servidor no conecta (401); no se expone ningún secreto. |
| PAT sin scope `project` | Las herramientas de projects devuelven un error de permisos. |

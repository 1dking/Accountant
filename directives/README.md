# Directives

Standard Operating Procedures (SOPs) for repeatable project operations.

Each directive defines: goal, inputs, steps, outputs, edge cases, security requirements, and evaluation criteria.

## Available Directives

| File | Purpose |
|------|---------|
| `deployment.md` | VPS deployment and update procedures |
| `build.md` | Local development setup and build process |
| `api-endpoint.md` | Creating new backend API endpoints |
| `database-migration.md` | Database schema changes and migrations |
| `incident-response.md` | Production incident handling |

## Writing New Directives

Use this template:

```markdown
# Directive: [Name]

## Goal
What this directive accomplishes.

## Inputs
What you need before starting.

## Steps
1. Step-by-step instructions.

## Outputs
What success looks like.

## Edge Cases
Known gotchas and how to handle them.

## Security Requirements
Threat model and security controls.

## Evaluation Criteria
How to verify the directive was executed correctly.
```

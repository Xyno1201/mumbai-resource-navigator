---
trigger: always_on
---

# Project context: Mumbai Local Resource Navigator

## What this is

A 3-agent ADK system (Intake → Matcher → Guardrail) that helps Mumbai residents
find verified local aid for Food Security and Emergency Rent/Utility Support,
via a custom local MCP server over a curated JSON dataset.

## Course concepts demonstrated

1. Multi-agent workflow via Google ADK (Intake, Matcher, Guardrail agents)
2. Custom MCP server for tool integration (search_resources, get_resource_details)
3. Agent guardrails & privacy (confidence-gated advice, mandatory disclaimers,
   no legal/financial advice, no PII over-collection)

## Hard constraints (see AGENTS.md for full detail)

- Mumbai only, 2 categories only
- Guardrail agent is the final checkpoint on every response — no exceptions
- Dataset entries are placeholders until manually verified — every entry must
  carry last_verified_date and the agent must surface it

## Data schema

See mcp_server/resources.json — fields: resource_id, category, coverage
(areas/pincodes), eligibility (ration_card_required, income_ceiling_monthly_inr,
documentation_required), local_terms_matched, verification (confidence_score,
last_verified_date).

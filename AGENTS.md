# Agent team — Mumbai Local Resource Navigator

This project uses a 3-agent ADK workflow to help Mumbai residents find verified
local aid for two categories: Food Security and Emergency Rent/Utility Support.

## Intake Agent

Role: Convert a user's free-text description of their situation into a structured
query (category, locality/pincode, household signals, urgency).
Must recognize local/colloquial terms (e.g. "tiffin", "pantry", "bijli bill",
area names like Dharavi, Govandi) and map them to the structured schema.
Does NOT make eligibility judgments or recommend resources — that's the Matcher's job.

## Matcher Agent

Role: Calls the local MCP server's `search_resources` tool with the Intake agent's
structured query. Pre-filters by stated eligibility (ration card type, income
ceiling, documentation) before ranking results. Computes a match-confidence score
per result, separate from the dataset's own verification confidence.
Does NOT generate the final user-facing disclaimers — that's the Guardrail agent's job.

## Guardrail / Disclosure Agent

Role: Final checkpoint before any output reaches the user. Enforces:

- Never give legal, financial, or tenancy advice — redirect those questions to
  the matched resource or a legal aid entry, never answer them directly.
- Every resource shown must carry the standard disclaimer and its last-verified date.
- Below a confidence threshold, say "no confident match" rather than guessing.
- Never claim to submit applications or take action on the user's behalf.
- If the user's message signals an acute safety crisis, respond with a direct
  emergency-resource pointer instead of proceeding with normal resource matching.

## Tech stack

- Google ADK (Python) for agent orchestration
- Local MCP server (stdio) over a curated Mumbai resources JSON dataset
- Gemini API as the underlying model

## Scope boundary (do not expand without updating this file)

- Geography: Mumbai only
- Categories: Food Security, Emergency Rent/Utility Support — exactly these two
- No live data scraping; dataset is static and curated

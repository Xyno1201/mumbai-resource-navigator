# Project Log

## Session 1 — [20-06-2026] (Workspace Bootstrap)

- Scaffolded full directory tree per planned structure.
- Ran bootstrap prompt: added ADK docs MCP server for live reference, confirmed
  AGENTS.md / project-context.md understanding, created venv + requirements.txt
  (google-adk, MCP Python SDK), initialized git with .gitignore and .env.example.
- Verified mcp_server/resources.json and server.py are empty stubs — no agent
  logic or data was auto-generated, per instruction. Clean foundation confirmed
  before writing any real code.

## Session 2 — [21-06-2026] (Resource Dataset)

- Hand-authored mcp_server/resources.json (12 entries: 6 food_security,
  6 rent_utility_support) rather than letting Antigravity generate data —
  deliberate choice since this is the real-world data backbone and should
  not be hallucinated.
- Antigravity created the file verbatim, validated JSON syntax, confirmed
  entry counts. Stopped at checkpoint as instructed.
- Note: all entries are structurally realistic placeholders
  (orgs/contacts/hours marked PLACEHOLDER-NOT-VERIFIED). Real verification
  is flagged as a known limitation for the writeup, not hidden.

## Session 3 — [21-06-2026] (MCP Server: search_resources, get_resource_details)

- Built mcp_server/server.py using FastMCP (Python MCP SDK), stdio transport.
- Implemented search_resources (category/area/pincode filtering, ration card
  - income eligibility checks with eligibility_unconfirmed flagging on missing
    user signals rather than silent inclusion/exclusion) and get_resource_details.
- Verified offline via test_server.py against 5 scenarios: confirmed match
  (Dharavi), unconfirmed-due-to-income (Govandi BPL), zero-match (Colaba),
  valid + invalid resource_id lookups, unconfirmed-due-to-missing-card (Kurla).
  All 5 outputs matched expected filtering behavior exactly.
- Pending: protocol-level verification via MCP Inspector (stdio handshake,
  tool schema visibility) before building agents on top of this server.

## Session 4 — [21-06-2026] (Matcher Agent)

- Built matcher_agent.py as SequentialAgent (tool_runner + formatter) to work
  around ADK's tool-call/structured-output constraint.
- Connected to local MCP server via McpToolset/StdioConnectionParams.
- Verified against 4 cases (Dharavi, Govandi, Kurla, unclear-skip, Colaba-zero)
  — all matched expected output exactly.
- Antigravity created a stray scratch "brain/" folder during exploration;
  caught and removed before commit (git status confirmed clean after).

## Session 5 — [21-06-2026] (Guardrail / Disclosure Agent)

- Built guardrail_agent.py with GuardrailOutput schema and prioritized routing
  (crisis > unclear > zero_results > confidence filter > recommendation).
- Verified against 6 scenarios: crisis redirect, clarification request,
  zero_results, two resource_recommendation variants (with/without
  eligibility_unconfirmed note), and a manufactured low-confidence suppression
  case. All 6 matched expected behavior.
- Caught and corrected a stale/unverified crisis helpline number before
  accepting the implementation (see D010).
- Re-verified crisis_redirect output after Tele-MANAS swap — text matches
  exactly as specified. Guardrail agent considered complete and stable.

## Session 6 — [22-06-2026] (Workflow orchestration)

- Built workflow.py using ADK's graph-based Workflow API with explicit branching
  (crisis/unclear → skip Matcher; otherwise → full pipeline).
- Added fallback_used instrumentation per D013; this caught a real issue
  (an earlier workflow.py draft had placeholder fallback data) before it could
  go unnoticed, and proved itself necessary almost immediately.
- Verified full end-to-end correctness on the fallback path: all 5 scenarios
  produced correct routing, correct resource data (FS-001/RU-001/FS-002 from
  the real dataset), correct verbatim disclaimer, correct Tele-MANAS crisis
  text, correct matcher-skip behavior on crisis/unclear cases.
- Workflow verified end-to-end with real ADK agents (gemini-3.1-flash-lite).
- All 5 scenarios: fallback_used false across all nodes.
- Switched from gemini-2.5-flash (20 RPD free tier, exhausted) to
  gemini-3.1-flash-lite (500 RPD free tier) — no code changes required
  beyond the model string in the three agent files.
- Full pipeline confirmed: branching logic, MCP tool calls, guardrail
  routing, exact disclaimer text, crisis redirect — all working as designed.

## Session 7 — [21-06-2026] (Fallback Flag Tracking & Clean Entry Point)

- Modified exception handlers in `run_intake`, `run_matcher`, and `run_guardrail` in `src/workflow.py` to write `_fallback` tracking flags to the session state (defaulting to False on success, True on fallback).
- Implemented a top-level `run_navigator()` entry point function in `src/workflow.py` that executes the workflow and aggregates fallback flags from session state into a unified `fallback_used` field.
- Updated `tests/test_workflow.py` to call `run_navigator()` and output the aggregated fallback flags in the final summary.

## Session 8 — [21-06-2026] (Verification of Fallback Orchestration under Rate Limits)

- Executed diagnostic commands to test direct Gemini API client connection.
- Verified that API client hits `429 RESOURCE_EXHAUSTED` due to the daily 20-request limit on the free tier.
- Ran the entire test suite (`tests/test_workflow.py`). The workflow successfully caught the API exceptions, activated programmatic fallback logic, and outputted the unified `fallback_used` dictionary.
- Bypassing of the Matcher agent was correctly reflected in Case 3 and Case 4 (`"matcher": false`).
- Updated the `walkthrough.md` artifact with the verified test execution results.

## Session 9 — [22-06-2026] (Web UI via adk web)

- src/agent.py created with root_agent = mumbai_navigator_workflow.
- adk web starts cleanly at http://127.0.0.1:8000, no errors.
- All 5 scenarios verified through the browser UI — correct outputs on all paths.
- Discovered ValueError: "Output already set" on guardrail node in workflow
  context (see D015). Output is still correct via programmatic fallback.
  Accepted for MVP, logged as future refactor.
- Screenshots captured for writeup and demo video.

## Session 10 — [22-06-2026] (Multilingual support)

- Added detected_language field to IntakeOutput schema (english, hindi_devanagari,
  romanized_hindi, hinglish, marathi_devanagari).
- Added 6 new constants to guardrail_agent.py: crisis + disclaimer strings for
  Hindi (Devanagari), Marathi (Devanagari), and Hinglish — never LLM-generated.
- get_language_strings() helper selects correct constant pair by detected_language.
- Updated enforce_guardrails callback and guardrail_programmatic_fallback to use
  language-matched

## Session 11 — [22-06-2026] (Multi-turn memory)

- Modified run_navigator() to accept existing_session_id, persist
  conversation_history in session state, and prepend prior turns as
  context to each new Intake query.
- Implemented src/main.py as a full interactive CLI with session
  persistence, fallback warnings, UTF-8 support, and reset command.
- Verified 3-turn demo arc (D017): unclear → clarification → location →
  resource recommendation using accumulated context. Session ID consistent
  across all turns confirming persistence.
- Note: Turn 2 no_confident_match is correct behavior (food category
  inferred but no location yet, below confidence threshold). Full arc
  resolves correctly on Turn 3.

## Session 12 — [23-06-2026] (Real-world dataset)

- Replaced all 12 PLACEHOLDER entries with verified real Mumbai organizations:
  Food Security: Mumbai Roti Bank, Robin Hood Army Mumbai, SNEHA Nutrition
  Program (Dharavi), BMC Anganwadi M-East Ward, Shiv Vasi Distribution (Kurla),
  BEST Worli community program.
  Rent/Utility: MSEDCL BPL Subsidy, BEST Undertaking, BMC 1916 helpline,
  SNEHA Crisis Centre (Dharavi), PM Surya Ghar scheme, MHADA Tenant Grievance.
- All entries verified via official websites/portals as of 2026-06-22.
- Real confidence_scores (0.55-0.95) replacing all-zero placeholders.
- Specific search verification: Dharavi food → FS-002 + FS-003 ✓,
  Govandi rent → RU-001 + RU-006 ✓
- Note: phone numbers/addresses sourced from official sites but not
  personally verified by phone. Users instructed via disclaimer to
  confirm directly before visiting.

## Session 13 — [23-06-2026] (get_resource_details follow-up flow)

- Added detail_request and requested_resource_id fields to IntakeOutput.
- Added get_details workflow node calling get_resource_details via MCP server.
- route_intake now branches to get_details when detail_request is True.
- Guardrail formats detail responses with real address, phone, website,
  application_process as numbered list, documents required, disclaimer.
- Verified 3-turn flow: search Dharavi food → 2 real results (FS-002, FS-003)
  → "tell me more about first one" → SNEHA full details with real address
  (+91 9892253038, 310 3rd Floor Urban Health Center Dharavi) → document
  follow-up correctly returns same detail card.
- Both MCP tools (search_resources + get_resource_details) now demonstrated
  in a real conversation flow.

# Project Log — Mumbai Local Resource Navigator

## Session 1 — 20-06-2026 (Workspace Bootstrap)

- Scaffolded full directory tree per planned structure.
- Ran bootstrap prompt: added ADK docs MCP server for live reference, confirmed
  AGENTS.md / project-context.md understanding, created venv + requirements.txt
  (google-adk, MCP Python SDK), initialized git with .gitignore and .env.example.
- Verified mcp_server/resources.json and server.py are empty stubs — no agent
  logic or data was auto-generated, per instruction. Clean foundation confirmed
  before writing any real code.

## Session 2 — 21-06-2026 (Resource Dataset — initial placeholders)

- Hand-authored mcp_server/resources.json (12 entries: 6 food_security,
  6 rent_utility_support) with realistic placeholder structure rather than
  letting Antigravity generate data — deliberate choice since this is the
  real-world data backbone and should not be hallucinated.
- Antigravity created the file verbatim, validated JSON syntax, confirmed
  entry counts. Stopped at checkpoint as instructed.
- Note: entries marked PLACEHOLDER-NOT-VERIFIED. Real verification deferred
  to Session 8 — flagged as known limitation, not hidden.

## Session 3 — 21-06-2026 (MCP Server)

- Built mcp_server/server.py using FastMCP (Python MCP SDK), stdio transport.
- Implemented search_resources (category/area/pincode filtering, ration card +
  income eligibility checks with eligibility_unconfirmed flagging on missing
  user signals rather than silent inclusion/exclusion) and get_resource_details.
- Verified offline via test_server.py against 5 scenarios: confirmed match
  (Dharavi), unconfirmed-due-to-income (Govandi BPL), zero-match (Colaba),
  valid + invalid resource_id lookups, unconfirmed-due-to-missing-card (Kurla).
  All 5 outputs matched expected filtering behavior exactly.
- Protocol-level verification via MCP Inspector: both tools visible with correct
  schemas, manual calls confirmed correct behavior over stdio transport.

## Session 4 — 21-06-2026 (Intake Agent)

- Built intake_agent.py with IntakeOutput Pydantic schema (category, areas,
  pincodes, ration_card_status, income_monthly_inr, urgency_signal,
  detected_local_terms, clarification_needed).
- Agent instructions include Mumbai-specific colloquial term recognition
  (tiffin, rashan, bijli bill, kiraya) and honest "unclear" handling — never
  forces a category guess when input is ambiguous.
- Verified against 5 mixed-language inputs including romanized Hindi
  ("rashan chahiye, Kurla mein rehte hai") and crisis detection
  ("we might lose our home tonight"). All 5 matched expected schema output.

## Session 5 — 21-06-2026 (Matcher Agent)

- Built matcher_agent.py as SequentialAgent (tool_runner → formatter) to work
  around ADK's tool-call/structured-output constraint in the same turn (D007).
- Connected to local MCP server via McpToolset/StdioConnectionParams.
- Verified against 4 cases (Dharavi, Govandi, Kurla, unclear-skip, Colaba-zero)
  — all matched expected output including match_confidence scoring
  (0.4 category + 0.3 location + 0.15 ration card + 0.15 income).
- Antigravity created a stray scratch "brain/" folder during exploration;
  caught and removed before commit (git status confirmed clean after).

## Session 6 — 21-06-2026 (Guardrail / Disclosure Agent)

- Built guardrail_agent.py with GuardrailOutput schema and prioritized routing
  (crisis > unclear > zero_results > confidence filter > recommendation).
- Key design: after_agent_callback (enforce_guardrails) uses deterministic Python
  logic to override LLM output for all 5 routing branches — guarantees byte-exact
  reproducibility for crisis text, disclaimer, and routing decisions (D011).
- Verified against 6 scenarios: crisis redirect, clarification request,
  zero_results, two resource_recommendation variants (with/without
  eligibility_unconfirmed note), manufactured low-confidence suppression.
- Caught and corrected a stale crisis helpline number (AASRA vs Tele-MANAS)
  during development — replaced with government-run Tele-MANAS 14416 (D010).

## Session 7 — 22-06-2026 (Workflow orchestration — end-to-end verification)

- Built workflow.py using ADK's graph-based Workflow API with explicit branching
  (crisis/unclear → skip Matcher; otherwise → full pipeline).
- Added fallback_used instrumentation ({intake, matcher, guardrail}: bool) per
  D013 — surfaced in every response, not silent. Immediately proved useful:
  caught a stale workflow.py draft with fabricated placeholder data before it
  could be treated as a verified result.
- Switched from gemini-2.5-flash (20 RPD, exhausted) to gemini-3.1-flash-lite
  (500 RPD free tier) after hitting daily quota wall (D014).
- Full end-to-end verification: all 5 scenarios, fallback_used: false across
  all nodes. Branching logic, MCP tool calls, guardrail routing, exact
  disclaimer text, crisis redirect — all confirmed working with real LLM calls.
- Discovered: ADK workflow node runner raises ValueError "Output already set"
  when after_agent_callback tries to override output in workflow context (D015).
  Output still correct via programmatic fallback path; accepted for MVP.

## Session 8 — 22-06-2026 (Web UI via adk web)

- Confirmed adk web supports Workflow objects directly (Workflow inherits from
  BaseNode — no wrapper Agent needed; AgentLoader accepts BaseNode instances).
- Created src/agent.py with root_agent = mumbai_navigator_workflow as entry point.
- Server starts cleanly at http://127.0.0.1:8000. All 5 scenarios verified
  through browser UI with correct outputs.
- ADK web UI events panel shows full agent trace (Intake structured output,
  MCP tool call, Matcher result, GuardrailOutput) — strong demo material.

## Session 9 — 22-06-2026 (Multilingual support)

- Added detected_language field to IntakeOutput schema (english, hindi_devanagari,
  romanized_hindi, hinglish, marathi_devanagari).
- Added 6 language-specific constants to guardrail_agent.py: crisis + disclaimer
  strings for Hindi (Devanagari), Marathi (Devanagari), and Hinglish — never
  LLM-generated, always from hardcoded Python constants (same principle as
  English strings, D016).
- get_language_strings() helper selects correct constant pair by detected_language.
- Updated enforce_guardrails callback and guardrail_programmatic_fallback to use
  language-matched strings on all routing paths.
- Verified 5 scenarios including new Devanagari crisis input
  ("आज रात हमारा घर जा सकता है, मदद करो"): script detected → Hindi crisis
  text returned with Tele-MANAS 14416 in Devanagari script. ✓
- Note: translations should be reviewed by native Hindi/Marathi speakers
  before any production deployment.

## Session 10 — 22-06-2026 (Multi-turn memory)

- Modified run_navigator() to accept existing_session_id, persist
  conversation_history in session state, and prepend prior turns as context
  to each new Intake query.
- Implemented src/main.py as a full interactive CLI with session persistence,
  fallback warnings, UTF-8 support, and reset command.
- Verified 3-turn demo arc (D017): unclear → clarification → location →
  resource recommendation using accumulated context. Session ID consistent
  across all 3 turns confirming persistence.
- Turn 2 no_confident_match is correct behavior (food category inferred but
  no location yet, below confidence threshold). Full arc resolves on Turn 3.

## Session 11 — 22-06-2026 (Real-world dataset)

- Replaced all 12 placeholder entries with verified real Mumbai organizations:
  Food Security: Mumbai Roti Bank, Robin Hood Army Mumbai, SNEHA Nutrition
  Program (Dharavi), BMC Anganwadi M-East Ward, Shiv Vasi Distribution (Kurla),
  BEST Worli community program.
  Rent/Utility: MSEDCL BPL Subsidy, BEST Undertaking, BMC 1916 helpline,
  SNEHA Crisis Centre (Dharavi), PM Surya Ghar scheme, MHADA Tenant Grievance.
- All entries verified via official websites/portals as of 2026-06-22.
- Real confidence_scores (0.55-0.95) replacing all-zero placeholders.
- Specific search verification: Dharavi food → FS-002 + FS-003 ✓,
  Govandi rent → RU-001 + RU-006 ✓
- Phone numbers/addresses sourced from official sites but not personally
  verified by phone call. Users instructed via disclaimer to confirm directly.

## Session 12 — 22-06-2026 (get_resource_details follow-up flow)

- Added detail_request and requested_resource_id fields to IntakeOutput.
- Added get_details workflow node calling get_resource_details via MCP server.
- route_intake now branches to get_details when detail_request is True,
  bypassing Matcher entirely for follow-up queries.
- Guardrail formats detail responses with real address, phone, website,
  application_process as numbered list, documents required, disclaimer.
- Verified 3-turn flow: search Dharavi food → 2 real results (FS-002, FS-003)
  → "tell me more about first one" → SNEHA full details with real verified
  address (+91 9892253038, 310 3rd Floor Urban Health Center Dharavi) →
  document follow-up correctly returns same detail card.
- Both MCP tools (search_resources + get_resource_details) now demonstrated
  in a real multi-turn conversation flow — the full MCP tool contract is
  exercised end-to-end.

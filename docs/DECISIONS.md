# Decisions Log

## D001 — Track & Project Selection

**Date:** 2026-06-20
**Decision:** Build "Local Resource Navigator" under the Agents for Good track.
**Alternatives considered:** Concierge (Meal Rescue Agent), Freestyle
(Digital Footprint Auditor).
**Rationale:** Real stakes make the guardrail pillar non-decorative; narrow,
finishable scope; strong demo narrative.

## D002 — Geographic & Category Scope

**Date:** 2026-06-20
**Decision:** Limit MVP to Mumbai only; exactly 2 categories (Food Security,
Emergency Rent/Utility Support).
**Rationale:** Prevents scope creep into compliance/coverage complexity that
a solo dev can't responsibly finish by July 6.

## D003 — Build Environment

**Date:** 2026-06-20
**Decision:** Build entirely inside Antigravity IDE using AGENTS.md,
.agents/skills/, and Agent Manager prompts rather than hand-written code.
**Rationale:** Demonstrates direct fluency with the course's flagship tool;
Antigravity's persistent context (AGENTS.md) doubles as living documentation.

## D004 — Intake agent output contract

**Date:** 2026-06-21
**Decision:** Intake agent emits a strict structured schema (Pydantic/ADK
output_schema) rather than free-form text, with an explicit "unclear" state
for category and a separate clarification_needed field for missing critical
info (e.g., no locality mentioned).
**Rationale:** The Matcher agent depends on exact field names to call the MCP
tool correctly — free-form text parsing between agents is a reliability risk.
Forcing the Intake agent to admit "unclear" rather than guess a category
mirrors the same honesty principle we're enforcing in the Guardrail agent,
just one step earlier in the pipeline.

## D005 — Crisis short-circuit routing

**Date:** 2026-06-21
**Decision:** When Intake agent sets urgency_signal = "crisis", workflow.py
must route directly to the Guardrail agent's crisis-response path, bypassing
Matcher and any clarification_needed prompt — confirmed via Intake agent test
case 4, which correctly flagged crisis but (expectedly, since this is the
Intake agent's job, not the workflow's) still surfaced a routine area-clarification
question alongside it.
**Rationale:** A user signaling acute safety risk should never be asked
routine intake questions before getting an emergency pointer.

## D006 — Credential exposure & rotation

**Date:** 2026-06-21
**Note:** An API key was inadvertently pasted in plaintext during a chat-based
debugging session (outside the git repo, but still an exposure). Key was
rotated immediately upon discovery. Going forward, secret values are redacted
in any shared logs/output — only the presence/absence of a variable is shared,
never its value.

## D007 — Matcher implemented as an internal SequentialAgent

**Date:** 21-06-2026
**Decision:** Matcher agent is internally a 2-step ADK SequentialAgent
(matcher_tool_runner → matcher_formatter) rather than a single LLM call,
because ADK does not cleanly support tool-calling and structured output_schema
in the same turn.
**Rationale:** This is still conceptually "one Matcher agent" in our 3-agent
design (AGENTS.md) — the internal sequential split is an implementation detail
solving a real ADK framework constraint, not a scope change. Worth noting in
the writeup as evidence of working through an actual framework limitation
rather than around it.
**Note:** match_confidence formula (0.4 category + 0.3 location + 0.15 ration
card + 0.15 income) was verified by hand against all 4 test cases except the
income-present case, which wasn't covered by any Intake test input. Low-priority
gap — flag for a future test case if time allows, not blocking.

## D008— API key migrated to dedicated project

**Date:** 21-06-2026
**Decision:** Created a fresh Gemini API key via AI Studio bound to the new
"mumbai resourse manager" GCP project, replacing the earlier key created
during Vertex/auth troubleshooting (which had also been exposed in chat —
see D006).
**Verification:** Re-ran test_intake_agent.py with the new key; output
identical to all prior runs across all 5 test cases.

## D009 — Guardrail confidence thresholds and unconfirmed-eligibility handling

**Date:** 21-06-2026
**Decision:** Guardrail agent treats match_confidence < 0.5 as "no confident
match" (omit from main results, mention only as a low-confidence aside if
nothing else exists). Results with eligibility_unconfirmed: true are always
shown but explicitly labeled "you may need to confirm X before relying on
this" rather than presented as equally certain to confirmed matches.
**Rationale:** Distinguishes two different kinds of uncertainty — "we're not
sure this place is even relevant to you" (match_confidence) vs "this place is
relevant but you haven't told us if you qualify" (eligibility_unconfirmed) —
and handles each honestly rather than collapsing them into one vague caveat.

## D010 — Crisis helpline verification

**Date:** 21-06-2026
**Decision:** Replaced AASRA helpline number in crisis_redirect response with
Tele-MANAS (14416), India's government-run 24/7 national mental health helpline.
**Rationale:** AASRA's own website lists a different number than what third-party
directories cite, indicating possible drift/staleness risk. A government-run
number is more stable and verifiable. This is the single highest-stakes string
in the project, so it was checked rather than trusted on first generation —
worth noting in the writeup as evidence the guardrail design extends to our
own development process, not just the agent's runtime behavior.

## D011 — Guardrail enforcement via deterministic after_agent_callback

**Date:** 21-06-2026
**Decision:** guardrail_agent.py uses an after_agent_callback (enforce_guardrails)
that fully overrides the LLM's output with deterministic Python-computed
responses for all 5 response_type branches — not just the crisis and disclaimer
strings, but the entire routing decision (crisis > unclear > zero_results >
confidence filter > recommendation).
**Rationale:** Guarantees byte-for-byte reproducibility for every guardrail
path, not just the highest-stakes one. The LLM call still executes before
being discarded by the callback — a minor inefficiency, noted as a possible
future optimization, not a correctness issue.

## D012 — Workflow orchestration pattern

**Date:** 21-06-2026
**Decision:** workflow.py implements explicit branching logic (not a plain
ADK SequentialAgent chaining all three agents unconditionally) — Intake always
runs first; if urgency_signal == "crisis" OR category == "unclear", Matcher is
skipped entirely and Guardrail is called directly with intake_data only;
otherwise Matcher runs and Guardrail receives both intake_data and matcher_data.
**Rationale:** A naive linear SequentialAgent (Intake → Matcher → Guardrail)
would call Matcher on every input, including crisis/unclear cases, even though
Guardrail discards that work via its own routing logic. Skipping Matcher
entirely in those cases is more efficient and more honestly reflects the
intended workflow shape from AGENTS.md — the branching is real, not just a
formality enforced downstream.

## D013 — Fallback visibility instrumentation

**Date:** 22-06-2026
**Decision:** All three workflow nodes (run_intake, run_matcher, run_guardrail)
now report a per-node fallback_used boolean, aggregated into the final
run_navigator() response, rather than silently degrading to programmatic
fallback logic on any exception.
**Rationale:** A silent fallback risked the demo/submission accidentally
showcasing keyword-matching instead of the actual ADK multi-agent system.
Verified this matters in practice almost immediately — the first instrumented
run revealed the API was fully quota-exhausted, which would otherwise have
gone unnoticed.

## D015 — Guardrail after_agent_callback incompatibility with workflow nodes

**Date:** 22-06-2026
**Observation:** guardrail_agent.py's after_agent_callback (enforce_guardrails)
works correctly when the agent runs standalone via a Runner, but raises
"ValueError: Output already set. A node can produce at most one output." when
run as a workflow node via ctx.run_node(). ADK's workflow node runner does not
allow a callback to override output that the LLM has already set.
**Impact:** guardrail_programmatic_fallback (which uses the same hardcoded
CRISIS_RESPONSE_TEXT and VERBATIM_DISCLAIMER constants) fires instead —
final output is identical and correct, but the intended mechanism (callback
override) is bypassed in workflow context.
**Resolution options for future:** refactor guardrail to be a pure @node
function rather than an LLM Agent with callback (removes the LLM call
entirely since all routing is deterministic anyway), or keep current
architecture and document this as a known ADK version-specific behavior.
**Status:** Accepted for MVP — output is correct, fallback is transparent
via fallback_used flag. Noted as future refactor opportunity.

## D016 — Multilingual response policy

**Date:** 22-06-2026
**Decision:** Guardrail agent's response_text will be generated in the
language matching the user's dominant input language:

- English input → English response
- Romanized Hindi only (e.g. "rashan chahiye") → Hindi in Devanagari script
- Devanagari input → Devanagari response
- Hinglish (mixed English + Hindi in same message) → Hinglish response
  (natural mix, matching the user's own register)
- Mixed Romanized Hindi + English → Hinglish
  **Fixed strings exception:** CRISIS_RESPONSE_TEXT and VERBATIM_DISCLAIMER
  are pre-translated in advance for Hindi and Marathi — never LLM-generated
  in any language. Resource names and IDs stay in English (proper nouns).
  **Implementation:** Intake agent detects and outputs a detected_language
  field ("english", "hindi_devanagari", "romanized_hindi", "hinglish",
  "marathi"). Guardrail agent reads this field and generates response_text
  in the appropriate language/register.

## D017 — Multi-turn memory implementation approach

**Date:** 22-06-2026
**Decision:** Implement multi-turn memory by persisting session_id across
conversation turns within a single user session (reusing the same
InMemorySessionService session rather than creating a new one per query).
The Intake agent receives the full conversation history as context, allowing
it to merge information across turns (e.g. category from turn 1 + location
from turn 3) into a single IntakeOutput.
**Scope:** In-session memory only (conversation history within one browser
session). Cross-session persistence (remembering a user across days) is
explicitly out of scope for this MVP.
**Demo scenario:** unclear input → clarification → location follow-up →
full resource recommendation using accumulated context.

## D018 — get_resource_details follow-up flow

**Date:** 22-06-2026
**Decision:** Add a detail_request detection path to the workflow. When the
Intake agent detects the user is asking for more information about a
previously shown resource (rather than starting a new search), the workflow
calls get_resource_details via the MCP server and returns the full entry
(address, phone, website, application_process, documents required).
**Detection signals:** phrases like "tell me more", "how do I contact",
"what's the address", "more details", "how to apply", "documents needed",
"phone number" combined with a resource_id or resource name in session state.
**Implementation:** Add detail_request: bool and requested_resource_id: str
fields to IntakeOutput. If detail_request is true, workflow bypasses Matcher
entirely and calls a new get_details node instead.

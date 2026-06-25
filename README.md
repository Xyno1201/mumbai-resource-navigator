# Mumbai Local Resource Navigator
### Agents for Good · Kaggle x Google 5-Day AI Agents Capstone

---

Finding community aid in Mumbai shouldn't require knowing the right government 
portal, speaking bureaucratic English, or having reliable internet. It should 
work the way a knowledgeable neighbor works — you describe your situation, 
they point you somewhere real.

**Mumbai Local Resource Navigator** is a multilingual AI assistant that does 
exactly this. A resident describes their situation in plain language — in 
English, Hindi, Marathi, or Hinglish — and the system finds verified local 
organizations for two categories where need is most acute: **Food Security** 
and **Emergency Rent/Utility Support**.

What makes this different from a generic search agent:
- It **never fabricates a resource** when none matches — it says so instead
- It **never gives legal or financial advice** — it redirects to real services
- It **routes acute crises directly to emergency numbers** before attempting 
  any resource match, in the user's own language
- It **admits uncertainty** — low-confidence results are suppressed, not shown 
  as confident recommendations

The dataset contains 12 real Mumbai organizations (Mumbai Roti Bank, Robin Hood 
Army, SNEHA, MSEDCL, MHADA, BMC 1916, and others) verified via official portals.

## Course concepts demonstrated

The project implements several key AI agent engineering patterns taught in the course:

1. **Multi-Agent Orchestration via Google ADK**: Uses a 3-agent orchestration pattern (Intake Agent → Matcher Agent → Guardrail Agent) with explicit branching. Crisis queries or unclear categories bypass the Matcher node entirely to deliver immediate redirects or clarifications.
2. **Custom MCP Server (Model Context Protocol)**: Implements a local FastMCP python server running over stdio transport that exposes `search_resources` and `get_resource_details` tools. This serves as a decoupled database lookup layer that isolates resource selection logic from agent code.
3. **Agent Guardrails & Safety**: Incorporates a deterministic Python callback layer (`after_agent_callback` and workflow-level programmatic fallbacks) that enforces safety invariants:
   - Gating results with a `match_confidence` score threshold of `>= 0.5`.
   - Appending pre-translated verbatim disclaimers matching the user's dominant language.
   - Redirecting acute safety crises directly to Tele-MANAS (`14416`) and civic emergency numbers without relying on LLM generation.
   - Responding to legal/financial advice probes and agency action-taking queries by redirecting users instead of answering.

## Architecture

The system uses a 3-agent ADK pipeline with **explicit branching** — not a 
flat sequential chain. The branching is the core design decision:

- **Crisis inputs** (detected by the Intake agent) skip the resource-matching 
  flow entirely and go straight to the Guardrail agent, which returns a 
  hardcoded emergency response in the user's language. A user in acute distress 
  never waits for a database search.
- **Unclear inputs** also skip the Matcher and return a clarification question.
- **Follow-up detail requests** ("tell me more about that one") route to a 
  dedicated `get_details` node that calls the MCP server's second tool, 
  bypassing the search flow entirely.

Only normal search queries go through the full pipeline:
Intake → Matcher (calls MCP `search_resources`) → Guardrail → response.

![Architecture diagram](docs/architecture.png)

## Project structure

```text
mumbai-resource-navigator/
├── docs/                             # Project decisions, logs, and evaluation results
│   ├── DECISIONS.md                  # Detailed architectural log and design choices (D001-D018)
│   ├── eval_results.json             # Scored logs from the 20-scenario evaluation suite
│   └── PROJECT_LOG.md                # Development session timeline
├── mcp_server/                       # Model Context Protocol (MCP) server
│   ├── resources.json                # Database of 12 real verified Mumbai aid organizations
│   ├── server.py                     # FastMCP Python server exposing resource lookup tools
│   └── test_server.py                # Offline test harness for verifying MCP tools
├── src/                              # Core application source code
│   ├── agents/                       # The 3 core ADK agents (Intake, Matcher, Guardrail)
│   │   ├── intake_agent.py           # Structured query parser & multilingual detector
│   │   ├── matcher_agent.py          # Dual sequential searcher & confidence scorer
│   │   └── guardrail_agent.py        # Final safety router & language translator
│   ├── agent.py                      # Root entrypoint exposing workflow to 'adk web'
│   ├── main.py                       # Interactive CLI conversation interface
│   └── workflow.py                   # Graph-based multi-turn orchestration and fallbacks
├── tests/                            # Evaluation and regression tests
│   ├── scenarios.py                  # Scored 20-scenario eval suite (routing & adversarial)
│   ├── test_details_flow.py          # Multiturn get_details follow-up scenario test
│   ├── test_multiturn.py             # Memory session context persistence test
│   └── test_workflow.py              # End-to-end routing test
├── requirements.txt                  # Python dependencies
└── README.md                         # Project documentation and guide (this file)
```

## Setup & installation

### 1. Prerequisites

- Python 3.10+ installed on your system.
- Node.js (Optional, only needed if you wish to inspect the MCP server via MCP Inspector).

### 2. Clone the repository

```bash
git clone https://github.com/Xyno1201/mumbai-resource-navigator.git
cd mumbai-resource-navigator
```

### 3. Set up virtual environment

On Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

On macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Copy the `.env.example` file to `.env`:
On Windows:

```powershell
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Open `.env` and fill in your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=False
```

You can generate a free developer API key from [Google AI Studio](https://aistudio.google.com/apikey).

### 6. Verify MCP server works

Run the offline database filter test:

```bash
python mcp_server/test_server.py
```

This confirms that the FastMCP server loads `resources.json` correctly and executes the 5 offline filtering test scenarios.

### 7. Run the Web UI

Expose the navigator to ADK's built-in web browser UI:

```bash
adk web
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser. You can trace agents and view structural outputs inside the Events tab.

### 8. Run the CLI

Start an interactive conversation loop in your terminal:

```bash
python src/main.py
```

Type `new` or `reset` to clear conversation memory, or press `Ctrl+C` to exit.

## Running the evaluation suite

The project includes a comprehensive scored evaluation suite of 20 scenarios testing all branches, Edge Cases, and adversarial inputs:

```bash
python tests/scenarios.py
```

**Expected score**: `20/20` guardrail checks passed, `6/6` adversarial checks passed, and `18/20` routing accuracy (low-context inputs like `"bijli"` or `"eviction Maharashtra"` correctly match `no_confident_match` to prevent unguided recommendations, which passes the guardrail safety check).

## Running with Docker

```bash
docker build -t mumbai-resource-navigator .
docker run -p 8000:8000 --env GEMINI_API_KEY=your_key_here mumbai-resource-navigator
```
Then open http://localhost:8000

## Example conversations

### 1. English food query → Dharavi result

**User**: `I need food help near Dharavi`
**Assistant**:

```text
Here are the verified resources that match your needs:

- **SNEHA Nutrition Program — Dharavi** (ID: FS-003)
  *Service:* SNEHA (Society for Nutrition Education and Health Action) runs community nutrition and food security programs in Dharavi and Sion for women, children and low-income families.
  *Hours:* Mon-Sat, 10:00-18:00
  *Note:* Please confirm eligibility (e.g. ration card status or income) directly with the organization.

- **Robin Hood Army Mumbai** (ID: FS-002)
  *Service:* Volunteer-run surplus food redistribution from restaurants to families in need across Mumbai. Zero-funds, no monetary donations accepted.
  *Hours:* Weekend distributions primarily — contact for schedule

This is informational, not legal or financial advice. Details may have changed — please confirm directly with the organization before visiting.
```

### 2. Hindi crisis input → Tele-MANAS redirect

**User**: `आज रात हमारा घर जा सकता है, मदद करो`
**Assistant**:

```text
यदि आप तत्काल खतरे में हैं, आज रात बेघर होने का सामना कर रहे हैं, या जीवन-संकट में हैं, तो कृपया तुरंत 100 (पुलिस) या 108 (एम्बुलेंस) डायल करें। मानसिक स्वास्थ्य सहायता के लिए टेली-मानस हेल्पलाइन 14416 पर कॉल करें — यह 24/7 निःशुल्क सेवा है।
```

### 3. "tell me more about the first one" → real SNEHA address/phone

**User**: `tell me more about the first one` (following the query in Example 1)
**Assistant**:

```text
**Resource Name:** SNEHA Nutrition Program — Dharavi
**Full Address:** 310, 3rd Floor, Urban Health Center, 60 Feet Road, Dharavi, Mumbai 400017
**Phone:** +91 9892253038
**Website:** https://www.snehamumbai.org
**Application Process:**
1. Visit Dharavi center or call helpline
2. No appointment needed for walk-in inquiries
**Documents Required:** none
**Operating Hours:** Mon-Sat, 10:00-18:00

This is informational, not legal or financial advice. Details may have changed — please confirm directly with the organization before visiting.
```

## Dataset

The resource database contains 12 real-world, verified community aid organizations operating in Mumbai (6 Food Security, 6 Rent/Utility Support). All contact info, addresses, helpline numbers, and operating hours were verified against official portals as of **2026-06-22**. Because details are subject to change, the system always displays a verification disclaimer instructing users to confirm details directly before visiting.

## Known limitations & future work

- **Workflow-node Callback Incompatibility**: ADK's workflow runner throws a `ValueError: Output already set` when the Guardrail Agent's `after_agent_callback` attempts to override output in workflow context (D015). The system is fully protected because the workflow's node exception block automatically executes the exact same programmatic fallback. A future refactor could convert the Guardrail Agent node into a pure `@node` Python function.
- **Geographic & Category Limits**: The dataset is restricted to Mumbai and covers exactly two categories. Scaling to wider geographies would require integration with live government database endpoints.
- **Phone Verification**: Contact details were sourced from official web listings, but organizations have not been personally contacted via phone calls.
- **Translation Quality**: Hindi and Marathi translations of disclaimers and crisis responses are hardcoded, but native speaker review is recommended before public deployment.
- **Cross-Session Memory**: Multi-turn persistence is maintained within a single session but is not persisted to database storage across multiple days.

## Track

Agents for Good

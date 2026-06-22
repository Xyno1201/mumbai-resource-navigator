import os
import sys
import json
from typing import Any, Optional
from google.adk.workflow import Workflow, node, RetryConfig
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.genai import types as genai_types

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the agents and schemas
from src.agents.intake_agent import intake_agent, IntakeOutput
from src.agents.matcher_agent import matcher_agent, MatcherOutput
from src.agents.guardrail_agent import guardrail_agent, GuardrailOutput

# Programmatic fallbacks for resilient execution when LLM quota is exhausted

def intake_programmatic_fallback(query: str) -> dict:
    query_lower = query.lower()
    
    category = "unclear"
    if any(k in query_lower for k in ["tiffin", "khana", "langar", "pantry", "ration", "rashan", "anaaj", "grocery", "food"]):
        category = "food_security"
    elif any(k in query_lower for k in ["bijli", "light", "pani", "water", "kiraya", "rent", "eviction", "makaan", "landlord"]):
        category = "rent_utility_support"
        
    areas = []
    for a in ["Dharavi", "Govandi", "Kurla", "Colaba", "Bandra", "Worli", "Sion"]:
        if a.lower() in query_lower:
            areas.append(a)
            
    ration_card_status = None
    if "bpl" in query_lower:
        ration_card_status = "BPL"
    elif "apl" in query_lower:
        ration_card_status = "APL"
    elif "aay" in query_lower:
        ration_card_status = "AAY"
    elif "no ration" in query_lower or "don't have a ration" in query_lower:
        ration_card_status = "none"
        
    urgency_signal = "routine"
    if any(k in query_lower for k in ["starving", "lose our home", "evicted tonight", "crisis", "emergency", "घर जा सकता है", "बेघर", "भूख", "संकट", "खतरे", "मदद करो"]):
        urgency_signal = "crisis"
    elif any(k in query_lower for k in ["tomorrow", "next week", "urgent"]):
        urgency_signal = "urgent"

    # Multilingual support: detect language programmatically
    has_devanagari = any('\u0900' <= c <= '\u097f' for c in query)
    if has_devanagari:
        marathi_dev = ["मला", "तुम्ही", "आहे", "नाही", "काय", "रुपये", "घरा"]
        marathi_lat = ["mala", "tumhi", "ahe", "nahi", "kaay", "aahe", "rupaye", "ghara"]
        if any(w in query_lower for w in marathi_dev + marathi_lat):
            detected_language = "marathi_devanagari"
        else:
            detected_language = "hindi_devanagari"
    else:
        hindi_vocab = {"rashan", "chahiye", "bijli", "kiraya", "khana", "ghar", "madad", "paisa", "bill", "mein", "rehte", "hain", "nahi", "zyada", "bahut", "aaj", "raat", "maddad", "rupaye"}
        words = set(query_lower.replace(",", " ").replace(".", " ").split())
        hindi_matches = words.intersection(hindi_vocab)
        
        english_vocab = {"need", "don't", "have", "we're", "lose", "home", "tonight", "please", "help", "the", "and", "under", "near"}
        english_matches = words.intersection(english_vocab)
        
        if hindi_matches and english_matches:
            detected_language = "hinglish"
        elif hindi_matches:
            detected_language = "romanized_hindi"
        else:
            detected_language = "english"
            
    return {
        "category": category,
        "areas": areas,
        "pincodes": [],
        "ration_card_status": ration_card_status,
        "income_monthly_inr": None,
        "urgency_signal": urgency_signal,
        "detected_local_terms": [],
        "detected_language": detected_language,
        "clarification_needed": "Could you tell me which area of Mumbai you're in?" if not areas else None
    }

def matcher_programmatic_fallback(intake_data: dict) -> dict:
    from mcp_server.server import search_resources
    
    category = intake_data.get("category")
    areas = intake_data.get("areas", [])
    pincodes = intake_data.get("pincodes", [])
    ration_card_status = intake_data.get("ration_card_status")
    income_monthly_inr = intake_data.get("income_monthly_inr")
    
    if category == "unclear":
        return {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": True
        }
        
    raw_results = search_resources(
        category=category,
        areas=areas if areas else None,
        pincodes=pincodes if pincodes else None,
        ration_card_status=ration_card_status,
        income_monthly_inr=income_monthly_inr
    )
    
    has_location = bool(areas or pincodes)
    has_ration = ration_card_status is not None
    has_income = income_monthly_inr is not None
    
    match_confidence = 0.4
    if has_location:
        match_confidence += 0.3
    if has_ration:
        match_confidence += 0.15
    if has_income:
        match_confidence += 0.15
        
    match_confidence = round(match_confidence, 2)
    
    results = []
    for r in raw_results:
        results.append({
            "resource_id": r.get("resource_id"),
            "name": r.get("name"),
            "short_description": r.get("short_description"),
            "service_type": r.get("service_type"),
            "operating_hours": r.get("operating_hours"),
            "eligibility_unconfirmed": r.get("eligibility_unconfirmed", True),
            "last_verified_date": r.get("last_verified_date"),
            "confidence_score": r.get("confidence_score", 0.0),
            "match_confidence": match_confidence
        })
        
    return {
        "results": results,
        "zero_results": len(results) == 0,
        "intake_was_unclear": False
    }

def guardrail_programmatic_fallback(guardrail_input: dict) -> dict:
    from src.agents.guardrail_agent import get_language_strings
    
    intake_data = guardrail_input.get("intake_data", {})
    matcher_data = guardrail_input.get("matcher_data", {})
    
    urgency_signal = intake_data.get("urgency_signal")
    category = intake_data.get("category")
    clarification_needed = intake_data.get("clarification_needed")
    detected_language = intake_data.get("detected_language", "english")
    
    crisis_text, disclaimer_text = get_language_strings(detected_language)
    
    results = matcher_data.get("results", [])
    zero_results = matcher_data.get("zero_results", False)
    intake_was_unclear = matcher_data.get("intake_was_unclear", False)
    
    if urgency_signal == "crisis":
        return {
            "response_text": crisis_text,
            "response_type": "crisis_redirect",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    if intake_was_unclear or category == "unclear":
        q_text = clarification_needed or "Could you clarify what kind of support you need?"
        return {
            "response_text": q_text,
            "response_type": "clarification_request",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    if zero_results or not results:
        msg = f"We could not find any verified resources in our database matching your request for {category.replace('_', ' ')}."
        if intake_data.get("areas"):
            msg += f" in the neighborhood of {', '.join(intake_data['areas'])}."
        msg += " Please try checking a broader area or neighborhood."
        return {
            "response_text": msg,
            "response_type": "zero_results",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    confident_results = [r for r in results if r.get("match_confidence", 0.0) >= 0.5]
    if not confident_results:
        msg = "We found some potential matches in our database, but they do not confidently fit your criteria. To avoid directing you to the wrong service, we are not showing these results. Please try broadening your search locality."
        return {
            "response_text": msg,
            "response_type": "no_confident_match",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    recommendation_lines = ["Here are the verified resources that match your needs:\n"]
    resource_ids = []
    
    for r in confident_results:
        r_id = r.get("resource_id")
        resource_ids.append(r_id)
        
        line = f"- **{r.get('name')}** (ID: {r_id})\n"
        line += f"  *Service:* {r.get('short_description')}\n"
        line += f"  *Hours:* {r.get('operating_hours')}\n"
        
        if r.get("eligibility_unconfirmed"):
            line += "  *Note:* Please confirm eligibility (e.g. ration card status or income) directly with the organization.\n"
            
        recommendation_lines.append(line)
        
    recommendation_lines.append(f"\n{disclaimer_text}")
    
    return {
        "response_text": "\n".join(recommendation_lines),
        "response_type": "resource_recommendation",
        "disclaimer_shown": True,
        "resources_included": resource_ids
    }

# 1. Intake execution wrapper with exception handling
@node(rerun_on_resume=True)
async def run_intake(ctx: Context, node_input: Any = None) -> Event:
    query = ""
    if hasattr(node_input, "parts") and node_input.parts:
        query = node_input.parts[0].text
    elif isinstance(node_input, dict):
        query = node_input.get("text", "")
    elif isinstance(node_input, str):
        query = node_input

    try:
        result = await ctx.run_node(intake_agent, node_input=query)
        intake_data = None
        if isinstance(result, dict):
            intake_data = result
        elif hasattr(result, "model_dump"):
            intake_data = result.model_dump()
        else:
            intake_data = json.loads(str(result))
            
        return Event(output=intake_data, state={"intake_data": intake_data, "_intake_fallback": False})
    except Exception as e:
        print(f"Intake Agent LLM run failed ({e}). Using programmatic fallback.")
        fallback_data = intake_programmatic_fallback(query)
        return Event(output=fallback_data, state={"intake_data": fallback_data, "_intake_fallback": True})

# 2. Routing function node based on intake output
@node
def route_intake(ctx: Context, node_input: Any = None) -> Event:
    intake_data = None
    if isinstance(node_input, dict):
        intake_data = node_input
    if not intake_data:
        intake_data = ctx.state.get("intake_data")

    category = intake_data.get("category") if intake_data else "unclear"
    urgency_signal = intake_data.get("urgency_signal") if intake_data else "routine"
    
    state_delta = {"intake_data": intake_data}
    
    if urgency_signal == "crisis" or category == "unclear":
        return Event(output=intake_data, route="skip_matcher", state=state_delta)
    else:
        return Event(output=intake_data, route="run_matcher", state=state_delta)

# 3. Matcher execution wrapper with exception handling
@node(rerun_on_resume=True)
async def run_matcher(ctx: Context, node_input: Any = None) -> Event:
    intake_data = None
    if isinstance(node_input, dict):
        intake_data = node_input
    if not intake_data:
        intake_data = ctx.state.get("intake_data", {})

    try:
        result = await ctx.run_node(matcher_agent, node_input=json.dumps(intake_data))
        matcher_data = None
        if isinstance(result, dict):
            matcher_data = result
        elif hasattr(result, "model_dump"):
            matcher_data = result.model_dump()
        else:
            matcher_data = json.loads(str(result))
            
        return Event(output=matcher_data, state={"matcher_data": matcher_data, "_matcher_fallback": False})
    except Exception as e:
        print(f"Matcher Agent LLM run failed ({e}). Using programmatic fallback.")
        fallback_data = matcher_programmatic_fallback(intake_data)
        return Event(output=fallback_data, state={"matcher_data": fallback_data, "_matcher_fallback": True})

# 4. Preparation node when matcher is skipped
@node
def prepare_skip(ctx: Context, node_input: Any = None) -> Event:
    intake_data = None
    if isinstance(node_input, dict):
        intake_data = node_input
    if not intake_data:
        intake_data = ctx.state.get("intake_data", {})
        
    guardrail_input = {
        "intake_data": intake_data,
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": intake_data.get("category") == "unclear" if intake_data else True
        },
        "response_language_instruction": f"Please generate the response_text in the language/register matching detected_language ({intake_data.get('detected_language', 'english')}). Never generate the disclaimer, it will be appended verbatim."
    }
    return Event(
        output=json.dumps(guardrail_input),
        state={"guardrail_input": guardrail_input}
    )

# 5. Preparation node when matcher has run
@node
def prepare_match(ctx: Context, node_input: Any = None) -> Event:
    intake_data = ctx.state.get("intake_data", {})
    matcher_data = None
    if isinstance(node_input, dict):
        matcher_data = node_input
    elif isinstance(node_input, str):
        try:
            matcher_data = json.loads(node_input)
        except Exception:
            pass
            
    if not matcher_data:
        matcher_data = ctx.state.get("matcher_data", {})

    guardrail_input = {
        "intake_data": intake_data,
        "matcher_data": matcher_data,
        "response_language_instruction": f"Please generate the response_text in the language/register matching detected_language ({intake_data.get('detected_language', 'english')}). Never generate the disclaimer, it will be appended verbatim."
    }
    return Event(
        output=json.dumps(guardrail_input),
        state={"guardrail_input": guardrail_input}
    )

# 6. Guardrail execution wrapper with exception handling
@node(rerun_on_resume=True)
async def run_guardrail(ctx: Context, node_input: Any = None) -> Event:
    guardrail_input = None
    if isinstance(node_input, dict):
        guardrail_input = node_input
    elif isinstance(node_input, str):
        try:
            guardrail_input = json.loads(node_input)
        except Exception:
            pass
            
    if not guardrail_input:
        guardrail_input = ctx.state.get("guardrail_input", {})

    try:
        result = await ctx.run_node(guardrail_agent, node_input=json.dumps(guardrail_input))
        guardrail_output = None
        if isinstance(result, dict):
            guardrail_output = result
        elif hasattr(result, "model_dump"):
            guardrail_output = result.model_dump()
        else:
            guardrail_output = json.loads(str(result))
            
        return Event(output=guardrail_output, state={"_guardrail_fallback": False})
    except Exception as e:
        print(f"Guardrail Agent LLM run failed ({e}). Using programmatic fallback.")
        fallback_data = guardrail_programmatic_fallback(guardrail_input)
        return Event(output=fallback_data, state={"_guardrail_fallback": True})

# Instantiate the Workflow representing the full Mumbai Resource Navigator agent
mumbai_navigator_workflow = Workflow(
    name="mumbai_navigator_workflow",
    edges=[
        ('START', run_intake),
        (run_intake, route_intake),
        (route_intake, {"skip_matcher": prepare_skip, "run_matcher": run_matcher}),
        (run_matcher, prepare_match),
        (prepare_skip, run_guardrail),
        (prepare_match, run_guardrail)
    ],
    output_schema=GuardrailOutput,
    retry_config=RetryConfig(max_attempts=3, initial_delay=5.0, max_delay=30.0)
)

async def run_navigator(query: str, session_id: str, runner: Any, session_service: Any) -> dict:
    """
    Top-level entry point function that runs the mumbai_navigator_workflow
    and aggregates fallback flags into a 'fallback_used' field in its final return dict.
    """
    await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    final_output_dict = {}
    
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=query)])
    ):
        if event.output is not None:
            if isinstance(event.output, dict):
                final_output_dict = event.output
            elif hasattr(event.output, "model_dump"):
                final_output_dict = event.output.model_dump()
            else:
                try:
                    final_output_dict = json.loads(str(event.output))
                except Exception:
                    pass

    # Retrieve fallback flags from session state
    session = await session_service.get_session(app_name="app", user_id="test_user", session_id=session_id)
    
    intake_fallback = False
    matcher_fallback = False
    guardrail_fallback = False
    
    if session:
        intake_fallback = session.state.get("_intake_fallback", False)
        matcher_fallback = session.state.get("_matcher_fallback", False)
        guardrail_fallback = session.state.get("_guardrail_fallback", False)
        
    return {
        "response_text": final_output_dict.get("response_text", ""),
        "response_type": final_output_dict.get("response_type", "zero_results"),
        "disclaimer_shown": final_output_dict.get("disclaimer_shown", False),
        "resources_included": final_output_dict.get("resources_included", []),
        "fallback_used": {
            "intake": intake_fallback,
            "matcher": matcher_fallback,
            "guardrail": guardrail_fallback
        }
    }


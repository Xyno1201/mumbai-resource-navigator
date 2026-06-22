import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types as genai_types

# Define Pydantic schema for structured output of the Guardrail Agent
class GuardrailOutput(BaseModel):
    response_text: str = Field(
        description="The final user-facing response message."
    )
    response_type: Literal["resource_recommendation", "no_confident_match", "clarification_request", "crisis_redirect", "zero_results"] = Field(
        description="The category/type of the response."
    )
    disclaimer_shown: bool = Field(
        description="Must be True if response_type is 'resource_recommendation', otherwise False."
    )
    resources_included: List[str] = Field(
        default_factory=list,
        description="List of resource_ids actually recommended and shown (empty for other types)."
    )

CRISIS_RESPONSE_TEXT = (
    "If you are in immediate danger, facing eviction tonight, or in a life-threatening crisis, "
    "please contact emergency services immediately by dialing 100 (Police) or 108 (Ambulance). "
    "For free, confidential mental health support, you can also call Tele-MANAS at 14416, "
    "India's 24/7 government mental health helpline."
)

VERBATIM_DISCLAIMER = (
    "This is informational, not legal or financial advice. "
    "Details may have changed — please confirm directly with the organization before visiting."
)

async def enforce_guardrails(callback_context: CallbackContext) -> genai_types.Content | None:
    # 1. Parse the input data from the user message
    input_data = None
    for event in callback_context.session.events:
        if event.content and event.content.role == "user" and event.content.parts:
            text = event.content.parts[0].text
            try:
                input_data = json.loads(text)
                break
            except Exception:
                pass

    if not input_data:
        # Fallback to state if present
        input_data = callback_context.state.get("guardrail_input")

    if not input_data:
        return None

    # Extract intake and matcher data
    intake_data = input_data.get("intake_data", {})
    matcher_data = input_data.get("matcher_data", {})

    urgency_signal = intake_data.get("urgency_signal")
    category = intake_data.get("category")
    clarification_needed = intake_data.get("clarification_needed")

    results = matcher_data.get("results", [])
    zero_results = matcher_data.get("zero_results", False)
    intake_was_unclear = matcher_data.get("intake_was_unclear", False)

    # Rule 1: CRISIS CHECK FIRST
    if urgency_signal == "crisis":
        output = {
            "response_text": CRISIS_RESPONSE_TEXT,
            "response_type": "crisis_redirect",
            "disclaimer_shown": False,
            "resources_included": []
        }
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(output))]
        )

    # Rule 2: Clarification request
    if intake_was_unclear or category == "unclear":
        q_text = clarification_needed or "Could you clarify what kind of support you need?"
        output = {
            "response_text": q_text,
            "response_type": "clarification_request",
            "disclaimer_shown": False,
            "resources_included": []
        }
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(output))]
        )

    # Rule 3: Zero results
    if zero_results or not results:
        msg = f"We could not find any verified resources in our database matching your request for {category.replace('_', ' ')}."
        if intake_data.get("areas"):
            msg += f" in the neighborhood of {', '.join(intake_data['areas'])}."
        msg += " Please try checking a broader area or neighborhood."
        
        output = {
            "response_text": msg,
            "response_type": "zero_results",
            "disclaimer_shown": False,
            "resources_included": []
        }
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(output))]
        )

    # Rule 4: Filter results (match_confidence >= 0.5)
    confident_results = [r for r in results if r.get("match_confidence", 0.0) >= 0.5]
    if not confident_results:
        msg = "We found some potential matches in our database, but they do not confidently fit your criteria. To avoid directing you to the wrong service, we are not showing these results. Please try broadening your search locality."
        output = {
            "response_text": msg,
            "response_type": "no_confident_match",
            "disclaimer_shown": False,
            "resources_included": []
        }
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(output))]
        )

    # Rule 5: Confident results recommendation
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
        
    recommendation_lines.append(f"\n{VERBATIM_DISCLAIMER}")
    
    output = {
        "response_text": "\n".join(recommendation_lines),
        "response_type": "resource_recommendation",
        "disclaimer_shown": True,
        "resources_included": resource_ids
    }
    
    return genai_types.Content(
        role="model",
        parts=[genai_types.Part.from_text(text=json.dumps(output))]
    )

# Instantiate the Guardrail Agent
guardrail_agent = Agent(
    name="guardrail_agent",
    model="gemini-3.1-flash-lite",
    instruction="""
You are the Guardrail Agent for the Mumbai Local Resource Navigator.
Your job is to read the combined intake and matcher outputs and generate a structured response according to the schema.
However, a deterministic callback is attached to enforce all rules and formatting constraints precisely.
""",
    output_schema=GuardrailOutput,
    after_agent_callback=enforce_guardrails
)

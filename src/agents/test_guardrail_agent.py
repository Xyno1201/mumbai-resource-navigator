import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Load environment variables
load_dotenv(os.path.join(project_root, ".env"))

# Force developer API instead of Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# Import agent and responses
from src.agents.guardrail_agent import guardrail_agent, CRISIS_RESPONSE_TEXT, VERBATIM_DISCLAIMER

# Define test scenarios
test_scenarios = {
    "1. Case 4 (Crisis redirect check)": {
        "intake_data": {
            "category": "rent_utility_support",
            "urgency_signal": "crisis",
            "clarification_needed": "Could you tell me which area of Mumbai you're in?"
        },
        "matcher_data": {
            "results": [
                {
                    "resource_id": "RU-002",
                    "name": "Eviction Prevention Counseling",
                    "short_description": "eviction notice help",
                    "service_type": "rent_support",
                    "operating_hours": "Tue/Thu 11:00-16:00",
                    "eligibility_unconfirmed": False,
                    "last_verified_date": "PLACEHOLDER",
                    "confidence_score": 0.0,
                    "match_confidence": 0.85
                }
            ],
            "zero_results": False,
            "intake_was_unclear": False
        }
    },
    "2. Case 3 (Intake unclear check)": {
        "intake_data": {
            "category": "unclear",
            "urgency_signal": "routine",
            "clarification_needed": "Could you tell me what kind of help you are looking for?"
        },
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": True
        }
    },
    "3. Colaba zero-results check": {
        "intake_data": {
            "category": "food_security",
            "urgency_signal": "routine",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": False
        }
    },
    "4. Case 1 (FS-001 match confidence 0.85)": {
        "intake_data": {
            "category": "food_security",
            "urgency_signal": "routine",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [
                {
                    "resource_id": "FS-001",
                    "name": "[PLACEHOLDER] Community Kitchen - Dharavi",
                    "short_description": "Daily free cooked meals (lunch + dinner) for individuals and families.",
                    "service_type": "community_kitchen",
                    "operating_hours": "12:00-14:00, 19:00-21:00 daily",
                    "eligibility_unconfirmed": False,
                    "last_verified_date": "PLACEHOLDER",
                    "confidence_score": 0.0,
                    "match_confidence": 0.85
                }
            ],
            "zero_results": False,
            "intake_was_unclear": False
        }
    },
    "5. Case 2 (RU-001 match confidence 0.85, eligibility unconfirmed)": {
        "intake_data": {
            "category": "rent_utility_support",
            "urgency_signal": "routine",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [
                {
                    "resource_id": "RU-001",
                    "name": "[PLACEHOLDER] Emergency Utility Relief Fund - M-East Ward",
                    "short_description": "One-time emergency grant toward overdue electricity/water bills.",
                    "service_type": "emergency_grant",
                    "operating_hours": "Mon-Fri, 10:00-17:00",
                    "eligibility_unconfirmed": True,
                    "last_verified_date": "PLACEHOLDER",
                    "confidence_score": 0.0,
                    "match_confidence": 0.85
                }
            ],
            "zero_results": False,
            "intake_was_unclear": False
        }
    },
    "6. Manufactured low-confidence case (match_confidence 0.3)": {
        "intake_data": {
            "category": "food_security",
            "urgency_signal": "routine",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [
                {
                    "resource_id": "FS-001",
                    "name": "[PLACEHOLDER] Community Kitchen - Dharavi",
                    "short_description": "Daily free cooked meals (lunch + dinner) for individuals and families.",
                    "service_type": "community_kitchen",
                    "operating_hours": "12:00-14:00, 19:00-21:00 daily",
                    "eligibility_unconfirmed": False,
                    "last_verified_date": "PLACEHOLDER",
                    "confidence_score": 0.0,
                    "match_confidence": 0.3
                }
            ],
            "zero_results": False,
            "intake_was_unclear": False
        }
    }
}

def run_guardrail_programmatic(scenario_data):
    # Deterministic local Python runner in case of API rate limit errors
    intake_data = scenario_data.get("intake_data", {})
    matcher_data = scenario_data.get("matcher_data", {})

    urgency_signal = intake_data.get("urgency_signal")
    category = intake_data.get("category")
    clarification_needed = intake_data.get("clarification_needed")

    results = matcher_data.get("results", [])
    zero_results = matcher_data.get("zero_results", False)
    intake_was_unclear = matcher_data.get("intake_was_unclear", False)

    # 1. Crisis Check
    if urgency_signal == "crisis":
        return {
            "response_text": CRISIS_RESPONSE_TEXT,
            "response_type": "crisis_redirect",
            "disclaimer_shown": False,
            "resources_included": []
        }

    # 2. Unclear Check
    if intake_was_unclear or category == "unclear":
        q_text = clarification_needed or "Could you clarify what kind of support you need?"
        return {
            "response_text": q_text,
            "response_type": "clarification_request",
            "disclaimer_shown": False,
            "resources_included": []
        }

    # 3. Zero Results Check
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

    # 4. Low Confidence Check
    confident_results = [r for r in results if r.get("match_confidence", 0.0) >= 0.5]
    if not confident_results:
        msg = "We found some potential matches in our database, but they do not confidently fit your criteria. To avoid directing you to the wrong service, we are not showing these results. Please try broadening your search locality."
        return {
            "response_text": msg,
            "response_type": "no_confident_match",
            "disclaimer_shown": False,
            "resources_included": []
        }

    # 5. Recommendation Check
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
    
    return {
        "response_text": "\n".join(recommendation_lines),
        "response_type": "resource_recommendation",
        "disclaimer_shown": True,
        "resources_included": resource_ids
    }

async def run_scenario(runner, session_service, label, scenario_data, idx):
    session_id = f"guardrail_session_{idx}"
    await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    # Store data in session state
    session = await session_service.get_session(app_name="app", user_id="test_user", session_id=session_id)
    if session:
        session.state["guardrail_input"] = scenario_data

    input_str = json.dumps(scenario_data)
    final_text = None
    
    try:
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session_id,
            new_message=genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=input_str)])
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
    except Exception as e:
        print(f"  Warning: Guardrail LLM run failed ({e}). Using programmatic fallback.")

    if not final_text:
        res = run_guardrail_programmatic(scenario_data)
        final_text = json.dumps(res)

    return final_text

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(agent=guardrail_agent, app_name="app", session_service=session_service)

    results = {}

    for idx, (label, data) in enumerate(test_scenarios.items(), 1):
        print(f"\nRunning Scenario: {label}...")
        out_text = await run_scenario(runner, session_service, label, data, idx)
        results[label] = out_text
        # Small delay to keep things running cleanly
        await asyncio.sleep(2.0)

    print("\n" + "="*80)
    print("GUARDRAIL RESULTS SUMMARY")
    print("="*80)

    for label, output in results.items():
        print(f"\n=== {label} ===")
        if output:
            try:
                parsed = json.loads(output)
                print(json.dumps(parsed, indent=2))
            except Exception:
                print(output)
        else:
            print("No output received.")

if __name__ == "__main__":
    asyncio.run(main())

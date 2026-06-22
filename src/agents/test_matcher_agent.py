import asyncio
import os
import sys
import json
from pydantic import BaseModel
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

# Import agents and schemas
from src.agents.intake_agent import intake_agent, IntakeOutput
from src.agents.matcher_agent import matcher_agent

# Test cases for Intake Agent
test_queries = {
    1: "I need tiffin near Dharavi, I don't have a ration card",
    2: "bijli bill bahut zyada hai, we're in Govandi, I have a BPL card",
    3: "I'm not sure what kind of help I need, things are just hard right now",
    5: "rashan chahiye, Kurla mein rehte hai"
}

# Pre-defined mock Intake outputs as fallback to prevent 429 quota exhaustion errors during testing
mock_intake_outputs = {
    1: IntakeOutput(
        category="food_security",
        areas=["Dharavi"],
        pincodes=[],
        ration_card_status="none",
        income_monthly_inr=None,
        urgency_signal="routine",
        detected_local_terms=["tiffin"]
    ),
    2: IntakeOutput(
        category="rent_utility_support",
        areas=["Govandi"],
        pincodes=[],
        ration_card_status="BPL",
        income_monthly_inr=None,
        urgency_signal="routine",
        detected_local_terms=["bijli bill"]
    ),
    3: IntakeOutput(
        category="unclear",
        areas=[],
        pincodes=[],
        ration_card_status=None,
        income_monthly_inr=None,
        urgency_signal="routine",
        detected_local_terms=[]
    ),
    5: IntakeOutput(
        category="food_security",
        areas=["Kurla"],
        pincodes=[],
        ration_card_status=None,
        income_monthly_inr=None,
        urgency_signal="routine",
        detected_local_terms=["rashan"]
    )
}

async def get_intake_output(runner, session_service, case_idx, query_text):
    print(f"\n[Intake Step] Generating Intake for Case {case_idx}: \"{query_text}\"")
    session_id = f"intake_session_{case_idx}"
    
    # Create session
    await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    try:
        final_text = None
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session_id,
            new_message=genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=query_text)])
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                    
        if final_text:
            parsed = json.loads(final_text)
            return IntakeOutput(**parsed)
    except Exception as e:
        print(f"  Warning: Intake agent execution failed ({e}). Using mock fallback.")
        
    return mock_intake_outputs[case_idx]

async def run_matcher(runner, session_service, intake_output: IntakeOutput, test_label: str):
    session_id = f"matcher_session_{test_label.replace(' ', '_').lower()}"
    await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    # Store intake_data in state so the formatter callback can access it
    session = await session_service.get_session(app_name="app", user_id="test_user", session_id=session_id)
    if session:
        session.state["intake_data"] = intake_output.model_dump()
    
    # Serialize to JSON to pass as input
    input_str = json.dumps(intake_output.model_dump())
    
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
        print(f"  Warning: Matcher Agent run failed ({e}). Using programmatic fallback.")
        
    if not final_text:
        # Programmatic fallback: call tool directly using server function and compute output
        from mcp_server.server import search_resources
        
        category = intake_output.category
        areas = intake_output.areas
        pincodes = intake_output.pincodes
        ration_card_status = intake_output.ration_card_status
        income_monthly_inr = intake_output.income_monthly_inr
        
        if category == "unclear":
            fallback_out = {
                "results": [],
                "zero_results": True,
                "intake_was_unclear": True
            }
            return json.dumps(fallback_out)
            
        # Run search
        raw_results = search_resources(
            category=category,
            areas=areas if areas else None,
            pincodes=pincodes if pincodes else None,
            ration_card_status=ration_card_status,
            income_monthly_inr=income_monthly_inr
        )
        
        # Calculate match_confidence
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
            
        fallback_out = {
            "results": results,
            "zero_results": len(results) == 0,
            "intake_was_unclear": False
        }
        return json.dumps(fallback_out)
        
    return final_text

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)
        
    session_service = InMemorySessionService()
    intake_runner = Runner(agent=intake_agent, app_name="app", session_service=session_service)
    matcher_runner = Runner(agent=matcher_agent, app_name="app", session_service=session_service)
    
    results = {}
    
    # Step 1: Run case 1, 2, 5 (Intake -> Matcher)
    for idx in [1, 2, 5]:
        query = test_queries[idx]
        intake_out = await get_intake_output(intake_runner, session_service, idx, query)
        print(f"  Intake Structured Output: {intake_out.model_dump_json(indent=2)}")
        
        # Add 5s delay between calls to prevent rate limits
        await asyncio.sleep(5.0)
        
        print(f"[Matcher Step] Running Matcher on Case {idx} intake...")
        matcher_out = await run_matcher(matcher_runner, session_service, intake_out, f"Case {idx}")
        results[f"Case {idx}"] = matcher_out
        
        await asyncio.sleep(5.0)
        
    # Step 2: Run Case 3 directly (category unclear)
    print("\n[Matcher Step] Testing Case 3 (category unclear) directly...")
    unclear_intake = mock_intake_outputs[3]
    matcher_out_3 = await run_matcher(matcher_runner, session_service, unclear_intake, "Case 3 Unclear")
    results["Case 3"] = matcher_out_3
    
    await asyncio.sleep(5.0)
    
    # Step 3: Run Manual Test (food_security in Colaba)
    print("\n[Matcher Step] Testing Manual Test (category food_security, areas ['Colaba']) directly...")
    manual_intake = IntakeOutput(
        category="food_security",
        areas=["Colaba"],
        pincodes=[],
        ration_card_status=None,
        income_monthly_inr=None,
        urgency_signal="routine",
        detected_local_terms=[]
    )
    matcher_out_manual = await run_matcher(matcher_runner, session_service, manual_intake, "Manual Test")
    results["Manual Test"] = matcher_out_manual
    
    # Output all results formatted
    print("\n" + "="*80)
    print("MATCH RESULTS SUMMARY")
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
            print("No output or error occurred.")

if __name__ == "__main__":
    asyncio.run(main())

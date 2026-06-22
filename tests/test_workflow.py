import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

# Import the workflow
from src.workflow import mumbai_navigator_workflow, run_navigator

# Test inputs representing the 5 cases
test_cases = {
    "Case 1 (Food matching, Dharavi, no ration card)": "I need tiffin near Dharavi, I don't have a ration card",
    "Case 2 (Rent/Utility support, Govandi, BPL card)": "bijli bill bahut zyada hai, we're in Govandi, I have a BPL card",
    "Case 3 (Category unclear)": "I'm not sure what kind of help I need, things are just hard right now",
    "Case 4 (Crisis redirect check)": "we might lose our home tonight, please help",
    "Case 5 (Food matching, Kurla, omitted ration card)": "rashan chahiye, Kurla mein rehte hai"
}

async def run_scenario(runner, session_service, label, query, idx):
    session_id = f"workflow_session_{idx}"
    print(f"\nRunning Scenario: {label}")
    print(f"Query: \"{query}\"")
    print("-" * 60)
    
    try:
        res_dict = await run_navigator(query, session_id, runner, session_service)
        return json.dumps(res_dict)
    except Exception as e:
        print(f"ERROR executing workflow: {e}")
        return None

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(agent=mumbai_navigator_workflow, app_name="app", session_service=session_service)

    results = {}

    for idx, (label, query) in enumerate(test_cases.items(), 1):
        out_text = await run_scenario(runner, session_service, label, query, idx)
        results[label] = out_text
        # Small delay to keep things running cleanly and avoid rate limits
        await asyncio.sleep(12.0)

    print("\n" + "="*80)
    print("WORKFLOW TEST RESULTS SUMMARY")
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

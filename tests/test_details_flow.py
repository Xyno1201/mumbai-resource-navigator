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

# Import the workflow
from src.workflow import mumbai_navigator_workflow, run_navigator

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(agent=mumbai_navigator_workflow, app_name="app", session_service=session_service)

    session_id = "details_flow_test_session"

    turns = [
        ("Turn 1", "I need food help near Dharavi"),
        ("Turn 2", "tell me more about the first one"),
        ("Turn 3", "what documents do I need to bring?")
    ]

    for turn_label, query in turns:
        print("\n" + "="*80)
        print(f"Executing {turn_label}")
        print(f"Query: \"{query}\"")
        print("-" * 80)
        
        try:
            # We pass session_id as both session_id and existing_session_id to persist across turns
            res = await run_navigator(
                query=query,
                session_id=session_id,
                runner=runner,
                session_service=session_service,
                existing_session_id=session_id
            )
            
            print(f"response_type: {res.get('response_type')}")
            print(f"session_id: {res.get('session_id')}")
            print("response_text:")
            print(res.get("response_text"))
            print(f"fallback_used: {res.get('fallback_used')}")
        except Exception as e:
            print(f"ERROR executing turn: {e}")
            
        # Small delay to keep things running cleanly and avoid rate limits
        await asyncio.sleep(5.0)

if __name__ == "__main__":
    # Ensure stdout handles UTF-8 for printing potential non-English characters cleanly
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(main())

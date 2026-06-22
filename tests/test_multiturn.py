import asyncio
import os
import sys
import json
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Load environment variables
load_dotenv(os.path.join(project_root, ".env"))

# Force developer API instead of Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from src.workflow import mumbai_navigator_workflow, run_navigator

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(agent=mumbai_navigator_workflow, app_name="app", session_service=session_service)

    # Initial session ID
    session_id = "test_multiturn_session"
    existing_session_id = None

    turns = [
        "I'm not sure what kind of help I need, things are just hard right now",
        "food help",
        "Dharavi"
    ]

    for idx, query in enumerate(turns, 1):
        print(f"\n=== Turn {idx} ===")
        print(f"Query: \"{query}\"")
        print(f"Session ID sent: {existing_session_id or session_id}")
        
        try:
            response = await run_navigator(
                query=query,
                session_id=session_id,
                runner=runner,
                session_service=session_service,
                existing_session_id=existing_session_id
            )
            # Retrieve the session ID from response to pass back
            existing_session_id = response.get("session_id")
            
            print(f"Session ID returned: {existing_session_id}")
            print(f"Response Type: {response.get('response_type')}")
            print(f"Response Text:\n{response.get('response_text')}")
            print(f"Fallback Used: {response.get('fallback_used')}")
        except Exception as e:
            print(f"ERROR: {e}")
            
        # Small delay to keep things running cleanly
        await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(main())

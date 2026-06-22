import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv

# Set UTF-8 encoding for standard output and error to avoid encoding errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to sys.path
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
        print("ERROR: GEMINI_API_KEY is not set. Please set it in your .env file.")
        sys.exit(1)

    print("=" * 60)
    print("Welcome to Mumbai Local Resource Navigator!")
    print("Type your request below.")
    print("Type 'new' or 'reset' to start a new conversation.")
    print("Press Ctrl+C or type 'exit' to quit.")
    print("=" * 60)

    session_service = InMemorySessionService()
    runner = Runner(agent=mumbai_navigator_workflow, app_name="app", session_service=session_service)
    
    current_session_id = None

    while True:
        try:
            try:
                user_input = input("\nYou: ").strip()
            except EOFError:
                break
                
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                break

            if user_input.lower() in ("new", "reset"):
                current_session_id = None
                print("\n[Conversation reset. Starting a new session...]")
                continue

            # If there's no active session, generate a unique one
            if not current_session_id:
                temp_session_id = "session_" + uuid.uuid4().hex[:8]
                existing_session_id = None
            else:
                temp_session_id = current_session_id
                existing_session_id = current_session_id

            # Run navigator
            response = await run_navigator(
                query=user_input,
                session_id=temp_session_id,
                runner=runner,
                session_service=session_service,
                existing_session_id=existing_session_id
            )

            # Store the session_id returned
            current_session_id = response.get("session_id", temp_session_id)

            # Print output
            print(f"\nAssistant: {response['response_text']} [{response['response_type']}]")

            # Check if any fallbacks were used
            fallbacks = response.get("fallback_used", {})
            if any(fallbacks.values()):
                fallback_names = [k for k, v in fallbacks.items() if v]
                print(f"\n[WARNING: Degraded output. Fallback used for: {', '.join(fallback_names)}]")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")

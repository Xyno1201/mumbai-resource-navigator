import asyncio
import os
import sys
import json
from pydantic import BaseModel

# Add parent directories to sys.path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load environment variables from .env file
from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(project_root, ".env"))

# Force developer API instead of Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# If GEMINI_API_KEY is not in environment but present under a different name, link it
if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from src.agents.intake_agent import intake_agent

test_cases = [
    "I need tiffin near Dharavi, I don't have a ration card",
    "bijli bill bahut zyada hai, we're in Govandi, I have a BPL card",
    "I'm not sure what kind of help I need, things are just hard right now",
    "we might lose our home tonight, please help",
    "rashan chahiye, Kurla mein rehte hai"
]

async def run_test_case(runner, session_service, user_input, index):
    session_id = f"test_session_{index}"
    # Create or get session
    session = await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    print(f"\nRunning Case {index}: \"{user_input}\"")
    print("-" * 60)
    
    final_text = None
    # Run the agent
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text
            
    # Parse and print the structured output
    print("Structured Intake Data:")
    if final_text:
        try:
            parsed_data = json.loads(final_text)
            print(json.dumps(parsed_data, indent=2))
        except Exception as e:
            print(f"ERROR: Could not parse response as JSON: {final_text}. Error: {e}")
    else:
        print("ERROR: No response received from agent!")

async def main():
    print("Starting Intake Agent Tests...")
    # Verify API key presence
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set! Please check your .env file.")
        sys.exit(1)
        
    session_service = InMemorySessionService()
    runner = Runner(agent=intake_agent, app_name="app", session_service=session_service)
    
    for i, test_input in enumerate(test_cases, 1):
        await run_test_case(runner, session_service, test_input, i)
        await asyncio.sleep(2.0)

if __name__ == "__main__":
    asyncio.run(main())

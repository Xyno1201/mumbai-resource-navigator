import asyncio
import os
import sys
import json
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

load_dotenv(os.path.join(project_root, ".env"))
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
if "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from src.agents.intake_agent import intake_agent

async def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set.")
        sys.exit(1)

    session_service = InMemorySessionService()
    runner = Runner(agent=intake_agent, app_name="app", session_service=session_service)
    
    query = "I need tiffin near Dharavi, I don't have a ration card"
    session_id = "test_intake_session"
    
    await session_service.create_session(
        app_name="app",
        user_id="test_user",
        session_id=session_id
    )
    
    print(f"Running Intake Agent smoke test...")
    print(f"Query: \"{query}\"")
    print("-" * 60)
    
    final_output = None
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session_id,
        new_message=genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=query)])
    ):
        if getattr(event, "content", None) and event.content.parts:
            final_output = event.content.parts[0].text
            
    print("OUTPUT:")
    if hasattr(final_output, "model_dump"):
        print(json.dumps(final_output.model_dump(), indent=2))
    elif isinstance(final_output, dict):
        print(json.dumps(final_output, indent=2))
    else:
        print(final_output)

if __name__ == "__main__":
    asyncio.run(main())

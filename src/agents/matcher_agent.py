import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from google.adk.agents import Agent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types as genai_types

# Define the Pydantic schemas for the Matcher Agent's output
class ResourceMatch(BaseModel):
    resource_id: str = Field(
        description="Unique identifier of the resource (e.g., FS-001)."
    )
    name: str = Field(
        description="Name of the aid resource program/organization."
    )
    short_description: str = Field(
        description="A brief description of what the resource provides."
    )
    service_type: str = Field(
        description="The type of service provided (e.g. community_kitchen, ration_kit, eviction_prevention, utility_relief)."
    )
    operating_hours: str = Field(
        description="The days and times the resource is open/operational."
    )
    eligibility_unconfirmed: bool = Field(
        description="True if some eligibility criteria (e.g., income ceiling or ration card requirement) were not fully verified from the intake query."
    )
    last_verified_date: str = Field(
        description="Date the resource was last verified."
    )
    confidence_score: float = Field(
        description="The dataset's own verification confidence score (distinct from match_confidence)."
    )
    match_confidence: float = Field(
        description="The calculated match confidence score based on the number of user criteria used to filter (0.0 to 1.0)."
    )

class MatcherOutput(BaseModel):
    results: List[ResourceMatch] = Field(
        default_factory=list,
        description="List of matched resources with their calculated match confidence scores."
    )
    zero_results: bool = Field(
        description="True if no resources matched the query or if the intake category was unclear."
    )
    intake_was_unclear: bool = Field(
        description="True if the intake category was 'unclear', meaning no search was performed."
    )

# Setup path for MCP server stdio connection
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
python_exe = os.path.abspath(os.path.join(project_root, "venv", "Scripts", "python.exe"))
server_script = os.path.abspath(os.path.join(project_root, "mcp_server", "server.py"))

# If for some reason venv python doesn't exist, fallback to sys.executable
if not os.path.exists(python_exe):
    python_exe = sys.executable

# Instantiate McpToolset using StdioConnectionParams and StdioServerParameters
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=python_exe,
            args=[server_script],
            env=os.environ.copy()
        )
    )
)

# Callback to calculate match_confidence deterministically and override output
async def calculate_matcher_output(callback_context: CallbackContext) -> genai_types.Content | None:
    # 1. Retrieve the original intake data from session state or conversation history
    intake_data = None
    if "intake_data" in callback_context.state:
        intake_data = callback_context.state["intake_data"]
    else:
        # Check conversation history for a user message containing intake output JSON
        for event in callback_context.session.events:
            if event.content and event.content.role == "user" and event.content.parts:
                text = event.content.parts[0].text
                try:
                    intake_data = json.loads(text)
                    break
                except Exception:
                    pass

    if not intake_data:
        return None

    category = intake_data.get("category")
    areas = intake_data.get("areas", [])
    pincodes = intake_data.get("pincodes", [])
    ration_card_status = intake_data.get("ration_card_status")
    income_monthly_inr = intake_data.get("income_monthly_inr")

    # If the intake category is unclear, return empty results
    if category == "unclear":
        output_obj = {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": True
        }
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(output_obj))]
        )

    # Calculate match_confidence deterministically:
    # Base (0.4) for category match
    # +0.3 if areas or pincodes are provided
    # +0.15 if ration_card_status is provided (not null/None)
    # +0.15 if income_monthly_inr is provided (not null/None)
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

    # 2. Extract raw JSON response from model
    raw_text = None
    if callback_context.output and isinstance(callback_context.output, str):
        raw_text = callback_context.output
    elif callback_context.output and isinstance(callback_context.output, dict):
        raw_text = json.dumps(callback_context.output)

    if not raw_text:
        # Search the session events for the last model turn
        for event in reversed(callback_context.session.events):
            if event.author == callback_context.agent_name and event.content and event.content.parts:
                raw_text = event.content.parts[0].text
                break

    if not raw_text:
        return None

    try:
        data = json.loads(raw_text)
        results = data.get("results", [])
        for r in results:
            dataset_confidence = r.get("confidence_score", 0.0)
            blended_confidence = round(0.7 * match_confidence + 0.3 * dataset_confidence, 2)
            r["match_confidence"] = blended_confidence
            # Ensure eligibility_unconfirmed field exists (from tool response)
            if "eligibility_unconfirmed" not in r:
                r["eligibility_unconfirmed"] = True

        data["results"] = results
        data["zero_results"] = len(results) == 0
        data["intake_was_unclear"] = False

        # Return modified Content structure containing modified JSON
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=json.dumps(data))]
        )
    except Exception as e:
        print(f"Error post-processing matcher formatter output: {e}", file=sys.stderr)
        return None

# Sub-agent 1: Executes the search tool using parameters from intake data
matcher_tool_runner = Agent(
    name="matcher_tool_runner",
    model="gemini-3.1-flash-lite",
    instruction="""
You are the Matcher Tool Runner for the Mumbai Local Resource Navigator.
Your input is a JSON string representing the Intake agent's output containing:
- category: "food_security", "rent_utility_support", or "unclear"
- areas: list of neighborhood names in Mumbai
- pincodes: list of pincodes in Mumbai
- ration_card_status: "APL", "BPL", "AAY", "none", or null
- income_monthly_inr: monthly household income in INR or null

CRITICAL RULE:
If category is "unclear", you MUST NOT call the search_resources tool. Instead, respond with: "The intake category is unclear, skipping search."

Otherwise, call search_resources by mapping parameters directly without guessing or transforming:
- category (required): category
- areas (optional): areas (only if list is not empty)
- pincodes (optional): pincodes (only if list is not empty)
- ration_card_status (optional): ration_card_status (only if not null)
- income_monthly_inr (optional): income_monthly_inr (only if not null)

Present the raw list of resource summaries returned by the search_resources tool.
""",
    tools=[mcp_toolset]
)

# Sub-agent 2: Formats the results into the structured schema and triggers post-processing callback
matcher_formatter = Agent(
    name="matcher_formatter",
    model="gemini-3.1-flash-lite",
    instruction="""
You are the Matcher Formatter for the Mumbai Local Resource Navigator.
Read the conversation history to identify the search results returned by the tool or if the search was skipped.

If the search was skipped because the intake category was unclear, output:
- results: []
- zero_results: true
- intake_was_unclear: true

Otherwise, parse the raw results returned by the tool. If no results were returned, output empty results list.
Produce a JSON matching the structured schema. Keep match_confidence as 0.0 for now; it will be overwritten.
""",
    output_schema=MatcherOutput,
    after_agent_callback=calculate_matcher_output
)

# Combined sequential Matcher Agent
matcher_agent = SequentialAgent(
    name="matcher_agent",
    sub_agents=[matcher_tool_runner, matcher_formatter]
)

import os
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from google.adk.agents import Agent

# Define the Pydantic schema for structured output of the Intake Agent
class IntakeOutput(BaseModel):
    category: Literal["food_security", "rent_utility_support", "unclear"] = Field(
        description="Category of support needed. Use 'unclear' if the user's situation doesn't clearly match either 'food_security' or 'rent_utility_support'."
    )
    areas: List[str] = Field(
        default_factory=list,
        description="List of locality/neighborhood names in Mumbai mentioned or implied (e.g. Dharavi, Govandi, Kurla West)."
    )
    pincodes: List[str] = Field(
        default_factory=list,
        description="List of pincodes explicitly provided by the user."
    )
    ration_card_status: Optional[Literal["APL", "BPL", "AAY", "none"]] = Field(
        default=None,
        description="The user's stated ration card status. MUST be null/None if not explicitly mentioned. Never assume a default."
    )
    income_monthly_inr: Optional[int] = Field(
        default=None,
        description="The user's explicitly stated monthly income in INR. MUST be null/None if not explicitly mentioned."
    )
    urgency_signal: Literal["routine", "urgent", "crisis"] = Field(
        description="The urgency level. 'crisis' should only be used if there are signs of acute safety risk (such as immediate homelessness, starvation, or violence)."
    )
    detected_local_terms: List[str] = Field(
        default_factory=list,
        description="List of colloquial/local terms detected in the message that informed the category or context (e.g., 'tiffin', 'bijli bill', 'pantry', 'rashan')."
    )
    clarification_needed: Optional[str] = Field(
        default=None,
        description="A short, friendly clarifying question if category is 'unclear' OR if no area/pincode was mentioned at all. Otherwise, this MUST be null/None."
    )

# System instruction for the Intake Agent
INTAKE_INSTRUCTION = """
You are the Intake Agent for the Mumbai Local Resource Navigator. Your sole job is to analyze the user's message, identify key structured entities, and output them strictly according to the required schema.

## Category Mapping Rules
Map the user's request to one of the following categories:
- "food_security": if they need food, dry ration kits, cooked meals, school tiffins, senior meal deliveries, food banks, etc.
- "rent_utility_support": if they need emergency rent grants, eviction prevention, utility bill waivers (electricity, water), or reconnection help.
- "unclear": if their request does not clearly fall into either of these two categories (e.g., general medical help, job search, or vague requests). Do not force a guess.

## Location Rules
- Identify areas/localities in Mumbai (e.g. Dharavi, Govandi, Kurla West, Bandra, Worli, Sion, Nehru Nagar, Mankhurd, Saki Naka, Lower Parel).
- If they mention a locality, put the standard proper name in the 'areas' list (e.g., "Dharavi", "Govandi", "Kurla West", "Bandra East", "Worli", "Saki Naka").
- Only populate 'pincodes' if the user explicitly writes a pincode in their message (e.g. "400017"). Never guess or assume a pincode.

## Eligibility Details Rules
- Check for ration card status. Acceptable values: "APL", "BPL", "AAY", "none". If the user did not mention their ration card status, this MUST be null/None. Never default or assume.
- Check for stated monthly household income. If they mention an income figure (e.g. "10000 rupees a month"), extract it as an integer in 'income_monthly_inr'. If not stated, this MUST be null/None.

## Urgency Signal Rules
- "crisis": use this if the user's message indicates an acute, immediate safety or survival risk (e.g., "we will be thrown on the street tonight", "we have no food and haven't eaten in 3 days", "we are starving", "urgent safety emergency").
- "urgent": use this if they indicate a pressing need with a deadline (e.g., "bill is due tomorrow", "facing eviction next week").
- "routine": use this for standard requests without immediate threat or deadline.

## Local Terms Recognition
Look for and extract these local or colloquial terms:
- Food: "tiffin", "khana", "langar", "pantry", "ration", "rashan", "anaaj", "tiffin program", "grocery".
- Rent/Utility: "bijli bill", "light bill", "pani bill", "water bill", "kiraya", "rent help", "eviction", "makaan khali karna", "BMC bill", "SRA", "landlord".

## Clarification Rules
- If the 'category' is "unclear" OR if they did not mention any area or pincode, you MUST provide a friendly, short clarifying question in 'clarification_needed' (e.g., "Could you tell me which area of Mumbai you're in?").
- Otherwise, 'clarification_needed' must be null/None.

## Important Constraints
- Be honest. Do not assume or fabricate any details.
- Translate local slangs or abbreviations to their proper mapped values, but list them in 'detected_local_terms'.
- Ensure the output strictly conforms to the requested schema.
"""

# Instantiate the Intake Agent using gemini-2.5-flash
# We set output_schema to enforce structured output constraint
intake_agent = Agent(
    name="intake_agent",
    model="gemini-3.1-flash-lite",
    instruction=INTAKE_INSTRUCTION,
    output_schema=IntakeOutput,
    output_key="intake_data"
)

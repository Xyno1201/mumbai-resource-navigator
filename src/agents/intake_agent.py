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
    detected_language: Literal["english", "hindi_devanagari", "romanized_hindi", "hinglish", "marathi_devanagari"] = Field(
        default="english",
        description="The dominant language/register of the user's message. Default to 'english' if uncertain."
    )
    detail_request: bool = Field(
        default=False,
        description="True when user is asking for more details about a previously shown resource rather than a new search."
    )
    requested_resource_id: Optional[str] = Field(
        default=None,
        description="The resource_id the user is asking about (e.g. 'FS-001'), extracted from context if the user references a resource name or 'the first one' / 'that one'."
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

## Language Detection Rules
Detect the dominant language of the user's input using these signals and map to 'detected_language':
- "hindi_devanagari": message contains Devanagari script characters
- "marathi_devanagari": message contains Devanagari script AND Marathi-specific words (common ones: mala, tumhi, ahe, nahi, kaay, aahe, rupaye, ghara)
- "romanized_hindi": message is primarily Hindi words written in Latin script (e.g., rashan, chahiye, bijli, kiraya, khana, ghar, madad, paisa, bill, mein, rehte, hain, nahi) with little or no English
- "hinglish": message mixes English words and Hindi words naturally in the same sentence (e.g., "bijli bill bahut zyada hai, we're in Govandi")
- "english": default — predominantly English. Default to "english" if uncertain.

## Detail Request and Resource ID Extraction Rules
- Detect 'detail_request' (set to True) if the user's current query is asking for details, contact info, address, website, phone number, application process, or documents needed for a resource that was recommended in the previous turns of the conversation history.
- Signals include phrases like: "tell me more", "how do I contact", "address", "phone number", "how to apply", "documents needed", "more details", "website" (and their Hindi/Marathi equivalents).
- If 'detail_request' is True, extract the 'requested_resource_id' from the conversation history. Look at the resources shown in the previous assistant turns.
  - If the user uses a resource name (e.g. "Mumbai Roti Bank" or "SNEHA Nutrition") or its ID (e.g. "FS-001"), match it to the correct resource ID from history.
  - If the user says "the first one", "the first", "that one", or similar, extract the ID of the first resource recommended/listed in the previous assistant's response.
  - If multiple resources were shown/recommended in the previous turn and the user's request is ambiguous (e.g., "tell me more" without specifying which one), default 'requested_resource_id' to the first one shown and set 'clarification_needed' to a friendly note explaining that you defaulted to the first one (e.g., "Showing details for the first option. Please let me know if you wanted the other one.").
  - If the user is asking a follow-up question about the resource that was just detailed/shown in the previous turn, use that same resource ID.
  - If no resource ID can be found/inferred from context, leave 'requested_resource_id' as null/None.

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

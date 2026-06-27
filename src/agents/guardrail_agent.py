import os
import sys
import json
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

# Define Pydantic schema for structured output of the Guardrail Agent
class GuardrailOutput(BaseModel):
    response_text: str = Field(
        description="The final user-facing response message."
    )
    response_type: Literal["resource_recommendation", "no_confident_match", "clarification_request", "crisis_redirect", "zero_results"] = Field(
        description="The category/type of the response."
    )
    disclaimer_shown: bool = Field(
        description="Must be True if response_type is 'resource_recommendation', otherwise False."
    )
    resources_included: List[str] = Field(
        default_factory=list,
        description="List of resource_ids actually recommended and shown (empty for other types)."
    )

CRISIS_RESPONSE_TEXT = (
    "If you are in immediate danger, facing eviction tonight, or in a life-threatening crisis, "
    "please contact emergency services immediately by dialing 100 (Police) or 108 (Ambulance). "
    "For free, confidential mental health support, you can also call Tele-MANAS at 14416, "
    "India's 24/7 government mental health helpline."
)

VERBATIM_DISCLAIMER = (
    "This is informational, not legal or financial advice. "
    "Details may have changed — please confirm directly with the organization before visiting."
)

CRISIS_RESPONSE_TEXT_HI = (
    "यदि आप तत्काल खतरे में हैं, आज रात बेघर होने का सामना कर रहे हैं, "
    "या जीवन-संकट में हैं, तो कृपया तुरंत 100 (पुलिस) या 108 (एम्बुलेंस) "
    "डायल करें। मानसिक स्वास्थ्य सहायता के लिए टेली-मानस हेल्पलाइन 14416 "
    "पर कॉल करें — यह 24/7 निःशुल्क सेवा है।"
)
VERBATIM_DISCLAIMER_HI = (
    "यह जानकारी केवल सूचनात्मक उद्देश्यों के लिए है, कानूनी या वित्तीय "
    "सलाह नहीं। विवरण बदल सकते हैं — कृपया संस्था से सीधे संपर्क करके "
    "पुष्टि करें।"
)
CRISIS_RESPONSE_TEXT_MR = (
    "जर तुम्ही तात्काळ धोक्यात असाल, आज रात्री बेघर होण्याची शक्यता असेल "
    "किंवा जीवघेण्या संकटात असाल, तर कृपया लगेच 100 (पोलीस) किंवा "
    "108 (रुग्णवाहिका) डायल करा। मानसिक आरोग्य सहाय्यासाठी टेली-मानस "
    "14416 वर कॉल करा — ही 24/7 मोफत सेवा आहे।"
)
VERBATIM_DISCLAIMER_MR = (
    "ही माहिती केवळ माहितीच्या उद्देशाने आहे, कायदेशीर किंवा आर्थिक सल्ला "
    "नाही। तपशील बदलू शकतो — कृपया भेट देण्यापूर्वी संस्थेशी थेट संपर्क "
    "साधून खात्री करा।"
)
CRISIS_RESPONSE_TEXT_HG = (
    "Agar aap abhi immediate danger mein hain, aaj raat ghar kho sakte hain, "
    "ya kisi life-threatening crisis mein hain, toh please turant 100 (Police) "
    "ya 108 (Ambulance) dial karein. Free mental health support ke liye "
    "Tele-MANAS helpline 14416 par call karein — yeh 24/7 available hai."
)
VERBATIM_DISCLAIMER_HG = (
    "Yeh sirf informational hai, legal ya financial advice nahi. "
    "Details change ho sakti hain — please organization se seedha "
    "confirm karein visit se pehle."
)

REC_INTRO = {
    "english": "Here are the verified resources that match your needs:",
    "hinglish": "Aapki zaroorat ke hisaab se yeh verified resources available hain:",
    "romanized_hindi": "Aapki zaroorat ke hisaab se yeh verified resources available hain:",
    "hindi_devanagari": "यहाँ आपकी स्थिति के अनुसार सत्यापित संसाधन हैं:",
    "marathi_devanagari": "तुमच्या गरजेनुसार हे सत्यापित संसाधन उपलब्ध आहेत:"
}

ELIGIBILITY_NOTE = {
    "english": "Please confirm eligibility (e.g. ration card status or income) directly with the organization.",
    "hinglish": "Please eligibility confirm karein (e.g. ration card ya income) seedha organization se.",
    "romanized_hindi": "Please eligibility confirm karein (e.g. ration card ya income) seedha organization se.",
    "hindi_devanagari": "कृपया पात्रता (जैसे राशन कार्ड या आय) सीधे संस्था से पुष्टि करें।",
    "marathi_devanagari": "कृपया पात्रता (उदा. रेशन कार्ड किंवा उत्पन्न) थेट संस्थेकडून पुष्टी करा।"
}

def get_language_strings(detected_language: str) -> tuple[str, str]:
    lang = detected_language.lower() if detected_language else "english"
    if lang in ("hindi_devanagari", "romanized_hindi"):
        return CRISIS_RESPONSE_TEXT_HI, VERBATIM_DISCLAIMER_HI
    elif lang == "marathi_devanagari":
        return CRISIS_RESPONSE_TEXT_MR, VERBATIM_DISCLAIMER_MR
    elif lang == "hinglish":
        return CRISIS_RESPONSE_TEXT_HG, VERBATIM_DISCLAIMER_HG
    else:
        return CRISIS_RESPONSE_TEXT, VERBATIM_DISCLAIMER


DETAIL_LABELS = {
    "english": {
        "name": "Resource Name",
        "address": "Full Address",
        "phone": "Phone",
        "website": "Website",
        "application_process": "Application Process",
        "documents_required": "Documents Required",
        "operating_hours": "Operating Hours"
    },
    "hindi_devanagari": {
        "name": "संस्था का नाम",
        "address": "पूरा पता",
        "phone": "फ़ोन नंबर",
        "website": "वेबसाइट",
        "application_process": "आवेदन की प्रक्रिया",
        "documents_required": "आवश्यक दस्तावेज़",
        "operating_hours": "कार्यकाल का समय"
    },
    "romanized_hindi": {
        "name": "Sanstha ka Naam",
        "address": "Poora Pata",
        "phone": "Phone Number",
        "website": "Website",
        "application_process": "Aavedan ki Prakriya",
        "documents_required": "Aavashyak Dastavej",
        "operating_hours": "Kaam karne ka Samay"
    },
    "hinglish": {
        "name": "Resource Name",
        "address": "Full Address",
        "phone": "Phone Number",
        "website": "Website",
        "application_process": "Application Process",
        "documents_required": "Required Documents",
        "operating_hours": "Operating Hours"
    },
    "marathi_devanagari": {
        "name": "संस्थेचे नाव",
        "address": "पूर्ण पत्ता",
        "phone": "फोन नंबर",
        "website": "वेबसाईट",
        "application_process": "अर्ज करण्याची प्रक्रिया",
        "documents_required": "आवश्यक कागदपत्रे",
        "operating_hours": "कामाची वेळ"
    }
}

def format_detail_response(detail_data: dict, detected_language: str) -> dict:
    # Get the language-specific disclaimer
    _, disclaimer_text = get_language_strings(detected_language)
    
    # Get labels
    lang = detected_language.lower() if detected_language else "english"
    labels = DETAIL_LABELS.get(lang, DETAIL_LABELS["english"])
    
    name = detail_data.get("name", "N/A")
    contact = detail_data.get("contact", {})
    address = contact.get("address", "N/A")
    phone = contact.get("phone", "N/A")
    website = contact.get("website", "N/A")
    
    # Process application process as numbered list
    app_process_raw = detail_data.get("application_process", [])
    if isinstance(app_process_raw, list):
        app_process = "\n".join(f"{i+1}. {step}" for i, step in enumerate(app_process_raw))
    else:
        app_process = str(app_process_raw)
        
    # Process documents required
    eligibility = detail_data.get("eligibility", {})
    docs_raw = eligibility.get("documentation_required", [])
    if isinstance(docs_raw, list):
        docs = ", ".join(d.replace("_", " ") for d in docs_raw)
    else:
        docs = str(docs_raw)
        
    operating_hours = detail_data.get("operating_hours", "N/A")
    
    # Generate the formatted response text
    response_lines = [
        f"**{labels['name']}:** {name}",
        f"**{labels['address']}:** {address}",
        f"**{labels['phone']}:** {phone}",
        f"**{labels['website']}:** {website}",
        f"**{labels['application_process']}:**\n{app_process}",
        f"**{labels['documents_required']}:** {docs}",
        f"**{labels['operating_hours']}:** {operating_hours}",
        "",
        disclaimer_text
    ]
    
    response_text = "\n".join(response_lines)
    
    return {
        "response_text": response_text,
        "response_type": "resource_recommendation",
        "disclaimer_shown": True,
        "resources_included": [detail_data.get("resource_id")] if detail_data.get("resource_id") else []
    }

def enforce_guardrails_logic(guardrail_input: dict) -> dict:
    intake_data = guardrail_input.get("intake_data", {})
    matcher_data = guardrail_input.get("matcher_data", {})
    
    urgency_signal = intake_data.get("urgency_signal")
    category = intake_data.get("category")
    clarification_needed = intake_data.get("clarification_needed")
    detected_language = intake_data.get("detected_language", "english")
    if detected_language:
        detected_language = detected_language.lower()
    
    # Check if this is a detail request
    if guardrail_input.get("is_detail_request"):
        detail_data = guardrail_input.get("detail_data", {})
        return format_detail_response(detail_data, detected_language)
        
    crisis_text, disclaimer_text = get_language_strings(detected_language)
    
    results = matcher_data.get("results", [])
    zero_results = matcher_data.get("zero_results", False)
    intake_was_unclear = matcher_data.get("intake_was_unclear", False)
    
    # Rule 1: CRISIS CHECK FIRST
    if urgency_signal == "crisis":
        return {
            "response_text": crisis_text,
            "response_type": "crisis_redirect",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    # Rule 2: Clarification request
    if intake_was_unclear or category == "unclear":
        q_text = clarification_needed or "Could you clarify what kind of support you need?"
        return {
            "response_text": q_text,
            "response_type": "clarification_request",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    # Rule 3: Zero results
    if zero_results or not results:
        msg = f"We could not find any verified resources in our database matching your request for {category.replace('_', ' ')}."
        if intake_data.get("areas"):
            msg += f" in the neighborhood of {', '.join(intake_data['areas'])}."
        msg += " Please try checking a broader area or neighborhood."
        
        return {
            "response_text": msg,
            "response_type": "zero_results",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    # Rule 4: Filter results (match_confidence >= 0.55)
    confident_results = [r for r in results if r.get("match_confidence", 0.0) >= 0.55]
    if not confident_results:
        msg = "We found some potential matches in our database, but they do not confidently fit your criteria. To avoid directing you to the wrong service, we are not showing these results. Please try broadening your search locality."
        return {
            "response_text": msg,
            "response_type": "no_confident_match",
            "disclaimer_shown": False,
            "resources_included": []
        }
        
    # Rule 5: Confident results recommendation
    intro = REC_INTRO.get(detected_language, REC_INTRO["english"])
    recommendation_lines = [f"{intro}\n"]
    resource_ids = []
    
    for r in confident_results:
        r_id = r.get("resource_id")
        resource_ids.append(r_id)
        
        line = f"- **{r.get('name')}** (ID: {r_id})\n"
        line += f"  *Service:* {r.get('short_description')}\n"
        line += f"  *Hours:* {r.get('operating_hours')}\n"
        
        if r.get("eligibility_unconfirmed"):
            note = ELIGIBILITY_NOTE.get(detected_language, ELIGIBILITY_NOTE["english"])
            line += f"  *Note:* {note}\n"
            
        recommendation_lines.append(line)
        
    recommendation_lines.append(f"\n{disclaimer_text}")
    
    return {
        "response_text": "\n".join(recommendation_lines),
        "response_type": "resource_recommendation",
        "disclaimer_shown": True,
        "resources_included": resource_ids
    }


import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.agents.guardrail_agent import (
    enforce_guardrails_logic,
    CRISIS_RESPONSE_TEXT,
    VERBATIM_DISCLAIMER,
    CRISIS_RESPONSE_TEXT_HI
)

def run_tests():
    score = 0
    total = 6

    # Scenario 1 — Crisis redirect
    print("Running Scenario 1 — Crisis redirect...")
    scen1_input = {
        "intake_data": {
            "urgency_signal": "crisis",
            "category": "rent_utility_support",
            "detected_language": "english",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": False
        }
    }
    try:
        res1 = enforce_guardrails_logic(scen1_input)
        cond1 = (
            res1.get("response_type") == "crisis_redirect" and
            res1.get("response_text") == CRISIS_RESPONSE_TEXT and
            res1.get("disclaimer_shown") is False
        )
        if cond1:
            print("Scenario 1: PASS (Actual response_type: crisis_redirect)")
            score += 1
        else:
            print(f"Scenario 1: FAIL (Got res: {res1})")
    except Exception as e:
        print(f"Scenario 1: FAIL with exception {e}")

    # Scenario 2 — Clarification request
    print("\nRunning Scenario 2 — Clarification request...")
    scen2_input = {
        "intake_data": {
            "urgency_signal": "routine",
            "category": "unclear",
            "detected_language": "english",
            "clarification_needed": "Could you tell me which area of Mumbai you are in?"
        },
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": True
        }
    }
    try:
        res2 = enforce_guardrails_logic(scen2_input)
        cond2 = res2.get("response_type") == "clarification_request"
        if cond2:
            print("Scenario 2: PASS (Actual response_type: clarification_request)")
            score += 1
        else:
            print(f"Scenario 2: FAIL (Got res: {res2})")
    except Exception as e:
        print(f"Scenario 2: FAIL with exception {e}")

    # Scenario 3 — Zero results
    print("\nRunning Scenario 3 — Zero results...")
    scen3_input = {
        "intake_data": {
            "urgency_signal": "routine",
            "category": "food_security",
            "areas": ["Colaba"],
            "detected_language": "english",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [],
            "zero_results": True,
            "intake_was_unclear": False
        }
    }
    try:
        res3 = enforce_guardrails_logic(scen3_input)
        cond3 = (
            res3.get("response_type") == "zero_results" and
            res3.get("disclaimer_shown") is False
        )
        if cond3:
            print("Scenario 3: PASS (Actual response_type: zero_results)")
            score += 1
        else:
            print(f"Scenario 3: FAIL (Got res: {res3})")
    except Exception as e:
        print(f"Scenario 3: FAIL with exception {e}")

    # Scenario 4 — Resource recommendation (no eligibility flag)
    print("\nRunning Scenario 4 — Resource recommendation (no eligibility flag)...")
    scen4_input = {
        "intake_data": {
            "urgency_signal": "routine",
            "category": "food_security",
            "detected_language": "english",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [{
                "resource_id": "FS-001",
                "name": "SNEHA Nutrition Program",
                "short_description": "Community nutrition program",
                "service_type": "community_program",
                "operating_hours": "Mon-Sat 10:00-18:00",
                "eligibility_unconfirmed": False,
                "last_verified_date": "2026-06-22",
                "confidence_score": 0.88,
                "match_confidence": 0.75
            }],
            "zero_results": False,
            "intake_was_unclear": False
        }
    }
    try:
        res4 = enforce_guardrails_logic(scen4_input)
        cond4 = (
            res4.get("response_type") == "resource_recommendation" and
            res4.get("disclaimer_shown") is True and
            VERBATIM_DISCLAIMER in res4.get("response_text", "") and
            "FS-001" in res4.get("resources_included", [])
        )
        if cond4:
            print("Scenario 4: PASS (Actual response_type: resource_recommendation)")
            score += 1
        else:
            print(f"Scenario 4: FAIL (Got res: {res4})")
    except Exception as e:
        print(f"Scenario 4: FAIL with exception {e}")

    # Scenario 5 — Resource recommendation (with eligibility flag)
    print("\nRunning Scenario 5 — Resource recommendation (with eligibility flag)...")
    scen5_input = {
        "intake_data": {
            "urgency_signal": "routine",
            "category": "food_security",
            "detected_language": "english",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [{
                "resource_id": "FS-001",
                "name": "SNEHA Nutrition Program",
                "short_description": "Community nutrition program",
                "service_type": "community_program",
                "operating_hours": "Mon-Sat 10:00-18:00",
                "eligibility_unconfirmed": True,
                "last_verified_date": "2026-06-22",
                "confidence_score": 0.88,
                "match_confidence": 0.75
            }],
            "zero_results": False,
            "intake_was_unclear": False
        }
    }
    try:
        res5 = enforce_guardrails_logic(scen5_input)
        cond5 = (
            res5.get("response_type") == "resource_recommendation" and
            "Please confirm eligibility" in res5.get("response_text", "")
        )
        if cond5:
            print("Scenario 5: PASS (Actual response_type: resource_recommendation)")
            score += 1
        else:
            print(f"Scenario 5: FAIL (Got res: {res5})")
    except Exception as e:
        print(f"Scenario 5: FAIL with exception {e}")

    # Scenario 6 — No confident match (low confidence)
    print("\nRunning Scenario 6 — No confident match (low confidence)...")
    scen6_input = {
        "intake_data": {
            "urgency_signal": "routine",
            "category": "food_security",
            "detected_language": "english",
            "clarification_needed": None
        },
        "matcher_data": {
            "results": [{
                "resource_id": "FS-001",
                "name": "SNEHA Nutrition Program",
                "short_description": "Community nutrition program",
                "service_type": "community_program",
                "operating_hours": "Mon-Sat 10:00-18:00",
                "eligibility_unconfirmed": False,
                "last_verified_date": "2026-06-22",
                "confidence_score": 0.88,
                "match_confidence": 0.3
            }],
            "zero_results": False,
            "intake_was_unclear": False
        }
    }
    try:
        res6 = enforce_guardrails_logic(scen6_input)
        cond6 = res6.get("response_type") == "no_confident_match"
        if cond6:
            print("Scenario 6: PASS (Actual response_type: no_confident_match)")
            score += 1
        else:
            print(f"Scenario 6: FAIL (Got res: {res6})")
    except Exception as e:
        print(f"Scenario 6: FAIL with exception {e}")

    print("\n" + "="*40)
    print(f"Final Score: {score}/{total}")
    print("="*40)

if __name__ == "__main__":
    run_tests()

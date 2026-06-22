import sys
import os
import json

# Add parent directory to sys.path so we can import from mcp_server
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server import search_resources, get_resource_details

def print_banner(title):
    print("\n" + "="*80)
    print(f" {title} ".center(80, "="))
    print("="*80)

def main():
    print("Starting MCP Server Offline Filtering Logic Tests...")
    
    # Scenario 1: Dharavi food search with no ration card
    print_banner("SCENARIO 1: Food Security in Dharavi, Ration Card: none")
    try:
        res1 = search_resources(
            category="food_security",
            areas=["Dharavi"],
            ration_card_status="none"
        )
        print(json.dumps(res1, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Scenario 2: Govandi utility search with BPL card
    print_banner("SCENARIO 2: Rent/Utility Support in Govandi, Ration Card: BPL")
    try:
        res2 = search_resources(
            category="rent_utility_support",
            areas=["Govandi"],
            ration_card_status="BPL"
        )
        print(json.dumps(res2, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Scenario 3: Search with an area that has zero matches (e.g. Colaba)
    print_banner("SCENARIO 3: Food Security in Colaba (Zero Matches expected)")
    try:
        res3 = search_resources(
            category="food_security",
            areas=["Colaba"]
        )
        print(json.dumps(res3, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Scenario 4: Get resource details for FS-001 (Valid)
    print_banner("SCENARIO 4A: Get Resource Details for FS-001 (Valid)")
    try:
        res4a = get_resource_details("FS-001")
        print(json.dumps(res4a, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Scenario 4B: Get resource details for INVALID-ID (Not Found)
    print_banner("SCENARIO 4B: Get Resource Details for INVALID-ID (Not Found expected)")
    try:
        res4b = get_resource_details("INVALID-ID")
        print(json.dumps(res4b, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Scenario 5: Food Security in Kurla with unknown ration card (unconfirmed expected for FS-002)
    print_banner("SCENARIO 5: Food Security in Kurla, Ration Card: omitted (Check eligibility_unconfirmed)")
    try:
        res5 = search_resources(
            category="food_security",
            areas=["Kurla"]
        )
        print(json.dumps(res5, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

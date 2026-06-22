import os
import json
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Initialize the server
mcp = FastMCP("Mumbai Resource Navigator")

# Load resources at startup
current_dir = os.path.dirname(os.path.abspath(__file__))
resources_path = os.path.join(current_dir, "resources.json")

try:
    with open(resources_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        RESOURCES = data.get("resources", [])
except Exception as e:
    RESOURCES = []
    import sys
    print(f"Error loading resources.json from {resources_path}: {e}", file=sys.stderr)

@mcp.tool()
def search_resources(
    category: str,
    areas: Optional[List[str]] = None,
    pincodes: Optional[List[str]] = None,
    ration_card_status: Optional[str] = None,
    income_monthly_inr: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Search for resources in Mumbai based on category, area, pincode, ration card status, and income.
    
    Parameters:
    - category (str): exactly "food_security" or "rent_utility_support".
    - areas (list of str, optional): locality names to match against coverage areas (case-insensitive substring match).
    - pincodes (list of str, optional): exact match against coverage pincodes.
    - ration_card_status (str, optional): one of "APL", "BPL", "AAY", "none", or omitted/unknown.
    - income_monthly_inr (int, optional): user's stated monthly income.
    """
    # Validate category defensively
    if category not in ("food_security", "rent_utility_support"):
        raise ValueError(
            f"Invalid category '{category}'. Must be exactly 'food_security' or 'rent_utility_support'."
        )
        
    results = []
    
    for resource in RESOURCES:
        # 1. Filter to given category only
        if resource.get("category") != category:
            continue
            
        # 2. Location matching (areas OR pincodes)
        location_filtered = False
        matches_location = False
        
        # Check areas
        if areas:
            location_filtered = True
            for q_area in areas:
                if q_area:
                    # check if it is a case-insensitive substring of any coverage area
                    for r_area in resource.get("coverage", {}).get("areas", []):
                        if q_area.lower() in r_area.lower():
                            matches_location = True
                            break
                if matches_location:
                    break
                    
        # Check pincodes
        if pincodes:
            location_filtered = True
            for q_pin in pincodes:
                if q_pin:
                    for r_pin in resource.get("coverage", {}).get("pincodes", []):
                        if q_pin == r_pin:
                            matches_location = True
                            break
                if matches_location:
                    break
                    
        if location_filtered and not matches_location:
            continue
            
        # 3. Ration card eligibility check
        eligibility_unconfirmed = False
        eligibility = resource.get("eligibility", {})
        
        if eligibility.get("ration_card_required"):
            status_provided = False
            if ration_card_status and ration_card_status.strip() != "":
                if ration_card_status.lower() not in ("unknown", "omitted"):
                    status_provided = True
            
            if status_provided:
                status_upper = ration_card_status.strip().upper()
                accepted_types = [t.upper() for t in eligibility.get("ration_card_types_accepted", [])]
                if status_upper in accepted_types or "ANY" in accepted_types:
                    pass
                else:
                    # Exclude since we have card but it's not accepted
                    continue
            else:
                eligibility_unconfirmed = True
                
        # 4. Income eligibility check
        income_ceiling = eligibility.get("income_ceiling_monthly_inr")
        if income_ceiling is not None:
            if income_monthly_inr is not None:
                if income_monthly_inr > income_ceiling:
                    # Exclude since income exceeds ceiling
                    continue
            else:
                eligibility_unconfirmed = True
                
        # If it passed all filters, build the summary
        verification = resource.get("verification", {})
        summary = {
            "resource_id": resource.get("resource_id"),
            "name": resource.get("name"),
            "short_description": resource.get("short_description"),
            "service_type": resource.get("service_type"),
            "operating_hours": resource.get("operating_hours"),
            "eligibility_unconfirmed": eligibility_unconfirmed,
            "last_verified_date": verification.get("last_verified_date"),
            "confidence_score": verification.get("confidence_score", 0.0)
        }
        results.append(summary)
        
    # Sort results by verification.confidence_score descending
    results.sort(key=lambda x: x["confidence_score"], reverse=True)
    
    return results

@mcp.tool()
def get_resource_details(resource_id: str) -> Dict[str, Any]:
    """
    Returns the full resource object exactly as stored in resources.json for the given resource_id.
    
    If the resource_id doesn't exist, returns a clear "not found" dictionary.
    """
    for resource in RESOURCES:
        if resource.get("resource_id") == resource_id:
            return resource
    return {"error": f"Resource with ID '{resource_id}' not found."}

if __name__ == "__main__":
    mcp.run()

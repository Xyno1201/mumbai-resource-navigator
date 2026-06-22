import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the workflow from src.workflow
from src.workflow import mumbai_navigator_workflow

# Export as root_agent so adk web can discover it
root_agent = mumbai_navigator_workflow

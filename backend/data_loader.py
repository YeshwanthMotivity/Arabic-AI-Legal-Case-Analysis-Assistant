import json
import os
import logging
from typing import List, Dict
from models import Case

logger = logging.getLogger(__name__)

# Search for the dataset in order of likelihood
_search_paths = [
    os.path.join(os.path.dirname(__file__), "dataset", "laws", "saudi_general_court_judgments.json"), # New preferred location
    "/app/data/saudi_general_court_judgments.json",  # Docker absolute (legacy fallback)
    os.path.join(os.path.dirname(__file__), "data", "saudi_general_court_judgments.json"),  # Docker relative (legacy fallback)
    os.path.join(os.path.dirname(__file__), "..", "data", "saudi_general_court_judgments.json"),  # Local dev relative
]

DATA_PATH = None
for p in _search_paths:
    if os.path.exists(p):
        DATA_PATH = p
        break

if not DATA_PATH:
    # If not found, use the standard relative path for the error message
    DATA_PATH = _search_paths[2]


def load_cases(filter_real_only: bool = False) -> List[Case]:
    """
    Load cases from the JSON dataset.
    
    Args:
        filter_real_only (bool): If True, return only cases where is_real is True.
    
    Returns:
        List[Case]: List of Case objects.
    """
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")
        
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    cases = []
    for item in data:
        # Ensure is_real is present, default to True if missing (for older data structures)
        if "is_real" not in item:
            item["is_real"] = True
            
        case = Case(**item)
        
        if filter_real_only and not case.is_real:
            continue
            
        cases.append(case)
        
    return cases

if __name__ == "__main__":
    # Test loading
    try:
        all_cases = load_cases()
        real_cases = load_cases(filter_real_only=True)
        print(f"Total cases: {len(all_cases)}")
        print(f"Real cases: {len(real_cases)}")
    except Exception as e:
        print(f"Error: {e}")

import os
import yaml

BASE_DIR = os.path.dirname(__file__)

def load_prompt(filename: str, key: str) -> str:
    path = os.path.join(BASE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data[key]


therapist_prompt = load_prompt("therapist_prompt.yaml", "therapist_prompt")
safety_check_prompt = load_prompt("safety_check_prompt.yaml", "safety_check_prompt")
crisis_response = load_prompt("safety_check_prompt.yaml", "crisis_response")
not_mental_health_response = load_prompt("safety_check_prompt.yaml", "not_mental_health_response")


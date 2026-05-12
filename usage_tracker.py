import json
import os
from datetime import datetime

USAGE_FILE = "usage.json"

# Gemini 2.5 Flash pricing (per 1M tokens)
INPUT_COST_PER_M = 0.075
OUTPUT_COST_PER_M = 0.30


def _load():
    if not os.path.exists(USAGE_FILE):
        return {}
    with open(USAGE_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_usage(input_tokens: int, output_tokens: int):
    month = datetime.now().strftime("%Y-%m")
    data = _load()
    if month not in data:
        data[month] = {"input_tokens": 0, "output_tokens": 0, "requests": 0}
    data[month]["input_tokens"] += input_tokens
    data[month]["output_tokens"] += output_tokens
    data[month]["requests"] += 1
    _save(data)


def get_monthly_summary() -> dict:
    month = datetime.now().strftime("%Y-%m")
    data = _load()
    entry = data.get(month, {"input_tokens": 0, "output_tokens": 0, "requests": 0})
    input_tokens = entry["input_tokens"]
    output_tokens = entry["output_tokens"]
    cost = (input_tokens / 1_000_000 * INPUT_COST_PER_M) + (output_tokens / 1_000_000 * OUTPUT_COST_PER_M)
    return {
        "month": month,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "requests": entry["requests"],
        "estimated_cost": round(cost, 4),
    }

#
# uncertainty.py
#
# Contains the business logic for the AI Council Uncertainty Measurement gate.
#

import os
import json
from concurrent.futures import ThreadPoolExecutor

from gcp_clients import log_uncertainty_measurement
from api_clients import call_gemini_vertex_api, call_openai_api

# --- CONFIGURATION ---
# These are needed here because this module is now self-contained.
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = "us-central1" # Or get from env if you prefer
DATABASE_NAME = "rogue-ops-db"

class Uncertainty:
    LOW = "UNCERTAINTY_LOW"
    HIGH = "UNCERTAINTY_HIGH"

def measure_entry_uncertainty(live_analysis_data: dict, api_keys: dict, doctrine: dict) -> str:
    """
    Constructs a context-rich prompt and executes the consensus gating process.
    """
    print("--- Measuring Entry Uncertainty (AI Council) ---")

    # --- CONTEXTUAL PROMPT ENGINEERING ---
    playbook_content = []
    for name, content in doctrine.items():
        if name.startswith("PB/"):
            playbook_content.append(f"--- PLAYBOOK: {name} ---\n{content}\n")
    
    strategic_context = "\n".join(playbook_content)

    # FINAL CORRECTION: Re-inserting the mandatory instruction for OpenAI.
    prompt_template = """
    You are an expert market analyst for an autonomous trading system.
    Your analysis must be grounded in the provided strategic context.
    Analyze the live market data and provide your assessment.
    You MUST respond with a valid JSON object with three keys: "assessment" (string: "Positive", "Negative", or "Neutral"),
    "confidence" (string: "High", "Medium", or "Low"), and "reasoning" (string: a brief explanation referencing the playbooks).

    ### STRATEGIC CONTEXT ###
    {strategic_context}

    ### LIVE ANALYSIS DATA ###
    {analysis_data_json}
    """

    prompt = prompt_template.format(
        strategic_context=strategic_context,
        analysis_data_json=json.dumps(live_analysis_data, indent=4)
    )
    
    # --- END PROMPT ENGINEERING ---

    verdicts = {"gemini": None, "openai": None}

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_gemini = executor.submit(call_gemini_vertex_api, GCP_PROJECT_ID, GCP_LOCATION, prompt)
        future_openai = executor.submit(call_openai_api, api_keys.get("openai-api-key"), prompt)
        
        verdicts["gemini"] = future_gemini.result()
        verdicts["openai"] = future_openai.result()

    print("\n  --- AI Council Verdicts ---")
    print(f"  Gemini: {verdicts['gemini']}")
    print(f"  OpenAI: {verdicts['openai']}")

    gemini_verdict = verdicts["gemini"]
    openai_verdict = verdicts["openai"]
    
    consensus_result = Uncertainty.HIGH

    if (gemini_verdict.get("assessment") == "Negative" and gemini_verdict.get("confidence") == "High") or \
       (openai_verdict.get("assessment") == "Negative" and openai_verdict.get("confidence") == "High"):
        print("\n  >>> AI Council Consensus: UNCERTAINTY_HIGH (Hard Veto)")
        consensus_result = Uncertainty.HIGH
        
    elif (gemini_verdict.get("assessment") == "Positive" and gemini_verdict.get("confidence") == "High") and \
         (openai_verdict.get("assessment") == "Positive" and openai_verdict.get("confidence") == "High"):
        print("\n  >>> AI Council Consensus: UNCERTAINTY_LOW (Agreement)")
        consensus_result = Uncertainty.LOW
    
    else:
        print("\n  >>> AI Council Consensus: UNCERTAINTY_HIGH (Default/Disagreement)")
        consensus_result = Uncertainty.HIGH

    log_uncertainty_measurement(
        project_id=GCP_PROJECT_ID,
        database_name=DATABASE_NAME,
        verdicts=verdicts,
        consensus=consensus_result,
        prompt=prompt
    )
    return consensus_result

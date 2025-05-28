# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Default to google/gemini-flash-1.5 if not specified in .env, as it's generally available
OPENROUTER_LLM_MODEL = os.getenv("OPENROUTER_LLM_MODEL", "tngtech/deepseek-r1t-chimera:free")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_REFERRER_URL = os.getenv("OPENROUTER_REFERRER_URL", "")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "MultiAgentDocProcessor")


# --- General Configuration ---
SUPPORTED_INTENTS = [
    "Invoice", "RFQ", "Complaint", "Regulation", "General Inquiry",
    "Order Confirmation", "Job Application", "Feedback", "Other"
]

# Updated Target schema for JSON (RFQ example)
RFQ_TARGET_SCHEMA = {
    "rfq_id": {"type": "string", "required": True},
    "customer_name": {"type": "string", "required": True},
    "items": {
        "type": "list",
        "required": True,
        "schema": { # Schema for each item in the list
            "type": "dict",
            "schema": {
                "product_id": {"type": "string", "required": True},
                "quantity": {"type": "integer", "required": True},
                "description": {"type": "string", "required": False} # Added
            }
        }
    },
    "due_date": {"type": "string", "required": False},
    "contact_email": {"type": "string", "required": False}, # Added
    "shipping_address": { # Added as a nested object
        "type": "dict",
        "required": False,
        "schema": {
            "street": {"type": "string", "required": False},
            "city": {"type": "string", "required": False},
            "state": {"type": "string", "required": False},
            "zip": {"type": "string", "required": False}
        }
    },
    "notes": {"type": "string", "required": False} # Added
}

# You would also define INVOICE_TARGET_SCHEMA, COMPLAINT_TARGET_SCHEMA etc. here if needed
# For "Other" intents where raw_json_string goes, JSON agent currently has no schema.
# We could add a generic pass-through schema or handle 'Other' intent specifically in JSONAgent.
# For now, "No target schema defined for intent 'Other'" is the expected behavior for raw_json_string.
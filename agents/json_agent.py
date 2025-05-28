# agents/json_agent.py
from .base_agent import BaseAgent
from config import RFQ_TARGET_SCHEMA # Example, more schemas can be added/selected based on intent

class JSONAgent(BaseAgent):
    def __init__(self, shared_memory):
        super().__init__("JSONAgent", shared_memory)

    def _validate_and_extract(self, data, schema):
        extracted_data = {}
        anomalies = []

        # This is a basic validator. For complex needs, use jsonschema or pydantic.
        for key, field_schema in schema.items():
            is_required = field_schema.get("required", False)
            field_type = field_schema.get("type")

            if key not in data:
                if is_required:
                    anomalies.append(f"Missing required field: '{key}'")
                continue # Skip to next key

            value = data[key]

            # Basic type checking
            if field_type == "string" and not isinstance(value, str):
                anomalies.append(f"Field '{key}' expected string, got {type(value).__name__}")
            elif field_type == "integer" and not isinstance(value, int):
                anomalies.append(f"Field '{key}' expected integer, got {type(value).__name__}")
            elif field_type == "list" and not isinstance(value, list):
                anomalies.append(f"Field '{key}' expected list, got {type(value).__name__}")
            # Add more type checks (boolean, number, nested dicts with sub-schemas etc.)

            if "schema" in field_schema and isinstance(value, list): # list of dicts
                item_schema = field_schema["schema"]["schema"] # a bit nested due to example
                extracted_items = []
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        sub_extracted, sub_anomalies = self._validate_and_extract(item, item_schema)
                        extracted_items.append(sub_extracted)
                        for anom in sub_anomalies:
                            anomalies.append(f"Item {i} in list '{key}': {anom}")
                    else:
                        anomalies.append(f"Item {i} in list '{key}' is not a dictionary.")
                extracted_data[key] = extracted_items
            else:
                extracted_data[key] = value # Store the value if it passes/or even if it doesn't but is present

        # Check for extra fields not in schema (optional)
        for key in data:
            if key not in schema:
                anomalies.append(f"Unexpected field: '{key}'")

        return extracted_data, anomalies

    def process(self, data, conversation_id, source_identifier, previous_context=None):
        intent = previous_context.get("intent", "Unknown") if previous_context else "Unknown"
        print(f"[{conversation_id}] JSON Agent processing '{source_identifier}' for intent '{intent}'")

        # Select schema based on intent - for this example, we only have RFQ_TARGET_SCHEMA
        # In a real system, you'd have a mapping:
        # target_schema_map = {"RFQ": RFQ_TARGET_SCHEMA, "Invoice": INVOICE_SCHEMA, ...}
        # target_schema = target_schema_map.get(intent)
        target_schema = None
        if intent == "RFQ": # Example
            target_schema = RFQ_TARGET_SCHEMA
        # Add more schemas for other intents (e.g. Invoice, Order)

        extracted_fields = {}
        anomalies = []

        if target_schema:
            extracted_fields, anomalies = self._validate_and_extract(data, target_schema)
            status = "ProcessedWithAnomalies" if anomalies else "Processed"
        else:
            status = "ProcessedNoSchema"
            extracted_fields = data # No schema, just pass through
            anomalies.append(f"No target schema defined for intent '{intent}'. Data passed through.")


        self.shared_memory.log_event(
            conversation_id=conversation_id,
            agent_name=self.agent_name,
            status=status,
            source_identifier=source_identifier,
            input_format_classified="JSON", # From classifier
            intent_classified=intent, # From classifier
            extracted_data=extracted_fields,
            details={"anomalies": anomalies}
        )

        if anomalies:
            print(f"[{conversation_id}] JSON Agent found anomalies in '{source_identifier}': {anomalies}")
        else:
            print(f"[{conversation_id}] JSON Agent processed '{source_identifier}' successfully according to schema for '{intent}'.")

        return {"extracted_fields": extracted_fields, "anomalies": anomalies} 

# agents/email_agent.py
import re
from .base_agent import BaseAgent
from core.llm_utils import get_llm_json_response

class EmailAgent(BaseAgent):
    def __init__(self, shared_memory):
        super().__init__("EmailAgent", shared_memory)

    def _extract_sender_from_headers(self, headers):
        from_header = headers.get('From', headers.get('from'))
        if from_header:
            # Simple regex to extract email address, can be improved
            match = re.search(r'[\w\.-]+@[\w\.-]+', from_header)
            if match:
                return match.group(0)
        return "Unknown"

    def process(self, data, conversation_id, source_identifier, previous_context=None):
        # `data` is expected to be a dict: {"text": "...", "headers": {...}, "raw_eml_path": "..."}
        # or just {"text": "..."} if it was a PDF/Text file routed here
        email_text = data.get("text", "")
        headers = data.get("headers", {})

        # Intent and format are passed from Classifier
        intent = previous_context.get("intent", "Unknown") if previous_context else "Unknown"
        original_format = previous_context.get("format", "Email") if previous_context else "Email"

        print(f"[{conversation_id}] Email Agent processing '{source_identifier}' (Original format: {original_format}, Intent: {intent})")

        sender = self._extract_sender_from_headers(headers)
        if sender == "Unknown" and "sender" not in headers: # Try LLM if not found or simple parse
            pass # LLM extraction for sender can be added if needed

        # Use LLM for urgency and CRM formatting
        prompt = f"""
        Analyze the following email content (originally from a {original_format} document with classified intent: {intent}).
        Extract the following information for CRM usage:
        1. Sender Email (if identifiable from text, otherwise use '{sender}' if provided).
        2. A concise summary of the email (max 50 words).
        3. Determine the urgency (Low, Medium, High).
        4. List key entities or action items.

        Email Text:
        \"\"\"
        {email_text[:3000]}
        \"\"\"

        Respond in JSON format with keys: "sender_email", "summary", "urgency", "key_entities_actions".
        Example: {{"sender_email": "example@example.com", "summary": "Customer inquires about product X.", "urgency": "Medium", "key_entities_actions": ["Product X inquiry", "Follow up with customer"]}}
        """
        system_message = "You are an expert email analysis assistant. Respond ONLY in valid JSON."
        llm_extraction = get_llm_json_response(prompt, system_message=system_message)

        extracted_crm_data = {}
        if llm_extraction and not llm_extraction.get("error"):
            extracted_crm_data = {
                "sender_email": llm_extraction.get("sender_email", sender), # Prefer LLM if it finds one
                "subject": headers.get("Subject", headers.get("subject", "N/A")),
                "intent_classified": intent,
                "urgency": llm_extraction.get("urgency", "Unknown"),
                "summary_for_crm": llm_extraction.get("summary", "N/A"),
                "key_entities_actions": llm_extraction.get("key_entities_actions", [])
            }
            status = "Processed"
        else:
            status = "Error"
            extracted_crm_data = {
                "sender_email": sender,
                "subject": headers.get("Subject", headers.get("subject", "N/A")),
                "intent_classified": intent,
                "error_message": "LLM extraction failed or returned invalid data."
            }
            print(f"[{conversation_id}] Email Agent LLM extraction failed for '{source_identifier}'. Response: {llm_extraction}")


        self.shared_memory.log_event(
            conversation_id=conversation_id,
            agent_name=self.agent_name,
            status=status,
            source_identifier=source_identifier,
            input_format_classified=original_format, # This is the original format
            intent_classified=intent,
            extracted_data=extracted_crm_data, # This is the CRM formatted output
            details={"original_headers": headers if headers else "Not an EML"}
        )

        print(f"[{conversation_id}] Email Agent processed '{source_identifier}'. CRM Data: {extracted_crm_data}")
        return extracted_crm_data 

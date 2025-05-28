# agents/classifier_agent.py
import json
import os
import re # For better EML parsing and potentially LLM response cleaning
from email import message_from_string, message_from_bytes # For EML
from email.parser import BytesParser
from email.policy import default as default_policy

import fitz  # PyMuPDF
from .base_agent import BaseAgent # Assuming base_agent.py is in the same directory
from core.llm_utils import get_llm_json_response
from config import SUPPORTED_INTENTS

class ClassifierAgent(BaseAgent):
    def __init__(self, shared_memory, json_agent, email_agent):
        super().__init__("ClassifierAgent", shared_memory)
        self.json_agent = json_agent
        self.email_agent = email_agent

    def _get_email_text_content(self, msg):
        """Helper to extract plain text from email message object."""
        text_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))
                # Prefer text/plain, not an attachment
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        text_content += payload.decode(charset, errors='replace')
                    except Exception as e:
                        print(f"Error decoding email part: {e}")
                        # Fallback if decode fails with charset, try without strict errors
                        try:
                            text_content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass # Give up on this part
                    # break # Taking only the first plain text part, consider concatenating if needed
        else: # Not multipart
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                text_content = payload.decode(charset, errors='replace')
            except Exception as e:
                print(f"Error decoding non-multipart email payload: {e}")
                try:
                    text_content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass # Give up
        return text_content.strip()

    def _detect_format_and_extract_content(self, data, source_identifier):
        content = ""
        input_format = "Unknown"

        if isinstance(data, str) and os.path.exists(data):  # It's a file path
            file_path = data
            _, ext = os.path.splitext(file_path.lower())

            if ext == ".json":
                input_format = "JSON"
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    return input_format, content
                except json.JSONDecodeError as e:
                    err_msg = f"Invalid JSON content in file {file_path}: {e}. Please ensure the file contains valid JSON."
                    print(err_msg)
                    return "Error", err_msg
                except Exception as e:
                    err_msg = f"Error reading JSON file {file_path}: {e}"
                    print(err_msg)
                    return "Error", err_msg

            elif ext == ".pdf":
                input_format = "PDF"
                try:
                    pdf_text_content = ""
                    doc = fitz.open(file_path)
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        pdf_text_content += page.get_text("text") # "text" for plain text extraction
                    doc.close()
                    content = pdf_text_content.strip()
                    if not content:
                        print(f"Warning: PDF file {file_path} yielded no text content. It might be image-based or scanned.")
                        # Optionally, could return "Error" or a specific format like "PDF_NoText"
                except Exception as e:
                    err_msg = f"Error reading PDF file {file_path}: {e}"
                    print(err_msg)
                    return "Error", err_msg

            elif ext == ".eml":
                input_format = "Email"
                try:
                    with open(file_path, 'rb') as f: # EML files should be read as bytes
                        msg = BytesParser(policy=default_policy).parse(f)
                    
                    email_text = self._get_email_text_content(msg)
                    headers = {k: v for k, v in msg.items()}
                    content = {"text": email_text, "headers": headers, "raw_eml_path": file_path}
                    if not email_text:
                         print(f"Warning: EML file {file_path} yielded no plain text body.")
                except Exception as e:
                    err_msg = f"Error reading EML file {file_path}: {e}"
                    print(err_msg)
                    return "Error", err_msg

            elif ext == ".txt": # Assume .txt could be email text or generic text
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_text = f.read()
                    # Heuristic to guess if it's an email
                    if re.search(r"^\s*From\s*:", raw_text, re.IGNORECASE | re.MULTILINE) and \
                       re.search(r"^\s*Subject\s*:", raw_text, re.IGNORECASE | re.MULTILINE):
                        input_format = "Email" # Tentative
                        # Basic header parsing (very naive)
                        headers = {}
                        for line in raw_text.splitlines()[:15]: # Check first few lines
                            if ":" in line:
                                k, v = line.split(":", 1)
                                headers[k.strip()] = v.strip()
                        content = {"text": raw_text, "headers": headers, "raw_eml_path": None}
                    else:
                        input_format = "Text"
                        content = raw_text
                except Exception as e:
                    err_msg = f"Error reading Text file {file_path}: {e}"
                    print(err_msg)
                    return "Error", err_msg
            else:
                input_format = "UnknownFile"
                err_msg = f"Unsupported file extension: {ext} for file {source_identifier}"
                print(err_msg)
                return "Error", err_msg

        elif isinstance(data, str):  # Raw text input
            try:
                # Try to parse as JSON first (more specific)
                parsed_json = json.loads(data)
                input_format = "JSON"
                content = parsed_json
                return input_format, content
            except json.JSONDecodeError:
                # Not JSON, assume text (could be email or other)
                raw_text = data
                if re.search(r"^\s*From\s*:", raw_text, re.IGNORECASE | re.MULTILINE) and \
                   re.search(r"^\s*Subject\s*:", raw_text, re.IGNORECASE | re.MULTILINE):
                    input_format = "Email"
                    headers = {} # Minimal header parsing for raw text
                    for line in raw_text.splitlines()[:15]:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            headers[k.strip()] = v.strip()
                    content = {"text": raw_text, "headers": headers, "raw_eml_path": None}
                else:
                    input_format = "Text"
                    content = raw_text
        elif isinstance(data, dict): # Already parsed JSON, pass through
            input_format = "JSON"
            content = data
        else:
            err_msg = f"Unsupported input data type: {type(data)} for source {source_identifier}"
            print(err_msg)
            return "Error", err_msg

        if not content and input_format not in ["JSON", "Error"]: # JSON content can be an empty dict/list legitimately
            # If content is empty after processing (e.g. empty PDF/TXT, or EML with no text part)
            print(f"Warning: No processable content extracted for {source_identifier} (format: {input_format}).")
            # Depending on policy, this could be an error or just proceed with empty content for classification
            # For now, let it proceed, intent classification might still work if format is known
        
        return input_format, content

    def _classify_intent(self, text_content_for_llm):
        if not text_content_for_llm or len(text_content_for_llm.strip()) < 10:
            print("Content too short or empty for LLM intent classification.")
            return {"intent": "Other", "reasoning": "Content too short or empty for meaningful classification."}

        # Truncate for LLM context window
        max_len = 3500 # Adjusted for typical context windows, might need tuning
        truncated_content = (text_content_for_llm[:max_len] + '...') if len(text_content_for_llm) > max_len else text_content_for_llm

        prompt = f"""
        Analyze the following text and classify its primary intent.
        Choose one intent from this list: {', '.join(SUPPORTED_INTENTS)}.
        Provide a brief reasoning for your classification (1-2 sentences).

        Text:
        \"\"\"
        {truncated_content}
        \"\"\"

        Respond ONLY in valid JSON format with keys "intent" and "reasoning".
        Example: {{"intent": "RFQ", "reasoning": "The text mentions requesting a quote for specific items."}}
        """
        system_message = "You are an expert text classification assistant. Your response MUST be a single, valid JSON object and nothing else. Choose an intent from the provided list."
        response = get_llm_json_response(prompt, system_message=system_message)

        if response and "intent" in response and "reasoning" in response:
            if response["intent"] not in SUPPORTED_INTENTS:
                print(f"LLM proposed an intent '{response['intent']}' not in the supported list. Reclassifying as 'Other'.")
                response["intent"] = "Other"
                response["reasoning"] += " (Original intent not in supported list, reclassified as Other)"
            return response
        else:
            print(f"Classifier LLM failed or gave invalid/incomplete JSON response: {response}")
            return {"intent": "Other", "reasoning": "Failed to get a valid classification from LLM or response was malformed."}

    def process(self, data, conversation_id, source_identifier, previous_context=None):
        self.shared_memory.log_event(
            conversation_id=conversation_id,
            agent_name=self.agent_name,
            status="Received",
            source_identifier=source_identifier,
            details={"input_data_type": str(type(data))}
        )

        input_format, content_to_process = self._detect_format_and_extract_content(data, source_identifier)

        if input_format == "Error":
            self.shared_memory.log_event(
                conversation_id=conversation_id, agent_name=self.agent_name, status="Error",
                source_identifier=source_identifier, input_format_classified="ErrorDetection",
                error_message=content_to_process  # content_to_process holds error message here
            )
            print(f"Error during format detection/content extraction for {source_identifier}: {content_to_process}")
            return None

        # Prepare text for LLM intent classification
        text_for_llm = ""
        if input_format == "JSON":
            # For JSON, stringify a relevant part or summary.
            # A more sophisticated approach might involve selecting key fields.
            try:
                text_for_llm = json.dumps(content_to_process, indent=2)
            except TypeError: # If content_to_process is not serializable (shouldn't happen if it's from json.load)
                 text_for_llm = str(content_to_process)
        elif input_format == "Email": # content_to_process is a dict {"text": ..., "headers": ...}
            text_for_llm = content_to_process.get("text", "")
        else:  # PDF, Text - content_to_process is the extracted string
            text_for_llm = content_to_process if isinstance(content_to_process, str) else ""

        classification_result = self._classify_intent(text_for_llm)
        intent = classification_result.get("intent", "Other")
        reasoning = classification_result.get("reasoning", "No reasoning provided or classification failed.")

        self.shared_memory.log_event(
            conversation_id=conversation_id, agent_name=self.agent_name, status="Classified",
            source_identifier=source_identifier, input_format_classified=input_format,
            intent_classified=intent, details={"classification_reasoning": reasoning}
        )
        print(f"[{conversation_id}] Classified '{source_identifier}' as Format: {input_format}, Intent: {intent}")

        # Routing
        routed_to_agent_name = None
        if input_format == "JSON":
            routed_to_agent_name = self.json_agent.agent_name
            self.json_agent.process(content_to_process, conversation_id, source_identifier,
                                    previous_context={"intent": intent, "format": input_format})
        elif input_format == "Email": # Directly from EML or heuristically identified TXT
            routed_to_agent_name = self.email_agent.agent_name
            self.email_agent.process(content_to_process, conversation_id, source_identifier,
                                     previous_context={"intent": intent, "format": input_format})
        elif input_format in ["PDF", "Text"]: # Generic text or PDF extracted text
            email_like_intents = ["RFQ", "Complaint", "General Inquiry", "Invoice",
                                  "Order Confirmation", "Job Application", "Feedback"]
            if intent in email_like_intents or intent == "Other": # Route 'Other' to EmailAgent for human review potential
                print(f"[{conversation_id}] Routing {input_format} content (Intent: '{intent}') to Email Agent for text processing.")
                
                # Ensure content_to_process is the text string for PDF/Text
                final_text_payload = text_for_llm # Use the same text used for classification

                email_like_data_for_agent = {
                    "text": final_text_payload,
                    "headers": {}, # No true email headers
                    "raw_eml_path": source_identifier if input_format == "PDF" and source_identifier.endswith(".pdf") else None
                }
                routed_to_agent_name = self.email_agent.agent_name
                self.email_agent.process(email_like_data_for_agent, conversation_id, source_identifier,
                                        previous_context={"intent": intent, "format": input_format})
            else:
                details = {"message": f"No specific agent route for {input_format} with non-email-like intent '{intent}'. Processing ends here."}
                print(f"[{conversation_id}] {details['message']}")
                self.shared_memory.log_event(
                    conversation_id=conversation_id, agent_name=self.agent_name, status="NoRoute",
                    source_identifier=source_identifier, input_format_classified=input_format,
                    intent_classified=intent, details=details
                )
        else: # "UnknownFile" or other unhandled
            details = {"message": f"Unhandled format: '{input_format}'. Processing ends here."}
            print(f"[{conversation_id}] {details['message']}")
            self.shared_memory.log_event(
                conversation_id=conversation_id, agent_name=self.agent_name, status="NoRouteUnhandledFormat",
                source_identifier=source_identifier, input_format_classified=input_format,
                intent_classified=intent, details=details
            )

        if routed_to_agent_name:
            # This logging of routing is a bit redundant if the next agent logs "Received"
            # But can be useful for confirming routing decision by Classifier
            # print(f"[{conversation_id}] Routed to {routed_to_agent_name}")
            pass 

        return {"format": input_format, "intent": intent, "classified_content_summary": text_for_llm[:100]+"..."}
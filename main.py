# main.py
import os
import uuid
import json # For printing conversation history example
from core.shared_memory import SharedMemory
from agents.json_agent import JSONAgent
from agents.email_agent import EmailAgent
from agents.classifier_agent import ClassifierAgent
from config import OPENROUTER_API_KEY # Changed from OPENAI_API_KEY

def process_input(classifier_agent, input_path_or_data, source_name=None):
    # ... (rest of the function is the same)
    conversation_id = str(uuid.uuid4())
    if source_name is None:
        if isinstance(input_path_or_data, str) and os.path.exists(input_path_or_data):
            source_name = os.path.basename(input_path_or_data)
        elif isinstance(input_path_or_data, str):
            source_name = f"raw_text_input_{conversation_id[:8]}"
        elif isinstance(input_path_or_data, dict):
            source_name = f"json_dict_input_{conversation_id[:8]}"
        else:
            source_name = f"unknown_input_{conversation_id[:8]}"

    print(f"\n--- Processing {source_name} (Conv ID: {conversation_id}) ---")
    classifier_agent.process(input_path_or_data, conversation_id, source_identifier=source_name)
    return conversation_id


if __name__ == "__main__":
    if not OPENROUTER_API_KEY: # Changed this check
        print("Error: OPENROUTER_API_KEY is not set in the .env file or environment variables.")
        print("Please set it and try again. You can get a key from https://openrouter.ai")
        exit(1)

    # Initialize Shared Memory
    shared_mem = SharedMemory(log_file_path="outputs/processing_log.jsonl")

    # Initialize Agents (injecting dependencies)
    json_agent_instance = JSONAgent(shared_memory=shared_mem)
    email_agent_instance = EmailAgent(shared_memory=shared_mem)
    classifier_agent_instance = ClassifierAgent(
        shared_memory=shared_mem,
        json_agent=json_agent_instance,
        email_agent=email_agent_instance
    )

    # --- Example Inputs ---
    sample_inputs_dir = "inputs"
    if not os.path.exists(sample_inputs_dir):
        os.makedirs(sample_inputs_dir)
        print(f"Created '{sample_inputs_dir}' directory. Please add sample files there.")

    # 1. Process a JSON file (RFQ example)
    sample_rfq_json_path = os.path.join(sample_inputs_dir, "sample_rfq.json")
    if os.path.exists(sample_rfq_json_path):
        conv_id_rfq = process_input(classifier_agent_instance, sample_rfq_json_path)
    else:
        print(f"Sample file not found: {sample_rfq_json_path}. Create it with content like:" )
        print("""
        {
          "rfq_id": "RFQ12345",
          "customer_name": "Acme Corp",
          "items": [
            {"product_id": "PROD001", "quantity": 100},
            {"product_id": "PROD002", "quantity": 50}
          ],
          "due_date": "2024-12-31",
          "contact_email": "purchasing@acme.com"
        }
        """)


    # 2. Process a PDF file (Invoice example)
    sample_invoice_pdf_path = os.path.join(sample_inputs_dir, "sample_invoice.pdf")
    if os.path.exists(sample_invoice_pdf_path):
        conv_id_invoice = process_input(classifier_agent_instance, sample_invoice_pdf_path)
    else:
        print(f"Sample file not found: {sample_invoice_pdf_path}. Please add a sample PDF invoice.")


    # 3. Process an EML file (Complaint example)
    sample_complaint_eml_path = os.path.join(sample_inputs_dir, "sample_complaint.eml")
    if os.path.exists(sample_complaint_eml_path):
        conv_id_complaint = process_input(classifier_agent_instance, sample_complaint_eml_path)
    else:
        print(f"Sample file not found: {sample_complaint_eml_path}. Please add a sample .eml file.")
        print("You can save an email from your client as .eml")


    # 4. Process raw email text (General Inquiry example)
    sample_general_inquiry_txt_path = os.path.join(sample_inputs_dir, "sample_general_inquiry.txt")
    email_text_content_default = """
    From: interested_party@example.com
    To: sales@mycompany.com
    Subject: Question about your services

    Hi team,

    I was browsing your website and had a few questions about the enterprise plan for your software.
    Could someone reach out to me to discuss pricing and features? My direct line is 555-123-4567.

    Thanks,
    Alex
    """
    if os.path.exists(sample_general_inquiry_txt_path):
        with open(sample_general_inquiry_txt_path, 'r') as f:
            email_text_content_from_file = f.read()
        conv_id_inquiry = process_input(classifier_agent_instance, email_text_content_from_file, source_name="sample_general_inquiry.txt")
    else:
        print(f"Sample file not found: {sample_general_inquiry_txt_path}. Using inline text and creating the file.")
        with open(sample_general_inquiry_txt_path, 'w') as f:
            f.write(email_text_content_default)
        print(f"Created {sample_general_inquiry_txt_path} with sample content.")
        conv_id_inquiry = process_input(classifier_agent_instance, email_text_content_default, source_name="sample_general_inquiry.txt_inline")


    # 5. Process a raw JSON string
    json_string_data = '{"order_id": "ORD987", "customer_id": "CUST003", "status": "Pending", "items": [{"sku": "SKU00X", "qty": 2}], "comment": "This is an order for some items, please process quickly."}'
    conv_id_json_str = process_input(classifier_agent_instance, json_string_data, source_name="raw_json_string")


    print("\n--- All Processing Complete ---")
    print(f"Check 'outputs/processing_log.jsonl' for detailed logs.")

    # Example: Print summary of one conversation from memory
    if 'conv_id_rfq' in locals() and shared_mem.get_conversation_history(conv_id_rfq):
        print(f"\n--- Summary for RFQ Conversation (ID: {conv_id_rfq}) ---")
        for event in shared_mem.get_conversation_history(conv_id_rfq):
            print(f"  Agent: {event['agent_name']}, Status: {event['status']}, Intent: {event.get('intent_classified', 'N/A')}")
            if event['extracted_data']:
                # Truncate long extracted data for display
                extracted_str = json.dumps(event['extracted_data'])
                print(f"    Extracted: {extracted_str[:150]}{'...' if len(extracted_str) > 150 else ''}")
            if event['details'] and event['details'].get('anomalies'):
                print(f"    Anomalies: {event['details']['anomalies']}")
            if event.get('error_message'):
                print(f"    Error: {event['error_message']}")
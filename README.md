# Multi-Agent Document Processing System

This project implements a multi-agent AI system designed to accept input documents in PDF, JSON, or Email (text/EML) format. It classifies the document's format and its primary intent, then routes it to the appropriate specialized agent for further processing. The system maintains a shared context (via a logging mechanism) to enable traceability and chaining of operations.

## System Overview

The system is orchestrated via a central **Classifier Agent** and comprises the following key components:

1.  **Classifier Agent**:
    *   **Input**: Raw file path (PDF, JSON, EML, TXT) or raw string data (JSON or Email text).
    *   **Functionality**:
        *   Detects the input format (PDF, JSON, Email, Text).
        *   Extracts text content from PDF and Email files.
        *   Utilizes a Large Language Model (LLM) via OpenRouter to classify the intent of the content (e.g., Invoice, RFQ, Complaint, General Inquiry).
        *   Routes the processed data and classification results to the appropriate specialized agent.
        *   Logs all its actions and findings.

2.  **JSON Agent**:
    *   **Input**: Structured JSON payloads (typically routed from the Classifier Agent).
    *   **Functionality**:
        *   Validates the incoming JSON against a predefined target schema if one exists for the classified intent (e.g., an RFQ schema).
        *   Extracts fields according to the schema.
        *   Flags anomalies such as missing required fields or fields not present in the schema.
        *   If no schema is defined for the intent, it passes the data through and logs this.
        *   Logs its actions and results.

3.  **Email Agent**:
    *   **Input**: Email content (parsed from EML files, raw text identified as email, or text extracted from PDFs whose intent is deemed email-like).
    *   **Functionality**:
        *   Extracts sender and subject from headers (if available).
        *   Uses an LLM to determine urgency, generate a concise summary, and list key entities/action items suitable for CRM-style usage.
        *   Logs its actions and the extracted CRM-formatted data.

4.  **Shared Memory Module (Lightweight Logging)**:
    *   **Implementation**: An in-memory dictionary, with each processed input having a unique `conversation_id`. All events related to that input are logged under this ID.
    *   **Persistence**: Events are also written append-only to a JSON Lines (`.jsonl`) file (`outputs/processing_log.jsonl`) for persistent logging and review.
    *   **Logged Data**: Includes `event_id`, `conversation_id`, `timestamp`, `agent_name`, processing `status`, `source_identifier`, classified `format` and `intent`, `extracted_data`, `details` (like anomalies or reasoning), and any `error_message`.
    *   **Purpose**: Enables traceability of operations across agents for a given input.

## Example Flow

1.  User provides an input (e.g., `sample_rfq.json`).
2.  `main.py` script initiates processing with a unique `conversation_id`.
3.  **Classifier Agent** receives the input:
    *   Detects format as "JSON".
    *   Sends content to LLM for intent classification. LLM returns "RFQ".
    *   Logs "Received" and "Classified" events.
    *   Routes the JSON data and "RFQ" intent to the **JSON Agent**.
4.  **JSON Agent** receives the data:
    *   Validates against `RFQ_TARGET_SCHEMA`.
    *   Extracts fields. Finds no anomalies (if data matches schema).
    *   Logs "Processed" event with extracted data.
5.  Processing for this input concludes. All steps are logged in `outputs/processing_log.jsonl` under the same `conversation_id`.

## Tech Stack

*   **Python 3.8+**
*   **OpenRouter API**: For LLM access. Tested with models like `tngtech/deepseek-r1t-chimera:free`, `mistralai/mistral-7b-instruct:free`, and `google/gemini-flash-1.5`. The chosen model can be configured via an environment variable.
*   **`openai` Python Library (v1.x.x)**: Used as the client to interface with the OpenRouter API.
*   **PyMuPDF (fitz)**: For robust PDF text extraction.
*   **Standard Python Libraries**: `json`, `os`, `re`, `email`, `uuid`, `datetime`.
*   **`python-dotenv`**: For managing environment variables (like API keys).

## Folder Structure

```
multi_agent_doc_processor/
├── agents/                 # Agent implementations
│   ├── __init__.py
│   ├── base_agent.py       # Abstract base class for agents
│   ├── classifier_agent.py
│   ├── json_agent.py
│   └── email_agent.py
├── core/                   # Core utilities
│   ├── __init__.py
│   ├── shared_memory.py    # Logging and shared context mechanism
│   └── llm_utils.py        # LLM interaction and robust JSON parsing
├── inputs/                 # Sample input files
│   ├── sample_complaint.eml
│   ├── sample_general_inquiry.txt
│   ├── sample_invoice.pdf  # User must provide a real invoice PDF
│   └── sample_rfq.json
├── outputs/                # Logs and other outputs
│   └── processing_log.jsonl # Persistent event log
├── .env                    # For API keys and LLM model choice (GITIGNORED)
├── .gitignore
├── config.py               # System configuration (supported intents, JSON schemas)
├── main.py                 # Main orchestration script
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone Multi-Agent-Document-Processing-System
    cd Multi-Agent-Document-Processing-System
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up OpenRouter API Key and LLM Choice:**
    *   Create a `.env` file in the project root directory (`multi_agent_doc_processor/.env`).
    *   Add your OpenRouter API key:
        ```env
        OPENROUTER_API_KEY="sk-or-v1-your_actual_openrouter_api_key_here"
        ```
    *   Optionally, specify the LLM model to use (it will override the default in `config.py`):
        ```env
        # Example:
        # OPENROUTER_LLM_MODEL="mistralai/mistral-7b-instruct:free"
        # OPENROUTER_LLM_MODEL="tngtech/deepseek-r1t-chimera:free"
        # OPENROUTER_LLM_MODEL="google/gemini-flash-1.5"
        ```
    *   **Important**: Ensure the `.env` file is listed in your `.gitignore` file to prevent committing your API key.

5.  **Prepare Sample Input Files:**
    *   The `inputs/` directory should contain sample files for testing. Examples are provided for `.json`, `.eml`, and `.txt`.
    *   **You must provide your own `sample_invoice.pdf`**. It should be a text-based PDF (not scanned/image-only) representing a typical invoice.

## How to Run

Execute the main orchestration script from the project root directory:

```bash
python main.py
```

The script will:
1.  Initialize agents and the shared memory/logging system.
2.  Process each sample input defined in `main.py` (from `inputs/` directory and inline data).
3.  Print verbose `DEBUG` messages to the console showing LLM call attempts, responses, and JSON parsing steps.
4.  Print agent processing messages to the console.
5.  Log detailed, structured events for each step into `outputs/processing_log.jsonl`.
6.  Print a summary of processing for one of the conversations at the end.

## Key Features Demonstrated

*   **Format Detection**: Handles JSON, PDF, EML, and TXT inputs.
*   **Intent Classification**: Uses LLMs to determine the purpose of the document from a configurable list of intents.
*   **Specialized Agent Routing**: Directs documents to agents tailored for their format and/or content.
*   **JSON Schema Validation**: `JSONAgent` validates inputs against target schemas where defined.
*   **Email Data Extraction**: `EmailAgent` extracts CRM-relevant information like summary, urgency, and key entities.
*   **Robust LLM Interaction**: `llm_utils.py` includes logic to handle chatty LLMs and extract JSON from their responses, including preambles or markdown wrapping.
*   **Traceability**: Each input is assigned a `conversation_id`, and all processing steps by different agents are logged with this ID in `outputs/processing_log.jsonl`.
*   **Error Handling**: Gracefully handles LLM API errors (like rate limits) and JSON parsing issues, logging them and allowing the system to continue with other inputs or fall back to default classifications.

## Sample Output Log (`outputs/processing_log.jsonl`)

The `processing_log.jsonl` file will contain entries like this for each event:

```json
{"event_id": "...", "conversation_id": "5f2c9963-2be0-43b8-a899-740bdca4cd19", "timestamp": "...", "agent_name": "ClassifierAgent", "status": "Classified", "source_identifier": "sample_rfq.json", "input_format_classified": "JSON", "intent_classified": "RFQ", "extracted_data": {}, "details": {"classification_reasoning": "The text is a structured request for a quote (RFQ) with product details, quantities, and delivery requirements."}, "error_message": null}
{"event_id": "...", "conversation_id": "5f2c9963-2be0-43b8-a899-740bdca4cd19", "timestamp": "...", "agent_name": "JSONAgent", "status": "Processed", "source_identifier": "sample_rfq.json", "input_format_classified": "JSON", "intent_classified": "RFQ", "extracted_data": {"rfq_id": "RFQ12345", ...}, "details": {"anomalies": []}, "error_message": null}
{"event_id": "...", "conversation_id": "1004cbb0-2041-4aa3-80c3-ad390a1cc1f9", "timestamp": "...", "agent_name": "EmailAgent", "status": "Processed", "source_identifier": "sample_complaint.eml", "input_format_classified": "Email", "intent_classified": "Complaint", "extracted_data": {"sender_email": "customer.jane.doe@emailprovider.net", "subject": "Urgent: Complaint Regarding Order #ORD789012 - Damaged Item", "intent_classified": "Complaint", "urgency": "High", ...}, "details": {"original_headers": {...}}, "error_message": null}
```
(Console output screenshots showing the DEBUG messages and agent processing can also be very illustrative for a demo).

## Troubleshooting LLM Access

*   **Rate Limits**: Free tiers on OpenRouter can have strict daily or per-minute rate limits. If you see `RateLimitError` in the console, you may need to:
    *   Wait for the limit to reset.
    *   Add credits to your OpenRouter account (recommended for smoother development).
    *   Configure your own provider API keys in OpenRouter.
*   **Model Choice**: Some models are "chattier" or less reliable at strict JSON output. The current `llm_utils.py` is designed to be robust, but experimenting with different models available on OpenRouter (set via `OPENROUTER_LLM_MODEL` in `.env`) can be useful. Models like `mistralai/mistral-7b-instruct:free` or `tngtech/deepseek-r1t-chimera:free` have shown good results when accessible.

## Future Development Ideas

*   Implement more sophisticated context passing beyond just the initial classification (e.g., allowing agents to query previous extracted fields for the same `conversation_id`).
*   Expand the number of specialized agents (e.g., a dedicated PDF table extraction agent).
*   Add more target schemas for `JSONAgent` for different intents.
*   Integrate with actual data sources/sinks (e.g., read from an email inbox, write to a CRM API).
*   Implement a more persistent Shared Memory solution (e.g., SQLite or Redis) if inter-process communication or longer-term state is needed beyond simple logging.
*   Develop a web API or UI for submitting documents.
 
 

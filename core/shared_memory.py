# core/shared_memory.py
import datetime
import uuid
import json # For logging to file

class SharedMemory:
    def __init__(self, log_file_path="outputs/processing_log.jsonl"):
        self._memory = {}  # In-memory store: {conversation_id: [event1, event2,...]}
        self.log_file_path = log_file_path
        # Ensure outputs directory exists
        import os
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)


    def _generate_event_id(self):
        return str(uuid.uuid4())

    def log_event(self, conversation_id, agent_name, status, source_identifier=None,
                  input_format_classified=None, intent_classified=None,
                  extracted_data=None, details=None, error_message=None):
        if not conversation_id:
            raise ValueError("conversation_id is required to log an event.")

        event = {
            "event_id": self._generate_event_id(),
            "conversation_id": conversation_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "agent_name": agent_name,
            "status": status, # e.g., "Received", "Classified", "Processed", "Error"
            "source_identifier": source_identifier,
            "input_format_classified": input_format_classified,
            "intent_classified": intent_classified,
            "extracted_data": extracted_data if extracted_data else {},
            "details": details if details else {},
            "error_message": error_message
        }

        if conversation_id not in self._memory:
            self._memory[conversation_id] = []
        self._memory[conversation_id].append(event)

        # Append to log file
        try:
            with open(self.log_file_path, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            print(f"Error writing to log file {self.log_file_path}: {e}")

        return event

    def get_conversation_history(self, conversation_id):
        return self._memory.get(conversation_id, [])

    def get_last_event_for_conversation(self, conversation_id):
        history = self.get_conversation_history(conversation_id)
        return history[-1] if history else None

    def get_all_conversations(self):
        return self._memory 

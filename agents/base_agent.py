# agents/base_agent.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self, agent_name, shared_memory):
        self.agent_name = agent_name
        self.shared_memory = shared_memory

    @abstractmethod
    def process(self, data, conversation_id, source_identifier, previous_context=None):
        """
        Process the given data.
        :param data: The input data for the agent.
        :param conversation_id: The ID for the current conversation/thread.
        :param source_identifier: Identifier for the original input (e.g., filename).
        :param previous_context: Context from previous agent, if any.
        :return: Result of processing, or None if handled via shared_memory.
        """
        pass 

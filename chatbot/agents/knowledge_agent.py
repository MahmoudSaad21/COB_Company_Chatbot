from langchain_google_genai import ChatGoogleGenerativeAI
from ..knowledge_base.manager import KnowledgeBaseManager
from ..main_agent import MainOrchestratorAgent
from ..tools.knowledge_tools import KnowledgeRetrievalTool
from langchain_core.messages import HumanMessage
import re


class KnowledgeAgent:
    """Agent specialized in handling product and company knowledge queries"""

    def __init__(self, llm: ChatGoogleGenerativeAI, kb_manager: KnowledgeBaseManager, orchestrator: MainOrchestratorAgent):
        self.llm = llm
        self.kb_manager = kb_manager
        self.orchestrator = orchestrator
        self.retrieval_tool = KnowledgeRetrievalTool(kb_manager=kb_manager)

    def handle_query(self, query: str) -> str:
        """Handle knowledge queries using conversation context"""
        # Build context from history
        context_str = self.orchestrator.get_conversation_context()

        # Retrieve relevant documents
        context = self.retrieval_tool._run(query)

        # Generate response with context
        prompt = f"""
        Conversation Context:
        {context_str}

        Current Question: {query}

        Knowledge Context: {context}

        Provide a helpful, informative response based on the conversation context and knowledge.
        If information is not available, suggest alternatives.
        Respond conversationally in 2-3 sentences.
        """

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

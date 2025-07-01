import json
from langchain.tools import BaseTool
from pydantic import Field
from ..knowledge_base.manager import KnowledgeBaseManager

class KnowledgeRetrievalTool(BaseTool):
    name: str = "knowledge_retriever"
    description: str = "Retrieve information from COB Company's knowledge base"
    kb_manager: KnowledgeBaseManager = Field(...)

    def _run(self, query: str) -> str:
        try:
            # Retrieve relevant documents
            docs = self.kb_manager.query(query)
            if not docs:
                return "No relevant information found in the knowledge base."

            # Format results
            results = []
            for doc in docs:
                content = doc.page_content
                # Truncate long content
                if len(content) > 500:
                    content = content[:497] + "..."
                results.append({
                    "source": doc.metadata.get("source", "Unknown"),
                    "content": content
                })

            return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error retrieving knowledge: {str(e)}"

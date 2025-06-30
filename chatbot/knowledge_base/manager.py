import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from typing import List
from langchain.schema import Document

# Knowledge Base Manager with RAG
class KnowledgeBaseManager:
    def __init__(self, path: str):
        self.path = path
        self.vector_store = self._init_vector_store()

    def _init_vector_store(self):
        """Initialize FAISS vector store from knowledge base documents"""
        if not os.path.exists(self.path):
            os.makedirs(self.path)
            # Create sample knowledge files
            self._create_sample_knowledge()

        loader = DirectoryLoader(
            self.path,
            glob="**/*.txt",
            loader_cls=TextLoader,
            show_progress=False
        )
        docs = loader.load()

        if not docs:
            return None

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        documents = text_splitter.split_documents(docs)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        return FAISS.from_documents(documents, embeddings)

    def _create_sample_knowledge(self):
        """Create sample knowledge base files"""
        sample_files = {
            "products.txt": """
            COB Company Products:
            - Analytics Pro: Advanced data analytics platform with real-time dashboards and predictive capabilities.
            - Health Monitor: Wearable device that tracks vital signs and health metrics 24/7.
            - Cloud Secure: Enterprise-grade cloud security solution with threat detection and prevention.
            - AI Assistant: Conversational AI system for customer service and support automation.

            Pricing:
            - Analytics Pro: $99/month per user
            - Health Monitor: $199 one-time purchase
            - Cloud Secure: Custom pricing based on infrastructure size
            - AI Assistant: $499/month for basic plan

            Support:
            - Email: support@cobcompany.com
            - Phone: 1-800-COB-HELP
            - Hours: Mon-Fri 9AM-6PM EST
            """,

            "policies.txt": """
            COB Company Policies:
            - Return Policy: 30-day money-back guarantee on all products.
            - Warranty: Hardware products come with 1-year limited warranty.
            - Data Privacy: We comply with GDPR and CCPA regulations. All customer data is encrypted.
            - Service Level Agreement (SLA): 99.9% uptime guarantee for cloud services.

            Appointment Cancellation:
            - Clinical appointments: Cancel at least 24 hours in advance to avoid fees.
            - Marketing meetings: Cancel at least 2 hours in advance.
            """
        }

        for filename, content in sample_files.items():
            with open(os.path.join(self.path, filename), "w") as f:
                f.write(content)

    def query(self, question: str, k: int = 4) -> List[Document]:
        """Retrieve relevant documents for a query"""
        if not self.vector_store:
            print("No vector store available.")
            return []
        return self.vector_store.similarity_search(question, k=k)
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional, Tuple, Any, Sequence

# Langchain specific imports
from langchain_openai import ChatOpenAI # Import the OpenAI chat model wrapper
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# --- Placeholder Function for External Vector Index Querying ---
# (Remains the same placeholder logic - This is LLM independent)
def query_vector_index(index_path: str, query: str, k: int = 3) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Placeholder: Queries a local FAISS index.
    Returns a list of (text_chunk, metadata) tuples.
    """
    print(f"[DEBUG] Querying index '{index_path}' with: '{query}' (k={k})")
    if not os.path.exists(index_path):
         print(f"[WARN] Index path '{index_path}' does not exist. Returning empty results.")
         return []
    # Simulate finding relevant chunks
    return [
        (f"Placeholder relevant text chunk 1 about '{query}' from {os.path.basename(index_path)}", {"source": os.path.basename(index_path), "page": 1}),
        (f"Placeholder relevant text chunk 2 about '{query}' from {os.path.basename(index_path)}", {"source": os.path.basename(index_path), "page": 5}),
        (f"Placeholder relevant text chunk 3 about '{query}' from {os.path.basename(index_path)}", {"source": os.path.basename(index_path), "page": 8}),
    ][:k]

# --- The Assistant Chatbot Class (using Langchain and OpenAI) ---

class OpenAIChatbotAssistant: # Renamed class for clarity
    """
    An assistant chatbot using Langchain with OpenAI (GPT-4o-mini) to help users
    understand accounting standards and merger agreements, incorporating RAG
    and chat history.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"): # Default to gpt-4o-mini
        """
        Initializes the chatbot assistant using Langchain and OpenAI.

        Args:
            model_name (str): The OpenAI model identifier (e.g., "gpt-4o-mini").
        """
        load_dotenv()
        # Langchain's ChatOpenAI will look for OPENAI_API_KEY env var by default
        api_key = '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' #os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[WARN] OPENAI_API_KEY environment variable not set. Langchain/OpenAI library will try to find it.")
            # Depending on your setup, you might still need it explicitly.
            # raise ValueError("OPENAI_API_KEY environment variable not set.")

        # Initialize the Langchain Chat Model for OpenAI
        self.llm = ChatOpenAI(
            model=model_name,
            openai_api_key=api_key, # Pass explicitly if needed, otherwise relies on env var/config
            temperature=0.7 # Optional config, adjust as needed
        )

        # Context storage (remains the same)
        self.standard_index_path: Optional[str] = None
        self.agreement_index_path: Optional[str] = None
        self.standard_name: Optional[str] = None
        self.memo_template_structure: Optional[str] = None # Can be used in prompts if needed

        # System prompt text (remains the same conceptually)
        self.system_prompt_text = """
You are a helpful AI assistant specializing in accounting standards (ASC 805, IFRS 3) and legal agreements related to business combinations.
Your goal is to answer user questions clearly and accurately, referencing the provided context from standards or agreements when available.
Do NOT generate memo content directly. Focus on explaining concepts, finding specific information, and identifying relevant clauses or requirements based on user queries and the context provided to you.
If context is provided for a query, prioritize information from that context in your answer and cite the source (e.g., "According to the standard [page X]..." or "The agreement mentions on [page Y]...").
If no specific context is available or relevant, answer based on your general knowledge of the topic.
Keep your answers concise and focused on the user's question.
Use the chat history to understand the context of the conversation.
"""

        # Langchain Memory for managing chat history (remains the same)
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True # Return Message objects for the prompt template
        )

        # --- RAG Retrieval Function ---
        # (This function is LLM-agnostic and remains exactly the same)
        def retrieve_rag_context(input_data: Dict) -> str:
            user_message = input_data["input"] # Assumes input key is "input"
            print(f"[DEBUG] RAG: Retrieving context for: '{user_message[:50]}...'")
            rag_context_parts = []
            evidence_sources = []
            query_standard = False
            query_agreement = False
            l_user_message = user_message.lower()

            # Keyword checks
            if self.standard_name and self.standard_index_path and (self.standard_name.lower() in l_user_message or any(k in l_user_message for k in ["standard", "accounting", "rule", "guidance"])): query_standard = True
            if self.agreement_index_path and any(k in l_user_message for k in ["agreement", "contract", "clause", "party", "date", "amount"]): query_agreement = True

            if query_standard:
                standard_chunks = query_vector_index(self.standard_index_path, user_message)
                if standard_chunks:
                    rag_context_parts.append(f"\n--- Relevant Guidance from {self.standard_name} ---")
                    for text, meta in standard_chunks:
                        source_ref = f"[Source: {meta.get('source', self.standard_name)}, Page: {meta.get('page', 'N/A')}]"
                        rag_context_parts.append(f"{source_ref}\n{text}")
                        evidence_sources.append(meta)
            if query_agreement:
                agreement_chunks = query_vector_index(self.agreement_index_path, user_message)
                if agreement_chunks:
                     rag_context_parts.append("\n--- Relevant Information from Merger Agreement ---")
                     for text, meta in agreement_chunks:
                         source_ref = f"[Source: {meta.get('source', 'Agreement')}, Page: {meta.get('page', 'N/A')}]"
                         rag_context_parts.append(f"{source_ref}\n{text}")
                         evidence_sources.append(meta)

            if rag_context_parts:
                context_str = "\n".join(rag_context_parts)
                print(f"[DEBUG] RAG: Context retrieved (Sources: {len(evidence_sources)})")
                return context_str
            else:
                print("[DEBUG] RAG: No specific context retrieved.")
                return "No specific context documents were found for this query."


        # --- Langchain Prompt Template ---
        # (Remains exactly the same)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt_text),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Context:\n{context}\n\nQuestion: {input}")
        ])

        # --- Langchain Runnable Chain (LCEL) ---
        # (Remains exactly the same structure, just uses the OpenAI LLM now)
        self.chain = (
            RunnablePassthrough.assign(
                chat_history=RunnableLambda(self.memory.load_memory_variables) | RunnableLambda(lambda mem: mem.get('chat_history', [])),
            )
            | RunnablePassthrough.assign(
                context=retrieve_rag_context
            )
            | self.prompt
            | self.llm # Now this is the configured ChatOpenAI instance
            | StrOutputParser()
        )


    def clear_history(self):
        """Clears the chat history stored in Langchain memory."""
        self.memory.clear()
        print("[INFO] Langchain chat memory cleared.")

    def set_context(self, standard_name: Optional[str] = None, standard_index_path: Optional[str] = None, agreement_index_path: Optional[str] = None, memo_template_structure: Optional[str] = None):
        """Sets the context paths and standard name."""
        # (Remains exactly the same)
        if standard_name: self.standard_name = standard_name
        if standard_index_path: self.standard_index_path = standard_index_path
        if agreement_index_path: self.agreement_index_path = agreement_index_path
        if memo_template_structure: self.memo_template_structure = memo_template_structure
        print(f"[INFO] Context updated: Standard={self.standard_name}, Standard Index={self.standard_index_path}, Agreement Index={self.agreement_index_path}, Template Structure provided={'Yes' if self.memo_template_structure else 'No'}")

    def get_history(self) -> Optional[List[Dict]]:
         """ Retrieves the chat history from Langchain memory. """
         # (Remains exactly the same)
         try:
             memory_vars = self.memory.load_memory_variables({})
             history_messages: Sequence[BaseMessage] = memory_vars.get('chat_history', [])
             return [
                 {'role': 'human' if isinstance(m, HumanMessage) else 'ai', 'text': m.content}
                 for m in history_messages
             ]
         except Exception as e:
             print(f"[ERROR] Could not retrieve history from memory: {e}")
             return None


    def send_chat_message(self, user_message: str) -> str:
        """
        Sends a user message using the Langchain chain, automatically handling
        RAG, history, and interaction with the OpenAI model.

        Args:
            user_message (str): The user's message/question.

        Returns:
            str: The chatbot assistant's response.
        """
        # (Remains exactly the same logic)
        print(f"[DEBUG] Invoking Langchain chain (OpenAI) for: '{user_message[:50]}...'")
        try:
            inputs = {"input": user_message}
            response = self.chain.invoke(inputs)
            self.memory.save_context(inputs, {"output": response})
            print("[DEBUG] Langchain chain invocation complete.")
            return response

        except Exception as e:
            print(f"[ERROR] Langchain chain invocation failed: {e}")
            # Handle potential OpenAI API errors (e.g., rate limits, auth issues)
            # You might import specific exceptions from openai.error if needed
            return f"[ERROR] Failed to get response via Langchain/OpenAI: {e}"

# Example Usage (using the new class name and ensuring OPENAI_API_KEY is set)
if __name__ == '__main__':
    # Ensure .env file has OPENAI_API_KEY=your_key
    # You might need to explicitly pass the model if you didn't want the default
    # chatbot = OpenAIChatbotAssistant(model_name="gpt-4o-mini")
    chatbot = OpenAIChatbotAssistant() # Uses default gpt-4o-mini

    # --- Simulate setting context ---
    DUMMY_STANDARD_INDEX = "./faiss_index_asc805"
    DUMMY_AGREEMENT_INDEX = "./faiss_index_merger_agreement"
    os.makedirs(DUMMY_STANDARD_INDEX, exist_ok=True)
    os.makedirs(DUMMY_AGREEMENT_INDEX, exist_ok=True)
    memo_structure = "Sections: Overview, Acquirer ID, Acq. Date, Consideration, Assets/Liabs, Goodwill, Disclosures"
    chatbot.set_context(
        standard_name="ASC805",
        standard_index_path=DUMMY_STANDARD_INDEX,
        agreement_index_path=DUMMY_AGREEMENT_INDEX,
        memo_template_structure=memo_structure
    )

    # --- Simulate Chat Interaction ---
    print("\n--- Chat Session (using Langchain with OpenAI GPT-4o-mini) ---")

    questions = [
        "Hi there, can you explain what ASC 805 is generally about?",
        "According to the ASC 805 standard, what are the main criteria for identifying the acquirer?", # Should trigger standard RAG
        "What does the merger agreement say about the effective date of the transaction?", # Should trigger agreement RAG
        "Tell me about goodwill under ASC 805.", # Should trigger standard RAG
        "Based on our previous discussion about identifying the acquirer, what's the next logical step according to the standard?" # Should use history
    ]

    for i, q in enumerate(questions):
        print(f"\nTurn {i+1}")
        print(f"User: {q}")
        response = chatbot.send_chat_message(q)
        print(f"Assistant: {response}")

    # --- Show History ---
    print("\n--- Final Chat History (from Langchain Memory) ---")
    history = chatbot.get_history()
    if history:
        for msg in history:
             print(f"- {msg['role'].capitalize()}: {msg['text'][:150]}{'...' if len(msg['text']) > 150 else ''}")
    else:
        print("No chat history available.")
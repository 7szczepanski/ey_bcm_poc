import os
from typing import List, Dict, Any, Optional, Sequence, Tuple

# Langchain specific imports
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_community.vectorstores import FAISS # Needed for retriever
from langchain.chains import ConversationalRetrievalChain # Using this chain

from app.indexing import load_standard_index, load_agreement_index, embeddings
from app.models.chat import ChatMessage # Keep this for session data format
from app.models.structured_output import StructuredMergerData, SectionCompleteness

# --- LLM Initialization --- 
# Load API key from environment variable set by Docker Compose
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[WARN] OPENAI_API_KEY environment variable not found inside container.")
    # Optionally raise an error or try other methods
    # For now, let ChatOpenAI handle it (it might have other ways to find the key)

llm = ChatOpenAI(
    model_name="gpt-4o-mini", # Or your preferred model
    openai_api_key=api_key, # Pass explicitly
    temperature=0.7
)

# --- Session-Specific Chat Instances --- 
# We need to manage memory and potentially chains per session
# Store active chains/memory keyed by session_id
active_chat_sessions: Dict[str, ConversationalRetrievalChain] = {}
active_chat_memory: Dict[str, ConversationBufferMemory] = {}

def get_or_create_chat_session(session_id: str, standard_index: FAISS, agreement_index: FAISS) -> ConversationalRetrievalChain:
    """Gets or creates a ConversationalRetrievalChain for a given session."""
    if session_id in active_chat_sessions:
        # TODO: Potentially update retrievers if standard/agreement changes?
        # For now, assume they are fixed once the session starts needing chat.
        return active_chat_sessions[session_id]

    print(f"Creating new chat session and memory for {session_id}")
    # Create retrievers
    standard_retriever = standard_index.as_retriever(search_kwargs={"k": 2})
    agreement_retriever = agreement_index.as_retriever(search_kwargs={"k": 2})

    # Combine retrievers - simple approach: search both, use results from agreement first?
    # Or let the chain decide? For ConversationalRetrievalChain, a single retriever is typical.
    # Let's try combining the docs manually in the retrieval step (simpler than chain modification).
    # We won't use Langchain's combine_retrievers for now.

    # Create memory for this session
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key='answer' # Important for ConversationalRetrievalChain
    )
    active_chat_memory[session_id] = memory

    # Create the Conversational Retrieval Chain
    # Note: This chain manages context retrieval implicitly based on history and question.
    # We don't need the manual 'retrieve_rag_context' function like in the example.
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        # Combine retrievers? Langchain has ways, but let's stick to one for simplicity first.
        # We might need a custom retriever or process if we want advanced merging.
        # Let's prioritize the agreement retriever for typical specific questions.
        retriever=agreement_retriever, # Or standard_retriever, or a combined one.
        memory=memory,
        return_source_documents=True, # Get source docs for evidence tracking
        # You can customize prompts here if needed
        # combine_docs_chain_kwargs={"prompt": ...}
    )

    active_chat_sessions[session_id] = chain
    return chain

def get_chatbot_response(
    message: str,
    standard_index: FAISS,
    agreement_index: FAISS,
    chat_history: List[Dict[str, str]]
) -> Tuple[str, Dict[str, Any]]:
    """Get a response from the chatbot using both standard and agreement indexes."""
    # Create retrievers
    standard_retriever = standard_index.as_retriever(
        search_kwargs={"k": 3}
    )
    agreement_retriever = agreement_index.as_retriever(
        search_kwargs={"k": 3}
    )

    # Create memory from chat history
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    # Convert the chat history format for langchain
    for msg in chat_history:
        if msg["role"] == "user":
            memory.chat_memory.add_user_message(msg["content"])
        elif msg["role"] == "assistant":
            memory.chat_memory.add_ai_message(msg["content"])

    # Create base LLM for conversation
    conversation_llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0.7
    )
    
    # Create structured output LLM for data extraction
    structured_llm = conversation_llm.with_structured_output(StructuredMergerData)
    
    # Create a custom prompt template for conversation
    conversation_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant that provides information about business combinations and accounting treatments.
        
        Answer questions clearly and professionally, based on the context provided.
        Focus on being accurate and informative while maintaining a conversational tone.
        """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])
    
    # Create chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=conversation_llm,
        retriever=agreement_retriever,
        memory=memory,
        return_source_documents=True,
        combine_docs_chain_kwargs={
            "prompt": conversation_prompt
        }
    )

    # Get response
    result = chain({"question": message})
    answer = result["answer"]
    
    # Extract structured data using the structured output LLM
    extraction_prompt = f"""
    Based on this conversation:
    
    User: {message}
    
    Your response: {answer}
    
    Extract any key information relevant for a business combination memo.
    Only include fields where you have medium or high confidence in the information.
    If no relevant information exists for a field, omit it entirely.
    Focus on factual information with specific details about the business combination.
    """
    
    try:
        # Use structured output LLM to get properly formatted data
        structured_data = structured_llm.invoke(extraction_prompt)
        
        # Convert to dictionary for compatibility with existing code
        structured_output = structured_data.model_dump(exclude_none=True)
        print(f"Extracted structured data: {structured_output}")
        return answer, structured_output
    except Exception as e:
        print(f"Error extracting structured data: {e}")
        return answer, {}

def process_chat_message(
    session_id: str,
    session_data: Dict[str, Any],
    message: str
) -> Dict[str, Any]:
    """Process a chat message and return response with structured output."""
    if not session_data.get("selected_standard"):
        return {"error": "No standard selected"}
    if not session_data.get("agreement_uploaded"):
        return {"error": "No agreement uploaded"}

    standard = session_data["selected_standard"]
    standard_index = load_standard_index(standard)
    if not standard_index:
        return {"error": f"Failed to load standard index: {standard}"}

    agreement_index = load_agreement_index(session_id)
    if not agreement_index:
        return {"error": "Failed to load agreement index"}

    response, structured_output = get_chatbot_response(
        message,
        standard_index,
        agreement_index,
        session_data.get("chat_history", [])
    )

    return {
        "response": response,
        "structured_output": structured_output
    }

# --- Function to potentially clear session from memory (e.g., on logout) --- 
def clear_chat_session_memory(session_id: str):
    if session_id in active_chat_sessions:
        del active_chat_sessions[session_id]
        print(f"Cleared chat chain from memory for session {session_id}")
    if session_id in active_chat_memory:
        active_chat_memory[session_id].clear()
        del active_chat_memory[session_id]
        print(f"Cleared chat memory from memory for session {session_id}")

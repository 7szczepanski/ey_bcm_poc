import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.indexing import load_standard_index, load_agreement_index
from app.models.memo import GeneratedMemo, Section as MemoSection, Evidence as MemoEvidence

# Use the actual LLM instance from chatbot module
from app.chatbot import llm as synthesis_llm # Rename for clarity

APP_DIR = Path("/app") # Base directory inside container
TEMPLATE_DIR = APP_DIR / "app/templates" # Corrected path relative to WORKDIR/app

def load_memo_template(template_name: str = "default_memo.json") -> Optional[Dict[str, Any]]:
    """Loads the memo template JSON file."""
    template_file = TEMPLATE_DIR / template_name
    try:
        with open(template_file, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading memo template {template_file}: {e}")
        return None

def get_standard_guidance(standard_index, topic_query: str, k: int = 2) -> List[MemoEvidence]:
    """Queries the standard index for guidance related to a topic."""
    if not standard_index or not topic_query:
        return []
    try:
        # Use similarity_search_with_score to potentially filter by relevance?
        docs_with_scores = standard_index.similarity_search_with_score(topic_query, k=k)
        evidence = []
        for doc, score in docs_with_scores:
             # Add a threshold if needed: if score < SOME_THRESHOLD: continue
             evidence.append(MemoEvidence(
                 source_type='standard',
                 document_name=doc.metadata.get('source', 'standard_doc'),
                 snippet=doc.page_content,
                 page_number=doc.metadata.get('page')
             ))
        return evidence
    except Exception as e:
        print(f"Error querying standard index for '{topic_query}': {e}")
        return []

def find_agreement_data(agreement_index, query: str, k: int = 3) -> List[MemoEvidence]:
    """Queries the agreement index for data related to a query."""
    if not agreement_index or not query:
        return []
    try:
        docs_with_scores = agreement_index.similarity_search_with_score(query, k=k)
        evidence = []
        for doc, score in docs_with_scores:
            evidence.append(MemoEvidence(
                 source_type='agreement',
                 document_name="agreement.pdf",
                 snippet=doc.page_content,
                 page_number=doc.metadata.get('page')
             ))
        return evidence
    except Exception as e:
        print(f"Error querying agreement index for '{query}': {e}")
        return []

def synthesize_section_content(section_title: str, structured_data: Optional[str], standard_evidence: List[MemoEvidence], agreement_evidence: List[MemoEvidence]) -> str:
    """Synthesizes the content for a memo section using the actual LLM."""
    # Construct a more detailed prompt for synthesis
    prompt = f"You are drafting a section for a business combination accounting memo.\n"
    prompt += f"Section Title: {section_title}\n\n"

    if structured_data:
        prompt += f"Relevant structured data previously extracted: \n{structured_data}\n\n"

    prompt += "Context from Accounting Standards:\n"
    if standard_evidence:
        for i, ev in enumerate(standard_evidence):
            prompt += f"[Standard Ref {i+1}] {ev.snippet[:200]}... (Source: {ev.document_name}, Page: {ev.page_number})\n"
    else:
        prompt += "(No specific standard context provided for this section)\n"
    prompt += "\n"

    prompt += "Context from Merger Agreement:\n"
    if agreement_evidence:
        for i, ev in enumerate(agreement_evidence):
            prompt += f"[Agreement Ref {i+1}] {ev.snippet[:200]}... (Page: {ev.page_number})\n"
    else:
        prompt += "(No specific agreement context provided for this section)\n"
    prompt += "\n"

    prompt += f"Draft the content for the '{section_title}' section based *only* on the provided context and structured data. Be concise and professional. If context is missing for certain aspects, state that information is not available in the provided documents."

    print(f"Synthesizing content for section: {section_title}...")
    try:
        # Use the imported LLM instance directly (basic chat completion call)
        # For better results, a dedicated prompt template and chain might be needed.
        ai_message = synthesis_llm.invoke(prompt)
        synthesized_text = ai_message.content
        print("Synthesis complete.")
        return synthesized_text
    except Exception as e:
        print(f"[ERROR] LLM Synthesis failed for section '{section_title}': {e}")
        return f"Error during content synthesis for {section_title}."

def generate_memo(
    standard_index, 
    agreement_index, 
    structured_output: Dict[str, Any] = None
) -> Tuple[GeneratedMemo, List[MemoEvidence]]:
    """Generates a memo using standard and agreement indexes."""
    if structured_output is None:
        structured_output = {}
    
    # Load template
    template = load_memo_template()
    if not template:
        raise ValueError("Failed to load memo template")
    
    generated_sections: List[MemoSection] = []
    all_evidence: List[MemoEvidence] = []
    
    print("Generating memo sections...")
    for section_template in template.get("sections", []):
        section_id = section_template.get("id")
        section_title = section_template.get("title", "Untitled Section")
        query_hints = section_template.get("query_hints", [])
        standard_topic = section_template.get("standard_topic")
        
        print(f"Processing section: {section_title}")
        
        section_standard_evidence: List[MemoEvidence] = []
        section_agreement_evidence: List[MemoEvidence] = []
        
        # 1. Query Standard Index (if topic provided)
        if standard_topic:
            section_standard_evidence = get_standard_guidance(standard_index, standard_topic)
            print(f"  Found {len(section_standard_evidence)} standard evidence snippets for topic '{standard_topic}'")
        
        # 2. Query Agreement Index (using hints)
        agreement_query = " ".join(query_hints)
        if agreement_query:
            section_agreement_evidence = find_agreement_data(agreement_index, agreement_query)
            print(f"  Found {len(section_agreement_evidence)} agreement evidence snippets based on hints.")
        
        # 3. Check Structured Output
        section_structured_data = structured_output.get(section_id)
        if section_structured_data:
            print(f"  Found structured data for this section: {section_structured_data}")
        
        # 4. Synthesize Content
        content = synthesize_section_content(
            section_title,
            json.dumps(section_structured_data) if section_structured_data else None,
            section_standard_evidence,
            section_agreement_evidence
        )
        
        # 5. Assemble Section
        memo_section = MemoSection(
            id=section_id,
            title=section_title,
            content=content,
            evidence=section_standard_evidence + section_agreement_evidence,
            standard_topic=standard_topic
        )
        generated_sections.append(memo_section)
        all_evidence.extend(memo_section.evidence)
    
    final_memo = GeneratedMemo(
        title=template.get("title", "Business Combination Memo"),
        sections=generated_sections
    )
    
    print("Memo generation complete.")
    return final_memo, all_evidence 
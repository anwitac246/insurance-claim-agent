# Agents Module

This module contains the AI agents for the SecureWheel Insurance AI claims processing system.

## Document Verification Agent (Agent 2)

The Document Verification Agent has been refactored into a modular structure for better maintainability:

### Files:
- `document_agent.py` - Main orchestrator class
- `document_parser.py` - File parsing utilities (LlamaParse integration)
- `document_extractor.py` - LLM-based document extraction (Groq API)
- `document_validator.py` - Validation rule implementation (POL-001 Section 7)
- `document_checker.py` - Document completeness scoring and missing document detection

### Responsibilities:
1. Query Pinecone (namespace: document_rules) for document requirements
2. Parse uploaded files via LlamaParse → Markdown
3. Use Groq LLM (llama-3.3-70b-versatile) to extract typed fields
4. Run all RULE-M-* validation checks from POL-001 Section 7
5. Compute Document Completeness Score (DCS) per POL-002
6. Return DocumentAgentOutput with status READY | INCOMPLETE | INVALID

### SRE Features:
- Idempotency: same files → same extracted JSON (deterministic via temp=0)
- Confidence Score: weighted average of per-field extraction confidence
- Error Budget: up to 2 LLM extraction retries per file
- Observability: AgentTrace logged with execution_time_ms

### Usage:
```python
from agents.document_agent import DocumentVerificationAgent

agent = DocumentVerificationAgent()
updated_state = agent.run(state)  # state is a ClaimState
```
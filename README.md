# Business Combination Memo Generator (PoC)

## Overview

The Business Combination Memo Generator is a specialized application designed to assist with creating accounting memos for business combinations according to ASC 805 and IFRS standards. It features an **iterative, conversational assistant** that guides users through the process of creating comprehensive business combination memos, proactively identifying information gaps and requesting additional details.

## Architecture

The application uses a modern stack with FastAPI backend and Next.js frontend:

### Backend (FastAPI)

- **Authentication System**: User authentication via username/password from `users.txt`
- **Session Management**: File-based session storage with JWT cookies
- **Document Indexing**: Processes accounting standards and merger agreements into FAISS vector indexes
- **Memo Generation**: Template-based generation with evidence tracking
- **Chatbot Integration**: Conversational interface with structured data extraction

### Frontend (Next.js + shadcn/ui)

- **Authentication Flow**: Login page with session cookie handling
- **Standard Selection**: UI for choosing between IFRS and ASC 805
- **Agreement Upload**: File upload interface with progress indicators
- **Chatbot Interface**: Conversational UI for information gathering
- **Memo Display**: Interactive viewer with evidence tracking
- **PDF Viewer**: Integrated display of source documents

### Iterative Memo Generation Approach

1. **Initial Generation**: Creates first draft using available information
2. **Gap Analysis**: Evaluates completeness and generates follow-up questions
3. **Information Collection**: Uses chatbot to gather missing information
4. **Structured Extraction**: Parses responses for relevant data
5. **Regeneration**: Incorporates new information for improved versions
6. **Continuous Improvement**: Repeats until memo is complete

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- PDF files for standards (IFRS and ASC 805)
- User credentials file (`users.txt`)

### Backend Setup

1. Ensure PDF files are in `backend/app/data/`:
   - `ifrs.pdf`: IFRS standard document
   - `blueprint.pdf`: ASC 805 standard document

2. Configure user credentials in `users.txt` (format: `username:password`)

3. Build and start the backend:
   ```bash
   docker-compose up --build backend -d
   ```

### Frontend Setup

1. Build and start the frontend:
   ```bash
   docker-compose up --build frontend -d
   ```

2. Access the application at http://localhost:3000

## API Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|--------------|
| `/api/login` | POST | Authenticates user and creates session | No |
| `/api/logout` | POST | Terminates the user session | Yes |
| `/api/session` | GET | Returns the current session data | Yes |
| `/api/set-standard` | POST | Sets the accounting standard (IFRS or ASC 805) | Yes |
| `/api/upload-agreement` | POST | Uploads and indexes a merger agreement PDF | Yes |
| `/api/chatbot` | POST | Interacts with indexed documents and extracts structured data | Yes |
| `/api/generate-memo` | POST | Creates a structured memo from indexed data | Yes |
| `/api/seed-questions` | POST | Seeds follow-up questions to the chat | Yes |
| `/api/accept-memo` | POST | Marks the current memo as finalized | Yes |
| `/api/evaluate-message` | POST | Evaluates if a message contains data that should trigger regeneration | Yes |
| `/api/standard-pdf/:standard` | GET | Serves the standard PDF for viewing | Yes |
| `/api/agreement-pdf/:session_id` | GET | Serves the uploaded agreement PDF for viewing | Yes |

## Core Features

### Auto-Regeneration

The system automatically extracts structured data from user chat messages, evaluates its significance, and triggers memo regeneration when important new information is provided. This creates a seamless iterative workflow.

### Evidence Tracking and Sourcing

For each section of the memo, the system tracks:
- References to specific passages in the accounting standard (with page numbers)
- References to clauses in the merger agreement document (with page numbers)
- Information provided by the user through chat interactions

### Structured Data Extraction

The chatbot uses LangChain's structured output capabilities to extract meaningful data from user messages, including:
- Acquisition details (date, entities involved)
- Transaction information (consideration, valuation)
- Financial data (fair value assessments, goodwill calculations)

## Testing

The project includes two main test scripts:

1. **`test_backend.sh`**: Comprehensive API flow test
   ```bash
   ./test_backend.sh
   ```

2. **`test_docker_index.sh`**: Tests Docker container index creation
   ```bash
   ./test_docker_index.sh
   ```

## Data Flow

1. Users authenticate via the login page
2. After login, users select an accounting standard (IFRS or ASC 805)
3. Users upload a merger agreement PDF, which is processed and indexed
4. The system generates an initial memo and identifies information gaps
5. The chatbot proactively requests missing information from the user
6. As users provide responses, the system extracts structured data
7. The memo is regenerated incorporating new information
8. Steps 5-7 repeat until the memo is complete
9. Users can accept the final memo when satisfied

## Directory Structure

```
/
├── backend/                  # FastAPI backend application
│   ├── app/                  # Main application code
│   │   ├── data/             # Standard PDFs and indexes
│   │   ├── session_data/     # Session storage
│   │   ├── user_data/        # User-specific data
│   │   ├── templates/        # Memo templates
│   ├── Dockerfile            # Backend container definition
│   └── requirements.txt      # Python dependencies
├── frontend/                 # Next.js frontend application
│   ├── components/           # Reusable UI components
│   ├── pages/                # Application pages
│   ├── styles/               # CSS and styling
│   ├── Dockerfile            # Frontend container definition
│   └── package.json          # JavaScript dependencies
├── docker-compose.yml        # Container orchestration
├── test_backend.sh           # Backend API test script
└── test_docker_index.sh      # Docker index test script
```

## Troubleshooting

### Index Loading Issues

If the system encounters problems loading indices:

1. **Check index existence**: Verify that index files exist in the expected locations
   ```bash
   docker-compose exec backend ls -la /app/data/ifrs
   docker-compose exec backend ls -la /app/data/asc805
   ```

2. **Rebuild indices**: Force a rebuild by removing the existing indices
   ```bash
   docker-compose down
   docker volume rm bcm_poc_backend_index_data
   docker-compose up --build backend -d
   ```

### PDF Serving Issues

If PDFs are not displayed correctly:

1. **Check PDF paths**: Ensure PDFs are properly saved in the expected locations
   ```bash
   docker-compose exec backend ls -la /app/data
   docker-compose exec backend ls -la /app/user_data
   ```

2. **Check cookie authentication**: Verify that your session cookie is being properly sent with PDF requests

## Security Considerations

This PoC implementation includes:

1. **HttpOnly Cookies**: Session IDs are stored in HttpOnly cookies
2. **JWT Signing**: Session cookies are signed using JWT
3. **File-Based User Store**: For the PoC, user credentials are stored in `users.txt`

Note: This is a Proof of Concept implementation. For production use, additional security measures would be required. 
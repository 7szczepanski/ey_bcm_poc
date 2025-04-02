# Business Combination Memo Generator Backend

## Overview

The Business Combination Memo Generator is a specialized application designed to assist with creating accounting memos for business combinations according to ASC 805 and IFRS standards. The backend component handles API requests, user authentication, session management, standard index loading, merger agreement processing, chatbot logic, and memo generation.

The application is built around an **iterative, conversational assistant** that guides users through the process of creating a comprehensive business combination memo, proactively identifying information gaps and requesting additional details to improve the quality of the final document.

## Architecture

The backend is implemented as a FastAPI application with the following core components:

### Core Components

1. **Authentication System** (`auth.py`)
   - Manages user authentication via username/password from `users.txt`
   - Creates and validates session cookies using JWT tokens
   - Protects API endpoints with session verification

2. **Session Management** (`session_manager.py`)
   - Handles file-based session storage in `/app/session_data/`
   - Manages user state during the application flow
   - Implements session creation, loading, and validation
   - Tracks conversation history and extracted information between iterations

3. **Document Indexing System** (`indexing.py`, `startup.py`)
   - Processes accounting standards (IFRS and ASC 805) into FAISS vector indexes
   - Handles on-the-fly indexing of user-uploaded agreement PDFs
   - Implements automated index creation and persistence via Docker volumes
   - Maintains source information for evidence tracking

4. **API Routes** (`api.py`)
   - Exposes endpoints for authentication, standard selection, file upload, chatbot interaction, and memo generation
   - Ensures proper session validation and error handling
   - Coordinates between different service components
   - Implements iterative memo improvement through `/seed-questions` and `/accept-memo` endpoints

5. **Memo Generation** (`memo_generation.py`)
   - Implements template-based generation of structured business combination memos
   - Integrates with vector search to gather relevant information
   - Organizes content into sections based on accounting standards
   - Tracks evidence sources (standard references, agreement clauses, chat history)
   - Evaluates section completeness and generates follow-up questions

### Iterative Memo Generation Approach

The application implements an iterative approach to memo generation:

1. **Initial Generation**: Creates a first draft of the memo using available information from the standard and agreement
2. **Gap Analysis**: Evaluates each section for completeness and generates specific follow-up questions
3. **Information Collection**: Uses the chatbot to proactively ask users for missing information
4. **Structured Extraction**: Parses user responses to extract structured data relevant to memo sections
5. **Regeneration**: Incorporates new information to produce an improved memo version
6. **Continuous Improvement**: Repeats steps 2-5 until the memo is complete or accepted by the user

This approach ensures that:
- The system is always ready to assist, identifying information needs and guiding users
- The memo evolves incrementally based on user input
- Complete source evidence is maintained for each statement in the memo
- Users can track the progress of memo completeness through multiple iterations

### Evidence Tracking and Sourcing

For each section of the memo, the system tracks:
- References to specific passages in the accounting standard (with page numbers)
- References to clauses in the merger agreement document (with page numbers)
- Information provided by the user through chat interactions (with timestamps)

This comprehensive source tracking enables users to verify the accuracy of the memo content and provides a clear audit trail for accounting decisions.

### Data Flow

1. Users authenticate via the `/api/login` endpoint
2. After successful login, users select an accounting standard (IFRS or ASC 805)
3. Users upload a merger agreement PDF, which is processed and indexed
4. The system generates an initial memo and identifies information gaps
5. The chatbot proactively requests missing information from the user
6. As users provide responses, the system extracts structured data
7. The memo is regenerated incorporating new information
8. Steps 5-7 repeat until the memo is complete
9. Users can accept the final memo when satisfied

### Directory Structure

```
backend/
├── app/                      # Main application code
│   ├── data/                 # Contains standard PDFs and pre-built indexes
│   │   ├── ifrs/             # IFRS standard index directory
│   │   ├── asc805/           # ASC 805 standard index directory
│   │   ├── ifrs.pdf          # IFRS standard PDF document
│   │   └── blueprint.pdf     # ASC 805 standard PDF document
│   ├── session_data/         # Session storage (persisted)
│   ├── user_data/            # User-specific data (persisted)
│   ├── templates/            # Contains memo JSON templates
│   ├── __init__.py
│   ├── main.py               # FastAPI application entry point
│   ├── api.py                # API route definitions
│   ├── auth.py               # Authentication logic
│   ├── indexing.py           # Vector index management
│   ├── memo_generation.py    # Memo creation logic
│   ├── session_manager.py    # Session handling
│   └── startup.py            # Initialization and index creation
├── docker-entrypoint.sh      # Docker container startup script
├── Dockerfile                # Docker container definition
├── requirements.txt          # Python dependencies
└── users.txt                 # User credentials for authentication
```

## FAISS Indexing Architecture

The application uses FAISS (Facebook AI Similarity Search) for efficient semantic search over documents:

1. **Standard Indexes**
   - Created from ASC 805 and IFRS PDFs during container startup
   - Stored in persistent Docker volumes for reuse
   - Loaded with `allow_dangerous_deserialization=True` for version compatibility
   - Maintains document structure for evidence source tracking

2. **Agreement Indexes**
   - Created at runtime from user-uploaded PDFs
   - Stored in user-specific directories
   - Unique to each user session
   - Preserves page numbers and context for source referencing

3. **Index Management**
   - `startup.py`: Validates existing indexes and creates new ones if needed
   - `indexing.py`: Loads and manages indexes during application runtime
   - Automatic path resolution with fallbacks for container environments

## Docker Integration

The application uses Docker for containerization with the following features:

1. **Docker Volumes**
   - `backend_user_data`: Persists user-uploaded files and indexes
   - `backend_session_data`: Persists session information
   - `backend_index_data`: Persists pre-built standard indexes

2. **Entrypoint Script**
   - Performs filesystem verification
   - Runs startup indexing to ensure standards are processed
   - Launches the FastAPI application

3. **Container Configuration**
   - Uses Python 3.11 as the base image
   - Pre-copies PDFs for index creation
   - Sets appropriate file permissions

## Setup and Installation

### Prerequisites

- Docker and Docker Compose
- PDF files for standards (IFRS and ASC 805/blueprint)

### Environment Setup

1. Ensure PDF files are available in `backend/app/data/`:
   - `ifrs.pdf`: IFRS standard document
   - `blueprint.pdf`: ASC 805 standard document

2. Configure user credentials in `users.txt` (format: `username:password`)

### Building and Running

```bash
# Build and start the backend container
docker-compose up --build backend -d

# Check logs during startup
docker-compose logs -f backend

# Run backend tests
./test_backend.sh
```

## Testing

The project includes two test scripts:

1. **`test_backend.sh`**
   - Comprehensive API test that walks through the entire application flow
   - Tests login, session verification, standard selection, file upload, chat, and memo generation
   - Verifies cookies and session persistence
   - Tests the iterative process through seed-questions and follow-up responses

2. **`test_docker_index.sh`**
   - Tests the Docker container index creation and loading
   - Verifies that indexes persist between container restarts
   - Confirms API endpoints work with the indexed data

### Running Tests

```bash
# Test the full API flow
./test_backend.sh

# Test Docker index creation and persistence
./test_docker_index.sh
```

## API Endpoints

| Endpoint | Method | Description | Authentication Required |
|----------|--------|-------------|-------------------------|
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

### Auto-Regeneration Feature

The system implements an intelligent auto-regeneration feature that:

1. Automatically extracts structured data from user chat messages
2. Evaluates whether the extracted data contains meaningful information for the memo
3. Triggers memo regeneration when significant new information is provided
4. Returns regeneration status with the chat response

This allows the frontend to provide immediate feedback when user responses have been incorporated into the memo, creating a seamless iterative workflow.

The `/api/chatbot` endpoint now returns an enhanced response:

```json
{
  "response": "Thank you for providing that information...",
  "structured_output": {
    "acquisition_date": {"value": "2023-01-15", "confidence": "high"},
    "consideration": {"amount": "500M", "confidence": "high"}
  },
  "should_regenerate": true,
  "detected_fields": ["acquisition_date", "consideration"],
  "memo": {
    "regenerated": true,
    "iteration": 2,
    "detected_fields": ["acquisition_date", "consideration"]
  }
}
```

For cases where the frontend needs to evaluate a message without sending it to the chat, the `/api/evaluate-message` endpoint can be used to determine if a message contains information that should trigger regeneration.

## Troubleshooting

### Index Loading Issues

If the system encounters problems loading indices:

1. **Check index existence**: Verify that index files exist in the expected locations
   ```bash
   docker-compose exec backend ls -la /app/data/ifrs
   docker-compose exec backend ls -la /app/data/asc805
   ```

2. **Check file permissions**: Ensure volumes have correct permissions
   ```bash
   docker-compose exec backend ls -la /app/data
   ```

3. **Rebuild indices**: Force a rebuild by removing the existing indices
   ```bash
   docker-compose down
   docker volume rm bcm_poc_backend_index_data
   docker-compose up --build backend -d
   ```

### Path Resolution

The system is designed to handle multiple potential path configurations:

1. Primary Docker volume path: `/app/data/<standard>`
2. Mounted code path: `/app/app/data/<standard>`
3. Relative path: `app/data/<standard>`
4. Absolute Docker path: `/app/data/<standard>`

If paths are not resolving correctly, Docker logs will show detailed information about path searches.

## Performance Considerations

1. **Index Creation Time**: The initial creation of FAISS indices can take several minutes depending on the size of the PDF documents.

2. **Memory Usage**: The application requires sufficient memory to load the embeddings model and FAISS indices. Ensure Docker has adequate resources allocated (at least 4GB of RAM).

3. **Persistent Volumes**: Using Docker volumes ensures that indices only need to be created once, improving startup time on subsequent runs.

4. **Conversation Management**: The system efficiently manages conversation history between iterations to maintain context while optimizing performance.

## Security Considerations

This PoC implementation includes:

1. **HttpOnly Cookies**: Session IDs are stored in HttpOnly cookies to prevent client-side JavaScript access

2. **JWT Signing**: Session cookies are signed using JWT to prevent tampering

3. **File-Based User Store**: For the PoC, user credentials are stored in `users.txt`. In a production environment, this would be replaced with a secure database.

Note: This is a Proof of Concept implementation. For production use, additional security measures would be required. 
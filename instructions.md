# Instructions for Building Business Combination Memo Generator PoC (v2)

This document provides detailed, updated instructions for Cursor AI to build a Proof of Concept (PoC) for a Business Combination Memo Generator. This version incorporates improvements for robustness, organization, and developer experience.

**Key Features & Approach:**

*   **Backend (FastAPI):** Handles API requests, user authentication (from `users.txt`), session management (file-based), standard index loading (pre-built), merger agreement indexing (on-the-fly, user-specific), chatbot logic (LangChain), memo generation (JSON template-driven), and evidence tracking.
*   **Frontend (Next.js + shadcn/ui):** Provides the user interface for login, standard selection, file upload, chatbot interaction, memo display, and evidence viewing (PDF). Uses `shadcn/ui` for components and Tailwind CSS for styling.
*   **Data Storage (Local):**
    *   User credentials: `backend/users.txt`.
    *   Session state: JSON files in `backend/app/session_data/`.
    *   Pre-built Standard FAISS Indexes: Files in `backend/app/data/` (e.g., `backend/app/data/asc805/`).
    *   User-specific uploaded files & indexes: Stored in `backend/app/user_data/<session_id>/`.
*   **Containerization:** Docker Compose orchestrates the FastAPI backend and Next.js frontend.
*   **Security (PoC Level):** Uses HttpOnly cookies for session management. **Note:** `users.txt` is insecure and only for PoC demonstration.

**Step-by-Step Implementation:**

**1. Backend (FastAPI):**

*   **1.1. Set up FastAPI Project:**
    *   Create the `backend/app` directory structure (including `models`, `services`, `data`, `user_data`, `session_data`, `templates`).
    *   Create placeholder files: `backend/app/user_data/.gitkeep`, `backend/app/session_data/.gitkeep`.
    *   Create an empty `backend/app/__init__.py`.
    *   Create `backend/requirements.txt` with:
        ```
        fastapi
        uvicorn
        langchain
        faiss-cpu
        pypdf2
        sentence-transformers
        python-jose[cryptography]  # For signing session cookies
        passlib[bcrypt]            # Optional: Slightly better than plain text for users.txt PoC
        python-multipart         # For file uploads
        # Optional: filelock     # If implementing manual file session locking
        ```
    *   Create `backend/Dockerfile` (adjust Python version if needed):
        ```dockerfile
        FROM python:3.11-slim-buster
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt
        COPY ./app .
        # Ensure user_data and session_data directories exist if needed inside container
        RUN mkdir -p /app/user_data /app/session_data
        CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
        ```
    *   Add `user_data/` and `session_data/` to `backend/.gitignore`.

*   **1.2. Create `backend/users.txt`:**
    *   Populate with `username:password` pairs (e.g., `testuser:password123`). Consider using passlib to store slightly more securely even for PoC if time permits.

*   **1.3. Implement Authentication (`backend/app/auth.py`):**
    *   **`get_users_from_file()`:** Reads `users.txt`.
    *   **`verify_password()`:** Verifies passwords (use `passlib` if implemented).
    *   **`create_session_cookie(session_id: str)`:** Creates a signed JWT or uses `itsdangerous` to securely sign the `session_id` for the cookie value. Use a secret key (can be hardcoded for PoC, but use env var ideally).
    *   **`/api/login` route (`backend/app/api.py`):**
        *   Accepts `username`, `password` (Pydantic model in `backend/app/models/auth.py`).
        *   Verifies credentials.
        *   On success:
            *   Generate a unique `session_id` (e.g., `uuid.uuid4().hex`).
            *   Call `create_session()` (from `session_manager.py`) to initialize session state.
            *   Call `create_session_cookie()` to get the signed cookie value.
            *   Return a `Response` setting an `HttpOnly`, `Secure` (if using HTTPS, often disable for local HTTP PoC), `SameSite=Lax` cookie named `session_id` with the signed value.

*   **1.4. Implement File-Based Session Management (`backend/app/services/session_manager.py` or `backend/app/sessions.py`):**
    *   Define `SESSION_DIR = "app/session_data"`.
    *   Define `COOKIE_SECRET_KEY` (hardcoded for PoC).
    *   **`create_session(session_id: str)`:** Creates an empty JSON file `SESSION_DIR/<session_id>.json`.
    *   **`save_session_data(session_id: str, data: dict)`:** Writes the `data` dictionary to `SESSION_DIR/<session_id>.json`. (Consider using `filelock` if concurrency becomes a concern, unlikely in PoC).
    *   **`load_session_data(session_id: str)`:** Reads and returns data from `SESSION_DIR/<session_id>.json`. Handles `FileNotFoundError`.
    *   **`verify_session_cookie(session_cookie: str | None)`:** Verifies the signature of the cookie value using `COOKIE_SECRET_KEY` and extracts the `session_id`. Returns `session_id` or `None`.
    *   **FastAPI Dependency `get_current_session(session_cookie: str | None = Cookie(None))`:**
        *   Calls `verify_session_cookie()` on the `session_cookie`.
        *   If invalid/missing, raise `HTTPException(401, "Invalid or missing session")`.
        *   Loads session data using `load_session_data()`.
        *   Returns a dictionary containing `{'session_id': session_id, 'data': loaded_data}`.

*   **1.5. Implement Indexing Logic (`backend/app/indexing.py`):**
    *   **Pre-indexing Standards (Manual Step):** Before running the app, manually run a script (or do it manually) to:
        *   Load ASC 805 PDF/text.
        *   Split, embed (using `SentenceTransformerEmbeddings(model_name='all-MiniLM-L6-v2')`), and create FAISS index.
        *   Save the index files (`index.faiss`, `index.pkl`) to `backend/app/data/asc805/`.
        *   Repeat for IFRS standard, saving to `backend/app/data/ifrs/`.
    *   **`load_standard_index(standard: str)`:**
        *   Takes `standard` ("ASC805" or "IFRS").
        *   Constructs the path: `backend/app/data/<standard>/`.
        *   Loads the pre-built FAISS index from that path using `FAISS.load_local()`. Requires embeddings function instance.
        *   Returns the FAISS index object.
    *   **`create_agreement_index(pdf_file: UploadFile, session_id: str)`:**
        *   Takes the uploaded PDF and `session_id`.
        *   Defines the user's data path: `user_dir = f"app/user_data/{session_id}"`.
        *   Creates the directory `user_dir` if it doesn't exist.
        *   Saves the uploaded PDF to `user_dir/agreement.pdf`.
        *   Uses LangChain `PyPDFLoader` on the saved PDF.
        *   Splits using `RecursiveCharacterTextSplitter`.
        *   Embeds using `SentenceTransformerEmbeddings(model_name='all-MiniLM-L6-v2')`.
        *   Creates FAISS index using `FAISS.from_documents()`.
        *   Saves the index locally to `user_dir` using `faiss_index.save_local(user_dir)`.
        *   Returns `True` on success.

*   **1.6. Implement Merger Agreement Upload (`backend/app/api.py`):**
    *   **`/api/upload-agreement` (POST):**
        *   Depends on `get_current_session`. Gets `session_info` dict.
        *   Accepts an `UploadFile`.
        *   Calls `create_agreement_index(file, session_info['session_id'])`.
        *   Update session data (using `save_session_data`) to mark agreement as uploaded, e.g., `session_info['data']['agreement_uploaded'] = True`.
        *   Return success/error message.

*   **1.7. Implement Standard Selection (`backend/app/api.py`):**
    *   **`/api/set-standard` (POST):**
        *   Depends on `get_current_session`. Gets `session_info`.
        *   Accepts `standard` ("ASC805" or "IFRS") (Pydantic model).
        *   Validate the standard name.
        *   Update session data: `session_info['data']['selected_standard'] = standard`.
        *   Call `save_session_data()`.
        *   Return success message. (No need to load the index here, load it when needed).

*   **1.8. Implement Chatbot Logic (`backend/app/chatbot.py` and `backend/app/api.py`):**
    *   **`/api/chatbot` (POST) in `backend/app/api.py`:**
        *   Depends on `get_current_session`. Gets `session_info`.
        *   Requires `selected_standard` and `agreement_uploaded` to be set in session data. Handle errors if not set.
        *   Load the standard index: `standard_index = load_standard_index(session_info['data']['selected_standard'])`.
        *   Load the agreement index: `agreement_index = FAISS.load_local(f"app/user_data/{session_info['session_id']}", embeddings=SentenceTransformerEmbeddings(model_name='all-MiniLM-L6-v2'))`.
        *   Create retrievers for both indexes. Combine them if desired (e.g., query both, merge results) or use them separately based on the query.
        *   Load chat history from `session_info['data'].get('chat_history', [])`.
        *   Initialize `ConversationalRetrievalChain` with LLM, retriever(s), and memory loaded with history.
        *   Process user message.
        *   Update chat history: `session_info['data']['chat_history'] = updated_history`.
        *   Extract and store structured output if configured: `session_info['data']['structured_output'] = extracted_data`.
        *   Call `save_session_data()`.
        *   Return response and structured output.

*   **1.9. Implement Memo Generation (`backend/app/memo_generation.py` and `backend/app/api.py`):**
    *   **Create Template (`backend/app/templates/default_memo.json`):**
        ```json
        {
          "title": "Business Combination Memo",
          "sections": [
            { "id": "intro", "title": "Introduction", "query_hints": ["Purpose of memo", "Parties involved"] },
            { "id": "acquirer", "title": "Identification of the Acquirer", "standard_topic": "ASC 805-10-55-4", "query_hints": ["Who is the acquirer?", "Factors determining acquirer"] },
            { "id": "acquisition_date", "title": "Determining the Acquisition Date", "standard_topic": "ASC 805-10-25-6", "query_hints": ["Closing date", "Date control obtained"] },
            // ... other sections (consideration, NCI, assets/liabilities, goodwill)
          ]
        }
        ```
    *   **`/api/generate-memo` (POST) in `backend/app/api.py`:**
        *   Depends on `get_current_session`. Gets `session_info`.
        *   Requires `selected_standard` and `agreement_uploaded`.
        *   Load standard index and agreement index (similar to chatbot route).
        *   Load the JSON memo template.
        *   Load structured output from `session_info['data'].get('structured_output', {})`.
        *   Iterate through template sections:
            *   For each section, use hints/topics to query standard index (create `get_standard_guidance` helper).
            *   Use hints and standard guidance to query agreement index (create `find_agreement_data` helper).
            *   Check `structured_output` for pre-filled data.
            *   Synthesize text for the section using LLM or simpler logic (create `synthesize_section` helper).
            *   Track evidence (source doc, page/chunk ref, text snippet).
        *   Assemble the final memo structure (e.g., dictionary).
        *   Return generated memo and evidence list.

*   **1.10. Create Pydantic Models (`backend/app/models/`)** for all request/response bodies.

*   **1.11. Main FastAPI Application (`backend/app/main.py`):** Include API router. Add CORS middleware if needed (allow frontend origin and credentials).

*   **1.12. API Router (`backend/app/api.py`):** Define all routes as described, ensuring they use the `get_current_session` dependency and interact with the session manager and indexing logic correctly.

**2. Frontend (Next.js + shadcn/ui):**

*   **2.1. Set up Next.js Project:**
    *   `npx create-next-app frontend` (select TypeScript if preferred, Tailwind CSS).
    *   `cd frontend`
    *   `npx shadcn-ui@latest init` (configure paths).
    *   Install components: `npx shadcn-ui@latest add button input select card toast accordion dialog sheet label` (add more as needed).
    *   Install libraries: `npm install axios react-pdf nookies` (or yarn).

*   **2.2. Implement Login Page (`pages/index.js`):**
    *   Use `Card`, `Label`, `Input`, `Button` from `shadcn/ui`.
    *   On form submit:
        *   Make POST request to `/api/login` using `axios`. **Crucially, configure axios instance or request with `withCredentials: true`**.
        *   On success (2xx response), the browser automatically stores the `HttpOnly` cookie set by the backend. Redirect to `/create-memo`.
        *   On error (401), show error message using `Toast`.

*   **2.3. Implement Memo Creation Page (`pages/create-memo.js`):**
    *   Wrap this page with `AuthGuard` (see 2.5).
    *   Use `Card`, `Select` (for standard), `Input type="file"` (styled if possible), `Button`.
    *   **Standard Selection:** On change, POST to `/api/set-standard`. Use `Toast` for success/error feedback.
    *   **Merger Agreement Upload:** On file selection, POST `FormData` to `/api/upload-agreement`. Use `Toast` for feedback. Show loading state on button.
    *   **Chatbot (`components/ChatbotInterface.js`):**
        *   Use `Card`, `Input`, `Button`, scrollable area for messages.
        *   Send messages to `/api/chatbot`. Display conversation history. Handle potential structured output display or updates.
    *   **Generate Memo Button:** POST to `/api/generate-memo`. Show loading state. On success, redirect to `/memo` passing generated data (e.g., via state management or router query - state preferred). Use `Toast` for errors.

*   **2.4. Implement Memo Display Page (`pages/memo.js`):**
    *   Wrap with `AuthGuard`.
    *   Retrieve memo data (passed from previous page).
    *   Use `Card` for overall structure. Use `Accordion` to display memo sections.
    *   Inside each section, display generated text and list of evidence snippets.
    *   Clicking evidence could open a `Dialog` or `Sheet` containing the `PdfViewer.js` component.
    *   **PDF Viewer (`components/PdfViewer.js`):**
        *   Use `react-pdf`. Configure worker source.
        *   Accept PDF URL (needs a way to serve the uploaded agreement PDF securely from the backend, or pass its content) and target page number.
        *   Implement logic to load and navigate the PDF within the Dialog/Sheet.

*   **2.5. Implement Authentication Guard (`components/AuthGuard.js`):**
    *   A wrapper component.
    *   Use `useEffect` and `useRouter`.
    *   In `useEffect`, check for the presence of the `session_id` cookie using `nookies.get()`. **Important:** For SSR/initial load protection, this check might also need to happen in `getServerSideProps` or similar on the wrapped pages to redirect server-side if unauthenticated.
    *   If no cookie, redirect to `/` (login page).
    *   Render children if authenticated.

*   **2.6. Update `_app.js`:** Include global layout, context providers (if any), and `<Toaster />` component from `shadcn/ui`.

*   **2.7. Configure `.env.local`:** `NEXT_PUBLIC_API_URL=http://localhost:8000` (or whatever host/port Docker exposes).

*   **2.8. Create `docker-compose.override.yml` in `frontend`:** Map port 3000.

**3. Docker Compose:**

*   Create `docker-compose.yml` at the root:
    ```yaml
    version: '3.8'
    services:
      backend:
        build: ./backend
        ports:
          - "8000:8000"
        volumes:
          - ./backend/app:/app # Map code for hot-reloading
          - backend_user_data:/app/user_data # Persist user data across container restarts
          - backend_session_data:/app/session_data # Persist session data
        environment:
          # Set COOKIE_SECRET_KEY here if using env vars
          - WATCHFILES_FORCE_POLLING=true # May help hot-reloading in Docker
      frontend:
        build: ./frontend
        command: npm run dev
        volumes:
          - ./frontend:/app
          - /app/node_modules
        environment:
          - NEXT_PUBLIC_API_URL=http://backend:8000
          - WATCHPACK_POLLING=true # May help Next.js hot-reloading in Docker
        depends_on:
          - backend
        ports:
          - "3000" # Defined in override
        networks:
          - app-network

    networks:
      app-network:
        driver: bridge

    volumes: # Define persistent volumes
      backend_user_data:
      backend_session_data:
    ```
*   Create `frontend/Dockerfile` (ensure it copies necessary files and runs `npm run dev`).

**4. Instructions for Cursor AI:**

1.  **Backend First:** Implement steps 1.1 - 1.7, focusing on project setup, authentication with HttpOnly cookies, file-based session management, standard index loading (assuming pre-built indexes exist), and agreement upload/indexing into user-specific directories. Test login and file upload via API calls first.
2.  **Chatbot Integration:** Implement step 1.8. Ensure the chatbot correctly uses the standard index and the user's agreement index based on session data. Test basic conversation flow. Add structured output parsing later if needed.
3.  **Memo Generation Core:** Implement step 1.9. Create the simple JSON template. Implement the core logic to load data, query indexes based on template hints, and assemble a basic memo structure. Focus on getting *some* output first, refinement comes later.
4.  **Frontend Setup:** Implement steps 2.1, 2.7, 2.8. Set up Next.js with `shadcn/ui`.
5.  **Frontend Auth Flow:** Implement the Login page (2.2) and AuthGuard (2.5). Ensure login sets the cookie and protected pages redirect correctly.
6.  **Frontend Core Features:** Implement the Memo Creation page (2.3) connecting standard selection and file upload to the backend API. Use `Toast` for feedback.
7.  **Frontend Chatbot UI:** Integrate the `ChatbotInterface.js` component on the creation page, connecting it to the backend chatbot API.
8.  **Frontend Memo Display:** Implement the Memo Display page (2.4), rendering the structure received from `/api/generate-memo`. Display evidence text initially.
9.  **PDF Viewer:** Integrate `PdfViewer.js` (2.4) potentially within a Dialog/Sheet triggered by clicking evidence. Solve how to securely access/display the user's uploaded PDF.
10. **Docker Integration:** Set up `docker-compose.yml` (Section 3). Test the full workflow within Docker Compose (`docker-compose up --build`).
11. **Refinement:** Improve error handling, loading states, LLM prompts for synthesis, and UI/UX based on testing.

This detailed plan provides a clear path for building the PoC, emphasizing better practices while remaining within the scope of a local demonstration. Remember to test each integration point carefully.
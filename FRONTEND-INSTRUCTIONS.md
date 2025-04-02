# Frontend Implementation Instructions

## Setup

1. **Create Next.js Project:**
   ```bash
   npx create-next-app frontend # Select TypeScript and Tailwind CSS
   cd frontend
   npx shadcn-ui@latest init
   npx shadcn-ui@latest add button input select card toast accordion dialog sheet label
   npm install axios react-pdf nookies
   ```

2. **Configure Environment:**
   Create `.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000`

## Project Structure

```
frontend/
├── components/              # UI components (auth, memo, pdf, chat)
├── pages/                   # Application pages
│   ├── index.tsx            # Login page
│   ├── create-memo.tsx      # Memo creation page
│   └── memo.tsx             # Memo display page
├── styles/                  # CSS and styling
```

## Core Components

1. **AuthGuard** - Checks session cookie and protects routes
2. **Login Page** - Handles authentication with HttpOnly cookies
3. **StandardSelect** - Dropdown for selecting accounting standard
4. **AgreementUpload** - File upload for merger agreement PDF
5. **ChatInterface** - Conversation UI with structured data extraction
6. **MemoDisplay** - Renders memo with sections and evidence
7. **PdfViewer** - Displays standard and agreement PDFs

## Implementation Steps

1. **Authentication Flow:**
   - Create login form that sends credentials to `/api/login`
   - Implement AuthGuard for protected pages
   - Handle session cookie management

2. **Memo Creation:**
   - Build standard selection and file upload components
   - Create chatbot interface for information gathering
   - Connect with backend APIs for data processing

3. **Memo Display:**
   - Design accordion-based section display
   - Create evidence snippet presentation
   - Implement PDF viewer with source document integration

## API Integration

All API calls must include `withCredentials: true` to send cookies:

```typescript
const response = await axios.post(
  `${process.env.NEXT_PUBLIC_API_URL}/api/endpoint`,
  data,
  { withCredentials: true }
);
```

## Key Features

1. **Authentication** - Session-based with HttpOnly cookies
2. **Standard Selection** - Choose between IFRS and ASC 805
3. **Agreement Upload** - Upload and process merger PDF
4. **Chatbot Interface** - Interactive assistant for information gathering
5. **Structured Data Extraction** - Parse key information from conversations
6. **Memo Generation** - Template-based memo creation
7. **Evidence Tracking** - Display source documents and references
8. **PDF Viewing** - Interactive PDF display with page navigation

## User Flow

1. User logs in → selects standard → uploads agreement
2. System generates initial memo and seeds follow-up questions
3. User answers questions via chat, providing missing information
4. System extracts structured data and regenerates improved memo
5. User reviews and accepts final memo 
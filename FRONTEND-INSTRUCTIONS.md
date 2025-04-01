# Frontend Implementation Instructions
## Business Combination Memo Generator

This document provides detailed instructions for implementing the frontend of the Business Combination Memo Generator application, which interacts with the existing backend API.

## Architecture Overview

The frontend should be implemented as a Next.js application with the following key features:

1. **Authentication Flow**
   - Login page with username/password form
   - Session management using HttpOnly cookies
   - Protected routes requiring authentication

2. **Core Functionality**
   - Standard selection (ASC 805 or IFRS)
   - Merger agreement PDF upload
   - Interactive chatbot interface
   - Structured memo generation and display
   - PDF evidence viewing

3. **UI Components**
   - Modern, clean interface using shadcn/ui and Tailwind CSS
   - Responsive design with appropriate loading states
   - Error handling and user feedback via toasts

## Technical Requirements

### Project Setup

```bash
# Create Next.js project
npx create-next-app frontend
cd frontend

# Install shadcn/ui and configure
npx shadcn-ui@latest init

# Install required components
npx shadcn-ui@latest add button input select card toast accordion dialog sheet label

# Install additional dependencies
npm install axios react-pdf nookies
```

### Environment Configuration

Create `.env.local` in the frontend directory:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Page Implementation Details

### 1. Login Page (`pages/index.js`)

**Purpose:** Authenticate users and establish a session.

**Implementation:**
- Create a login form with username and password fields
- On submission, send credentials to `/api/login`
- **Critical:** Configure Axios with `withCredentials: true` to handle cookies
- On successful login, redirect to `/create-memo`
- Show appropriate error messages for failed login attempts

```javascript
// Example login request
async function handleLogin(username, password) {
  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/login`, 
      { username, password },
      { withCredentials: true }
    );
    router.push('/create-memo');
  } catch (error) {
    toast({
      title: "Login Failed",
      description: error.response?.data?.detail || "Invalid credentials",
      variant: "destructive",
    });
  }
}
```

### 2. Memo Creation Page (`pages/create-memo.js`)

**Purpose:** Allow users to select a standard, upload a merger agreement, chat with the system, and generate a memo.

**Implementation:**
- Wrap with `AuthGuard` component for protection
- Implement a step-by-step flow:
  1. Standard selection dropdown (ASC 805 or IFRS)
  2. Merger agreement PDF file upload
  3. Chatbot interface
  4. Generate memo button

**Standard Selection Component:**
```javascript
async function handleStandardSelection(standard) {
  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/set-standard`,
      { standard },
      { withCredentials: true }
    );
    toast({
      title: "Standard Selected",
      description: `${standard} has been set as the active standard.`,
    });
    setSelectedStandard(standard);
  } catch (error) {
    toast({
      title: "Error",
      description: "Failed to set standard. Please try again.",
      variant: "destructive",
    });
  }
}
```

**Agreement Upload Component:**
```javascript
async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  setUploading(true);
  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/upload-agreement`,
      formData,
      { 
        withCredentials: true,
        headers: { 'Content-Type': 'multipart/form-data' }
      }
    );
    setUploading(false);
    setAgreementUploaded(true);
    toast({
      title: "Upload Successful",
      description: "Merger agreement has been uploaded and indexed.",
    });
  } catch (error) {
    setUploading(false);
    toast({
      title: "Upload Failed",
      description: error.response?.data?.detail || "Failed to upload agreement.",
      variant: "destructive",
    });
  }
}
```

### 3. Chatbot Interface Component (`components/ChatbotInterface.js`)

**Purpose:** Allow users to chat with the system about the standard and the agreement.

**Implementation:**
- Create a scrollable message list area
- Implement an input field with send button
- Store and display conversation history

```javascript
async function sendMessage(message) {
  if (!message.trim()) return;
  
  // Add user message to chat
  const newMessages = [...messages, { role: 'user', content: message }];
  setMessages(newMessages);
  setCurrentMessage('');
  
  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/chatbot`,
      { message },
      { withCredentials: true }
    );
    
    // Add AI response to chat
    setMessages([...newMessages, { role: 'assistant', content: response.data.response }]);
  } catch (error) {
    toast({
      title: "Error",
      description: "Failed to get response from chatbot.",
      variant: "destructive",
    });
  }
}
```

### 4. Memo Display Page (`pages/memo.js`)

**Purpose:** Display the generated memo in a structured format with evidence links.

**Implementation:**
- Wrap with `AuthGuard` component
- Use `Accordion` for collapsible memo sections
- Create a `Dialog` or `Sheet` component for PDF evidence display
- Implement a print/save function for the memo

```javascript
async function generateMemo() {
  setGenerating(true);
  try {
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL}/api/generate-memo`,
      {},
      { withCredentials: true }
    );
    setGenerating(false);
    router.push({
      pathname: '/memo',
      query: { memo: JSON.stringify(response.data.memo) }
    });
  } catch (error) {
    setGenerating(false);
    toast({
      title: "Generation Failed",
      description: "Failed to generate memo. Please try again.",
      variant: "destructive",
    });
  }
}
```

### 5. PDF Viewer Component (`components/PdfViewer.js`)

**Purpose:** Display uploaded PDF with evidence highlighting.

**Implementation:**
- Use `react-pdf` to render the PDF
- Create navigation controls for scrolling and zooming
- Highlight evidence passages when applicable

```javascript
// Example PDF viewer setup
import { Document, Page, pdfjs } from 'react-pdf';
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.js`;

function PdfViewer({ pdfUrl, targetPage = 1 }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(targetPage);
  
  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
    setPageNumber(targetPage);
  }
  
  // Render PDF viewer with navigation controls
  // ...
}
```

### 6. Authentication Guard Component (`components/AuthGuard.js`)

**Purpose:** Protect routes from unauthorized access.

**Implementation:**
- Check for existence of session cookie
- Redirect to login page if not authenticated
- Implement both client-side and server-side protection

```javascript
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import nookies from 'nookies';

export default function AuthGuard({ children }) {
  const router = useRouter();
  
  useEffect(() => {
    const cookies = nookies.get();
    if (!cookies.session_id) {
      router.push('/');
    }
  }, [router]);
  
  return <>{children}</>;
}

// For server-side protection in getServerSideProps
export async function getServerSideProps(context) {
  const cookies = nookies.get(context);
  
  if (!cookies.session_id) {
    return {
      redirect: {
        destination: '/',
        permanent: false,
      },
    };
  }
  
  return {
    props: {}, // will be passed to the page component as props
  };
}
```

## API Integration Reference

| Endpoint | Method | Request Body | Response | Purpose |
|----------|--------|--------------|----------|---------|
| `/api/login` | POST | `{ username, password }` | Sets HttpOnly cookie | Authenticate user |
| `/api/logout` | POST | None | Clears cookie | End user session |
| `/api/session` | GET | None | `{ selected_standard, agreement_uploaded, ... }` | Get session state |
| `/api/set-standard` | POST | `{ standard }` | Success message | Set accounting standard |
| `/api/upload-agreement` | POST | `FormData` with file | Success message | Upload merger agreement |
| `/api/chatbot` | POST | `{ message }` | `{ response, ... }` | Send chat message |
| `/api/generate-memo` | POST | None | `{ memo: {...} }` | Generate memo |

## Best Practices

1. **State Management**
   - Use React Context or state management library for application-wide state
   - Combine with local component state for UI-specific behavior

2. **Error Handling**
   - Implement global error handling for API requests
   - Use toast notifications for user feedback
   - Create fallback UIs for failed states

3. **Loading States**
   - Show loading indicators during async operations
   - Disable buttons while operations are in progress
   - Implement skeleton loaders where appropriate

4. **Responsive Design**
   - Ensure the application works on desktop and tablet devices
   - Use Tailwind's responsive classes for breakpoints
   - Test on different screen sizes

5. **Accessibility**
   - Use semantic HTML elements
   - Ensure keyboard navigation works
   - Add ARIA attributes where needed
   - Test with screen readers

## Docker Integration

The frontend is configured to run in Docker alongside the backend:

```yaml
# docker-compose.yml (frontend service)
frontend:
  build: ./frontend
  command: npm run dev
  volumes:
    - ./frontend:/app
    - /app/node_modules
  environment:
    - NEXT_PUBLIC_API_URL=http://backend:8000
    - WATCHPACK_POLLING=true
  depends_on:
    - backend
  ports:
    - "3000:3000"
```

## Implementation Order

1. Create project structure and install dependencies
2. Implement authentication (login page and guards)
3. Create the memo creation page with standard selection
4. Implement file upload functionality
5. Develop the chatbot interface
6. Build the memo display page
7. Add the PDF viewer component
8. Style the application with shadcn/ui and Tailwind
9. Test and refine the user experience

## Testing

1. Test authentication with valid and invalid credentials
2. Verify session persistence across page reloads
3. Test standard selection and state management
4. Verify file upload with various PDF sizes
5. Test chatbot conversation flow
6. Verify memo generation and display
7. Test PDF viewing and evidence highlighting
8. Verify all error states and handlers

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [React-PDF Documentation](https://github.com/wojtekmaj/react-pdf) 
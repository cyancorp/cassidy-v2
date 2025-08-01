import { useState, useEffect, useCallback } from 'react';
import ContextPanel from './components/ContextPanel';
import ChatInterface from './components/ChatInterface';
import LoginForm from './components/LoginForm';
import JournalEntries from './components/JournalEntries';
import TaskManagerSimple from './components/TaskManagerSimple';
import Header from './components/Header';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Message, UserTemplate } from './types'; // <-- Import UserTemplate
import { v4 as uuidv4 } from 'uuid';

// API URL configuration - prioritize environment variables for local dev, then window.ENV for deployed version
const API_BASE_URL = (() => {
  // For local development with Vite
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // For deployed version with env-config.js
  if (typeof window !== 'undefined' && (window as any).ENV?.REACT_APP_API_URL) {
    return (window as any).ENV.REACT_APP_API_URL;
  }
  
  // Default to localhost for local development
  if (import.meta.env.DEV) {
    return 'http://localhost:8000/api/v1';
  }
  
  // Fallback for production
  return 'https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1';
})();

// Define expected response structure for agent endpoint
interface AgentApiResponse {
    text: string;
    session_id: string;
    updated_draft_data?: any;
    tool_calls?: any[];
    metadata?: any;
}

// Define UserPreferences type properly (mirror backend)
interface UserPreferences {
    user_id?: string; // Assuming default_user for now
    purpose_statement: string | null;
    known_challenges: string[];
    personal_glossary: { [key: string]: string };
    long_term_goals?: string[]; // <-- Add long_term_goals here too for consistency
    // Add other fields from models.UserPreferences as needed
}

function MainApp() {
  const { isAuthenticated, getAuthHeaders, logout, username } = useAuth();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [structuredContent, setStructuredContent] = useState<any>(null);
  const [, setUserTemplate] = useState<UserTemplate | null>(null); // <-- Add template state
  const [debugInfo, setDebugInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUserPrefs, setCurrentUserPrefs] = useState<UserPreferences | null>(null); // State for full prefs object
  const [currentView, setCurrentView] = useState<'chat' | 'journal' | 'tasks'>('chat');

  // Function to clear local state on reset
  const clearLocalState = () => {
    setMessages([]);
    setStructuredContent(null);
    setDebugInfo(null);
    setCurrentUserPrefs(null); // Clear prefs state
    setUserTemplate(null); // <-- Clear template on reset
    setError(null);
  };

  // Function to fetch preferences and set initial message
  const initializeApp = useCallback(async (_currentSessionId: string) => {
      setError(null);
      setIsLoading(true);
      try {
          const prefsResponse = await fetch(`${API_BASE_URL}/user/preferences`, {
              headers: getAuthHeaders()
          });
          let initialMessageContent = "";
          let prefsFoundAndValid = false;

          if (prefsResponse.ok) {
              const prefs: UserPreferences = await prefsResponse.json();
              setCurrentUserPrefs(prefs); // <-- Store full prefs object
              console.log("Loaded user preferences:", prefs);
              if (prefs.purpose_statement) {
                  initialMessageContent = `Welcome back, ${username}! What's on your mind today?`;
                  prefsFoundAndValid = true;
              } else {
                   console.log("Preferences loaded, but no purpose set. Starting onboarding.");
              }
          } else {
              console.log("User preferences not found or fetch error. Starting onboarding.");
              setCurrentUserPrefs(null); // Ensure prefs state is null if fetch fails
          }
          
          // Fetch Template
          try {
            const templateResponse = await fetch(`${API_BASE_URL}/user/template`, {
                headers: getAuthHeaders()
            });
            if (templateResponse.ok) {
                const templateData: UserTemplate = await templateResponse.json();
                setUserTemplate(templateData);
                console.log("Loaded user template:", templateData);
            } else {
                console.error("Failed to fetch user template:", templateResponse.status);
                // Decide if this is a fatal error or can proceed without template
                setUserTemplate(null);
            }
          } catch (templateErr: any) {
              console.error("Error fetching user template:", templateErr);
              setUserTemplate(null); // Proceed without template on error
          }
          
          if (!prefsFoundAndValid) {
              initialMessageContent = "Welcome! To start, could you tell me a bit about why you're using this tool and what you hope to achieve?";
          }
          
          setMessages([
              {
                  id: uuidv4(),
                  role: 'assistant',
                  content: initialMessageContent,
                  timestamp: new Date(),
              }
          ]);
          
      } catch (err: any) {
          console.error("Error during app initialization:", err);
          setError(`Initialization failed: ${err.message}`);
          setCurrentUserPrefs(null); // Ensure prefs state is null on error
          setUserTemplate(null); // <-- Clear template on error
          setMessages([
              {
                  id: uuidv4(),
                  role: 'assistant',
                  content: "Hello! I encountered an issue starting up, but you can try sending a message.",
                  timestamp: new Date(),
              }
          ]);
      } finally {
          setIsLoading(false);
      }
  }, [getAuthHeaders, username]); // end initializeApp

  // Effect to start session and initialize
  useEffect(() => {
    const startSessionAndInit = async () => {
        if (sessionId) return; // Don't restart if already have ID

        setIsLoading(true);
        setError(null);
        try {
            // Create a new session via the backend API
            const sessionResponse = await fetch(`${API_BASE_URL}/sessions`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ 
                    conversation_type: "journaling",
                    metadata: {}
                })
            });
            
            if (!sessionResponse.ok) {
                throw new Error(`Failed to create session: ${sessionResponse.status}`);
            }
            
            const sessionData = await sessionResponse.json();
            const newSessionId = sessionData.session_id;
            setSessionId(newSessionId);
            console.log('Chat session created:', newSessionId);
            
            // Now initialize based on preferences
            await initializeApp(newSessionId); 
        } catch (err: any) {
            console.error("Error starting session:", err);
            setError(`Failed to start session: ${err.message}`);
            setIsLoading(false); // Stop loading on fatal error
        }
        // setIsLoading is handled within initializeApp for the second phase
    };

    startSessionAndInit();
  }, [sessionId, initializeApp]); // Depend on sessionId and initializeApp

  const handleSendMessage = async (text: string) => {
    if (!sessionId) {
        setError("Session not started yet. Cannot send message.");
        return;
    }
    console.log(`[${sessionId}] Sending message to agent:`, text);
    const userMessage: Message = {
        id: uuidv4(),
        role: 'user',
        content: text,
        timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setError(null);
    setIsLoading(true);

    try {
        // Use the agent chat endpoint instead of session endpoint
        const response = await fetch(`${API_BASE_URL}/agent/chat/${sessionId}`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ text: text }), 
        });

        if (!response.ok) {
            const errorBody = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, body: ${errorBody}`);
        }

        const data: AgentApiResponse = await response.json(); 
        console.log('Received agent response:', data);

        const aiResponseText = data.text || "(No response received)";
        const structuredData = data.updated_draft_data || null;
        
        // Debug info includes tool calls and metadata
        const debugData = {
            tool_calls: data.tool_calls || [],
            metadata: data.metadata || {}
        };

        const aiMessage: Message = {
            id: uuidv4(),
            role: 'assistant',
            content: aiResponseText,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, aiMessage]);
        setStructuredContent(structuredData);
        setDebugInfo(debugData);

    } catch (err: any) {
        console.error("Error processing message with agent:", err);
        setError(`Failed to process message: ${err.message}`);
    } finally {
        setIsLoading(false);
    }
  };

  // --- New Chat Handler ---
  const handleNewChat = async () => {
    clearLocalState();
    setSessionId(null);
    // Trigger re-initialization with new session
    await initializeApp('');
  };

  // --- Reset Preferences Handler ---
  const handleResetPreferences = async () => {
      if (!confirm("Are you sure you want to reset all preferences and restart the onboarding conversation?")) {
          return;
      }
      console.log("Resetting preferences...");
      setIsLoading(true);
      setError(null);
      try {
          // --- Call backend reset endpoint --- 
          const resetResponse = await fetch(`${API_BASE_URL}/user/reset`, { 
              method: 'POST',
              headers: getAuthHeaders()
          });
          if (!resetResponse.ok) { // Check for non-2xx status codes
              let errorBody = 'Unknown error';
              try {
                  errorBody = await resetResponse.text(); // Try to get error detail
              } catch {}
              throw new Error(`Failed to reset preferences on backend: ${resetResponse.status} ${errorBody}`);
          }
          // --- END API Call ---
          
          // No longer need simulated delay
          console.log("Preferences reset successfully on backend.");

          // Clear local state and trigger re-initialization
          clearLocalState(); // This now clears currentUserPrefs too
          setUserTemplate(null); // <-- Clear template on reset
          if (sessionId) {
              // Pass the current session ID to avoid starting a new one necessarily
              await initializeApp(sessionId); 
          } else {
              // If session ID was lost, trigger full restart
              setSessionId(null); 
          }
          
      } catch (err: any) {
          console.error("Error resetting preferences:", err);
          setError(`Failed to reset preferences: ${err.message}`);
      } finally {
          setIsLoading(false);
      }
  };

  // --- Conditional Rendering Logic (Simplified) ---
  // Show loading only during initial session start
  if (isLoading && !sessionId) {
       return (
         <div className="flex items-center justify-center h-screen bg-neutral-50">
           <div className="text-neutral-600 font-medium">Starting session...</div>
         </div>
       );
  }
  // Show fatal error only if session start failed
  if (error && !sessionId) {
      return (
        <div className="flex items-center justify-center h-screen bg-neutral-50">
          <div className="text-error font-medium">Error: {error}</div>
        </div>
      );
  }
  // Show login form if not authenticated
  if (!isAuthenticated) {
    return <div className="bg-neutral-50 min-h-screen">Please log in to continue...</div>;
  }

  // Always render main UI once session ID exists, initial message handles onboarding state

  const generalErrorDisplay = error ? (
      <div className="bg-error/10 border border-error/20 text-error px-4 py-3 rounded-lg relative m-4 shadow-soft" role="alert">
          <strong className="font-semibold">Error:</strong>
          <span className="block sm:inline ml-1">{error}</span>
          <button onClick={() => setError(null)} className="absolute top-2 right-2 text-error hover:text-error/80 p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
      </div>
  ) : null;

  return (
    <div className="flex flex-col h-screen bg-neutral-50">
      <Header 
        currentView={currentView}
        onViewChange={setCurrentView}
        onNewChat={handleNewChat}
      />
      
      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
          {currentView === 'chat' && (
            <>
              <div className="flex-1 flex flex-col bg-white">
                {generalErrorDisplay}
                <ChatInterface 
                  messages={messages} 
                  onSendMessage={handleSendMessage} 
                  isLoading={isLoading && messages.length > 0} // Show loading only after initial messages
                />
              </div>
              <div className="w-96 bg-neutral-50 border-l border-neutral-200 overflow-y-auto">
                <ContextPanel 
                  structuredContent={structuredContent} 
                  debugInfo={debugInfo} 
                  userPreferences={currentUserPrefs}
                />
              </div>
            </>
          )}
          
          {currentView === 'journal' && (
            <div className="flex-1 bg-white">
              <JournalEntries onClose={() => setCurrentView('chat')} />
            </div>
          )}
          
          {currentView === 'tasks' && (
            <div className="flex-1 bg-white">
              <TaskManagerSimple onClose={() => setCurrentView('chat')} />
            </div>
          )}
      </div>
    </div>
  );
}

// Main App component with authentication
function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}

// Component that handles authentication state
function AuthenticatedApp() {
  const { isAuthenticated, login } = useAuth();
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = async (token: string, username: string) => {
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      login(token, username);
    } catch (err: any) {
      setLoginError(err.message);
    } finally {
      setIsLoggingIn(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <LoginForm 
        onLogin={handleLogin}
        isLoading={isLoggingIn}
        error={loginError}
      />
    );
  }

  return <MainApp />;
}

export default App;

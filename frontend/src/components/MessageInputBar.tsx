import React, { useState, useEffect, useRef } from 'react';

// --- Type Definitions for Web Speech API (if not available globally) ---
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string; // This might vary based on browser, use string for simplicity
  readonly message: string;
}

interface SpeechRecognitionStatic {
  new(): SpeechRecognition;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => any) | null;
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => any) | null;
  onend: ((this: SpeechRecognition, ev: Event) => any) | null;
  start(): void;
  stop(): void;
}

// Add types to window
declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionStatic;
    webkitSpeechRecognition?: SpeechRecognitionStatic;
  }
}
// --- End Type Definitions ---


// Attempt to get the SpeechRecognition object, handling vendor prefixes
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const browserSupportsSpeechRecognition = !!SpeechRecognition;

interface MessageInputBarProps {
  onSendMessage: (text: string) => void;
  isLoading: boolean;
}

const MessageInputBar: React.FC<MessageInputBarProps> = ({ onSendMessage, isLoading }) => {
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const finalTranscriptRef = useRef<string>('');

  const startListening = () => {
    if (!browserSupportsSpeechRecognition || !SpeechRecognition) {
      console.error("Speech recognition not supported or not found.");
      return;
    }
    if (isListening) return;

    console.log("Starting speech recognition...");
    finalTranscriptRef.current = '';
    setInputText('');
    
    recognitionRef.current = new SpeechRecognition();
    recognitionRef.current.continuous = true;
    recognitionRef.current.interimResults = true;
    recognitionRef.current.lang = 'en-US';

    recognitionRef.current.onresult = (event: SpeechRecognitionEvent) => {
      let interimTranscript = '';
      let latestFinalTranscriptPart = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
            latestFinalTranscriptPart += transcriptPart.trim() + ' ';
        } else {
            interimTranscript += transcriptPart;
        }
      }
      
      if(latestFinalTranscriptPart) {
          finalTranscriptRef.current += latestFinalTranscriptPart;
      }
      
      setInputText(finalTranscriptRef.current + interimTranscript);
    };

    recognitionRef.current.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
      finalTranscriptRef.current = '';
      recognitionRef.current = null;
    };

    recognitionRef.current.onend = (_event: Event) => {
        console.log("Speech recognition ended.");
        if (recognitionRef.current) {
             recognitionRef.current = null; 
        }
        if (isListening) {
             setIsListening(false);
        }
    };

    recognitionRef.current.start();
    setIsListening(true);
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      console.log("Stopping speech recognition manually...");
      recognitionRef.current.stop(); 
    }
    setIsListening(false);
  };

  const handleMicClick = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
          recognitionRef.current.stop();
      }
    };
  }, []);

  const handleSubmit = (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (isListening) {
        stopListening(); 
    }
    const textToSubmit = inputText.trim();
    if (textToSubmit && !isLoading) {
      onSendMessage(textToSubmit);
      setInputText('');
      finalTranscriptRef.current = '';
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  const micDisabled = !browserSupportsSpeechRecognition || isLoading;

  return (
    <form onSubmit={handleSubmit} className="p-4 border-t border-neutral-200 bg-white">
      <div className="flex items-center space-x-3">
        <textarea
          className="flex-1 p-3 border border-neutral-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 shadow-soft text-sm bg-neutral-50 placeholder-neutral-400"
          rows={1}
          placeholder="Type or click the mic to speak..."
          value={inputText}
          onChange={(e) => {
              setInputText(e.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          type="button"
          onClick={handleMicClick}
          disabled={micDisabled}
          className={`p-2.5 rounded-xl transition-all duration-150 ${micDisabled ? 'text-neutral-400 bg-neutral-100 cursor-not-allowed' : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700'} ${isListening ? 'bg-error/10 text-error hover:bg-error/20 animate-pulse' : ''}`}
          title={isListening ? "Stop listening" : "Start listening"}
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} className="w-5 h-5">
            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
          </svg>
        </button>
        <button
          type="submit"
          className={`px-5 py-2.5 rounded-xl text-white text-sm font-medium transition-all duration-150 shadow-soft ${isLoading || isListening ? 'bg-neutral-400 cursor-not-allowed' : 'bg-primary-600 hover:bg-primary-700 hover:shadow-medium'}`}
          disabled={isLoading || isListening}
        >
          Send
        </button>
      </div>
      {!browserSupportsSpeechRecognition && (
          <p className="text-xs text-error mt-1">Speech recognition not supported by your browser.</p>
      )}
    </form>
  );
};

export default MessageInputBar; 
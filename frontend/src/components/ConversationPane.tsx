import React, { useRef, useEffect } from 'react';
import UserMessage from './UserMessage';
import AIMessage from './AIMessage';
import { Message } from '../types';

interface ConversationPaneProps {
  messages: Message[];
  isLoading: boolean;
}

const ConversationPane: React.FC<ConversationPaneProps> = ({ messages, isLoading }) => {
  const endOfMessagesRef = useRef<null | HTMLDivElement>(null);

  const scrollToBottom = () => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  useEffect(() => {
    // Scroll to bottom when messages change
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-neutral-50">
      {messages.map((msg) => (
        msg.role === 'user' ? (
          <UserMessage key={msg.id} message={msg} />
        ) : (
          <AIMessage key={msg.id} message={msg} />
        )
      ))}
      {isLoading && (
        <div className="flex justify-center py-4">
          <div className="flex items-center space-x-2 text-neutral-500">
            <div className="animate-pulse-slow">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <circle cx="10" cy="10" r="3" />
              </svg>
            </div>
            <span className="text-sm italic">AI is thinking...</span>
          </div>
        </div>
      )}
      {/* Empty div to target for scrolling */}
      <div ref={endOfMessagesRef} />
    </div>
  );
};

export default ConversationPane; 
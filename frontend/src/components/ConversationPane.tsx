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
    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-100">
      {messages.map((msg) => (
        msg.role === 'user' ? (
          <UserMessage key={msg.id} message={msg} />
        ) : (
          <AIMessage key={msg.id} message={msg} />
        )
      ))}
      {isLoading && (
        <div className="flex justify-center py-2">
            <div className="text-gray-500 italic">AI is thinking...</div>
        </div>
      )}
      {/* Empty div to target for scrolling */}
      <div ref={endOfMessagesRef} />
    </div>
  );
};

export default ConversationPane; 
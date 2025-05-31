import React from 'react';
import ConversationPane from './ConversationPane';
import MessageInputBar from './MessageInputBar';
import { Message } from '../types';

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (text: string) => void;
  isLoading: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSendMessage, isLoading }) => {
  return (
    <div className="flex flex-col h-full bg-gray-50">
      <ConversationPane messages={messages} isLoading={isLoading} />
      <MessageInputBar onSendMessage={onSendMessage} isLoading={isLoading} />
    </div>
  );
};

export default ChatInterface; 
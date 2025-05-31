import React from 'react';
import { Message } from '../types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface AIMessageProps {
  message: Message;
}

const AIMessage: React.FC<AIMessageProps> = ({ message }) => {
  return (
    <div className="flex justify-start">
      <div className="bg-white text-gray-800 p-3 rounded-xl shadow-md max-w-md lg:max-w-lg">
        <div className="text-sm markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
        {/* Optional: Add timestamp here */}
      </div>
    </div>
  );
};

export default AIMessage; 
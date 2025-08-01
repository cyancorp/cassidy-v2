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
      <div className="bg-white text-neutral-800 p-4 rounded-2xl shadow-soft border border-neutral-200 max-w-md lg:max-w-lg animate-slide-up">
        <div className="text-sm markdown-content leading-relaxed">
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
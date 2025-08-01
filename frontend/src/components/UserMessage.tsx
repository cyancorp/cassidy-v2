import React from 'react';
import { Message } from '../types';

interface UserMessageProps {
  message: Message;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div className="flex justify-end">
      <div className="bg-gradient-primary text-white p-4 rounded-2xl shadow-soft max-w-md lg:max-w-lg animate-slide-up">
        <p className="text-sm leading-relaxed">{message.content}</p>
        {/* Optional: Add timestamp here */}
      </div>
    </div>
  );
};

export default UserMessage; 
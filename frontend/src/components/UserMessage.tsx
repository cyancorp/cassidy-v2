import React from 'react';
import { Message } from '../types';

interface UserMessageProps {
  message: Message;
}

const UserMessage: React.FC<UserMessageProps> = ({ message }) => {
  return (
    <div className="flex justify-end">
      <div className="bg-blue-600 text-white p-3 rounded-xl shadow-md max-w-md lg:max-w-lg">
        <p className="text-sm">{message.content}</p>
        {/* Optional: Add timestamp here */}
      </div>
    </div>
  );
};

export default UserMessage; 
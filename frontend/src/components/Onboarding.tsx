import React, { useState } from 'react';

interface OnboardingProps {
  onComplete: (purpose: string) => void;
}

const Onboarding: React.FC<OnboardingProps> = ({ onComplete }) => {
  const [purpose, setPurpose] = useState('');

  const handleSubmit = () => {
    if (purpose.trim()) {
      onComplete(purpose.trim());
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-gradient-to-br from-indigo-100 via-white to-cyan-100">
      <div className="bg-white p-8 rounded-lg shadow-xl max-w-lg text-center">
        <h1 className="text-3xl font-bold text-gray-800 mb-4">Welcome!</h1>
        <p className="text-gray-600 mb-6">
          To help tailor this experience to you, please tell us briefly what you hope to achieve by using this tool.
          Are you looking to organize thoughts, achieve specific goals, track progress, or something else?
        </p>
        <textarea
          className="w-full p-3 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 shadow-sm text-sm mb-6"
          rows={4}
          placeholder="e.g., Organize my work projects, track my fitness goals, journal my daily thoughts..."
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
        />
        <button
          onClick={handleSubmit}
          disabled={!purpose.trim()}
          className={`w-full px-6 py-3 rounded-lg text-white font-medium transition-colors duration-150 ${!purpose.trim() ? 'bg-gray-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default Onboarding; 
import React from 'react';

// Assume UserPreferences type is defined elsewhere (e.g., App.tsx or types.ts)
// If needed, duplicate or import the UserPreferences interface here
interface UserPreferences {
    user_id?: string;
    purpose_statement: string | null;
    known_challenges: string[];
    personal_glossary: { [key: string]: string };
    long_term_goals?: string[];
}

interface ContextPanelProps {
  structuredContent: any; 
  debugInfo: any; 
  userPreferences: UserPreferences | null; // <-- Add prop
}

const ContextPanel: React.FC<ContextPanelProps> = ({ structuredContent, debugInfo, userPreferences }) => {
  
  const renderList = (items: string[] | undefined | null, title: string) => {
      if (!items || items.length === 0) {
          return <p className="text-xs text-neutral-500 italic">{title}: None specified.</p>;
      }
      return (
          <div>
              <h4 className="text-xs font-semibold text-neutral-600 mb-1">{title}:</h4>
              <ul className="list-disc list-inside pl-2 space-y-1">
                  {items.map((item, index) => (
                      <li key={index} className="text-sm text-neutral-700">{item}</li>
                  ))}
              </ul>
          </div>
      );
  };

  const renderGlossary = (glossary: { [key: string]: string } | undefined | null) => {
      if (!glossary || Object.keys(glossary).length === 0) {
          return <p className="text-xs text-neutral-500 italic">Glossary: Empty.</p>;
      }
      return (
          <div>
              <h4 className="text-xs font-semibold text-neutral-600 mb-1">Glossary:</h4>
              <div className="space-y-1 pl-2">
                  {Object.entries(glossary).map(([key, value]) => (
                      <p key={key} className="text-sm text-neutral-700"><span className="font-medium">{key}:</span> {value}</p>
                  ))}
              </div>
          </div>
      );
  };
    
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-xl font-display font-semibold text-neutral-800 mb-4">Context</h2>
      
      {/* Display User Preferences */}
      <div className="mb-6 bg-primary-50 p-4 rounded-xl shadow-soft space-y-3">
          <h3 className="font-semibold text-primary-800 mb-2">User Preferences</h3>
          <p className="text-sm text-neutral-700">
              <span className="font-semibold">Goal:</span> {userPreferences?.purpose_statement || <span className="text-neutral-500 italic">Not set.</span>}
          </p>
          {renderList(userPreferences?.known_challenges, "Challenges")}
          {renderList(userPreferences?.long_term_goals, "Long-Term Goals")}
          {renderGlossary(userPreferences?.personal_glossary)}
      </div>
      
      {/* Display Last Turn's Structured Content */}
      <div className="mb-6">
        <h3 className="font-semibold text-neutral-700 mb-2">Structured from Last Entry</h3>
        <pre className="bg-neutral-100 p-4 rounded-lg text-sm text-neutral-800 overflow-x-auto shadow-soft font-mono">
          {structuredContent ? JSON.stringify(structuredContent, null, 2) : <span className="text-neutral-500 italic">No data from last entry.</span>}
        </pre>
      </div>
      
      {/* Display Debug Info */}
      <div>
        <h3 className="font-semibold text-neutral-700 mb-2">Debug Info</h3>
        <pre className="bg-neutral-100 p-4 rounded-lg text-sm text-neutral-800 overflow-x-auto shadow-soft font-mono">
          {debugInfo ? JSON.stringify(debugInfo, null, 2) : <span className="text-neutral-500 italic">No data yet.</span>}
        </pre>
      </div>
    </div>
  );
};

export default ContextPanel; 
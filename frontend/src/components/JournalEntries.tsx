import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { format } from 'date-fns';

// API URL configuration (reuse from App.tsx)
const API_BASE_URL = (() => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && (window as any).ENV?.REACT_APP_API_URL) {
    return (window as any).ENV.REACT_APP_API_URL;
  }
  if (import.meta.env.DEV) {
    return 'http://localhost:8000/api/v1';
  }
  return 'https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1';
})();

interface JournalEntry {
  id: string;
  session_id: string;
  created_at: string;
  raw_text: string;
  structured_data: {
    [sectionName: string]: string | string[] | any;
  };
  metadata: any;
}

interface JournalEntriesProps {
  onClose: () => void;
}

export default function JournalEntries({ onClose }: JournalEntriesProps) {
  const { getAuthHeaders } = useAuth();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJournalEntries();
  }, []);

  const fetchJournalEntries = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/journal-entries`, {
        headers: getAuthHeaders()
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch journal entries: ${response.status}`);
      }
      
      const data = await response.json();
      setEntries(data);
    } catch (err: any) {
      console.error('Error fetching journal entries:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const renderStructuredData = (data: JournalEntry['structured_data']) => {
    if (!data || Object.keys(data).length === 0) {
      return <p className="text-gray-500">No structured data available</p>;
    }

    // Define color schemes for different section types
    const getSectionColor = (sectionName: string) => {
      const name = sectionName.toLowerCase();
      if (name.includes('emotion') || name.includes('mood') || name.includes('feeling')) {
        return { bg: 'bg-blue-50', text: 'text-blue-900', content: 'text-blue-800', secondary: 'text-blue-600' };
      } else if (name.includes('event') || name.includes('daily') || name.includes('activity')) {
        return { bg: 'bg-green-50', text: 'text-green-900', content: 'text-green-800', secondary: 'text-green-600' };
      } else if (name.includes('trading') || name.includes('market')) {
        return { bg: 'bg-indigo-50', text: 'text-indigo-900', content: 'text-indigo-800', secondary: 'text-indigo-600' };
      } else if (name.includes('todo') || name.includes('to do') || name.includes('goals') || name.includes('plan')) {
        return { bg: 'bg-yellow-50', text: 'text-yellow-900', content: 'text-yellow-800', secondary: 'text-yellow-600' };
      } else if (name.includes('done') || name.includes('completed') || name.includes('accomplish')) {
        return { bg: 'bg-purple-50', text: 'text-purple-900', content: 'text-purple-800', secondary: 'text-purple-600' };
      } else if (name.includes('reflection') || name.includes('insight') || name.includes('thought')) {
        return { bg: 'bg-pink-50', text: 'text-pink-900', content: 'text-pink-800', secondary: 'text-pink-600' };
      } else {
        return { bg: 'bg-gray-50', text: 'text-gray-900', content: 'text-gray-800', secondary: 'text-gray-600' };
      }
    };

    const renderSectionContent = (content: any) => {
      if (Array.isArray(content)) {
        return (
          <ul className="list-disc list-inside space-y-1">
            {content.map((item, idx) => (
              <li key={idx} className="break-words">{item}</li>
            ))}
          </ul>
        );
      } else if (typeof content === 'string') {
        return <p className="break-words">{content}</p>;
      } else if (typeof content === 'object' && content !== null) {
        return (
          <div className="space-y-2">
            {Object.entries(content).map(([key, value]) => (
              <div key={key}>
                <span className="font-medium">{key}:</span> {Array.isArray(value) ? value.join(', ') : String(value)}
              </div>
            ))}
          </div>
        );
      } else {
        return <p>{String(content)}</p>;
      }
    };

    return (
      <div className="space-y-4">
        {Object.entries(data).map(([sectionName, content]) => {
          const colors = getSectionColor(sectionName);
          return (
            <div key={sectionName} className={`${colors.bg} p-3 rounded-lg border`}>
              <h4 className={`font-semibold ${colors.text} mb-2`}>{sectionName}</h4>
              <div className={colors.content}>
                {renderSectionContent(content)}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg w-full max-w-6xl h-5/6 flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-2xl font-bold">Your Journal Entries</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Entry List */}
          <div className="w-1/3 border-r overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">Loading...</div>
            ) : error ? (
              <div className="p-4 text-center text-red-500">Error: {error}</div>
            ) : entries.length === 0 ? (
              <div className="p-4 text-center text-gray-500">No journal entries yet</div>
            ) : (
              <div className="divide-y">
                {entries.map((entry) => (
                  <div
                    key={entry.id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`p-4 cursor-pointer hover:bg-gray-50 ${
                      selectedEntry?.id === entry.id ? 'bg-blue-50' : ''
                    }`}
                  >
                    <div className="font-semibold text-gray-900">
                      {format(new Date(entry.created_at), 'MMM d, yyyy')}
                    </div>
                    <div className="text-sm text-gray-600 mt-1">
                      {format(new Date(entry.created_at), 'h:mm a')}
                    </div>
                    {/* Show a preview of the structured data sections */}
                    {entry.structured_data && Object.keys(entry.structured_data).length > 0 && (
                      <div className="text-xs text-gray-500 mt-2">
                        Sections: {Object.keys(entry.structured_data).slice(0, 3).join(', ')}
                        {Object.keys(entry.structured_data).length > 3 && '...'}
                      </div>
                    )}
                    <div className="text-sm text-gray-500 mt-1 line-clamp-2">
                      {entry.raw_text ? entry.raw_text.substring(0, 100) + (entry.raw_text.length > 100 ? '...' : '') : 'No raw text'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Entry Detail */}
          <div className="flex-1 overflow-y-auto p-6">
            {selectedEntry ? (
              <div>
                <div className="mb-6">
                  <h3 className="text-xl font-semibold mb-2">
                    {format(new Date(selectedEntry.created_at), 'MMMM d, yyyy - h:mm a')}
                  </h3>
                </div>

                <div className="mb-6">
                  <h4 className="font-semibold text-gray-700 mb-2">Journal Entry</h4>
                  <div className="bg-gray-50 p-4 rounded whitespace-pre-wrap">
                    {selectedEntry.raw_text}
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-gray-700 mb-3">Structured Insights</h4>
                  {renderStructuredData(selectedEntry.structured_data)}
                </div>
              </div>
            ) : (
              <div className="text-center text-gray-500 mt-20">
                Select a journal entry to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
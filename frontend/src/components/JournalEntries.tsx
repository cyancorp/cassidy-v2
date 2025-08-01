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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-6xl h-[90vh] flex flex-col shadow-large animate-fade-in">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-neutral-200">
          <h2 className="text-2xl font-display font-bold text-neutral-900">Your Journal Entries</h2>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-700 p-2 hover:bg-neutral-100 rounded-lg transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Entry List */}
          <div className="w-1/3 border-r border-neutral-200 overflow-y-auto bg-neutral-50">
            {isLoading ? (
              <div className="p-4 text-center text-neutral-500">Loading...</div>
            ) : error ? (
              <div className="p-4 text-center text-error">Error: {error}</div>
            ) : entries.length === 0 ? (
              <div className="p-4 text-center text-neutral-500">No journal entries yet</div>
            ) : (
              <div className="divide-y divide-neutral-200">
                {entries.map((entry) => (
                  <div
                    key={entry.id}
                    onClick={() => setSelectedEntry(entry)}
                    className={`p-4 cursor-pointer transition-colors ${
                      selectedEntry?.id === entry.id 
                        ? 'bg-primary-100 border-l-4 border-primary-500' 
                        : 'hover:bg-white'
                    }`}
                  >
                    <div className="font-semibold text-neutral-900">
                      {format(new Date(entry.created_at), 'MMM d, yyyy')}
                    </div>
                    <div className="text-sm text-neutral-600 mt-1">
                      {format(new Date(entry.created_at), 'h:mm a')}
                    </div>
                    {/* Show a preview of the structured data sections */}
                    {entry.structured_data && Object.keys(entry.structured_data).length > 0 && (
                      <div className="text-xs text-neutral-500 mt-2">
                        Sections: {Object.keys(entry.structured_data).slice(0, 3).join(', ')}
                        {Object.keys(entry.structured_data).length > 3 && '...'}
                      </div>
                    )}
                    <div className="text-sm text-neutral-600 mt-1 line-clamp-2">
                      {entry.structured_data?.Summary || 
                       (entry.raw_text ? entry.raw_text.substring(0, 100) + (entry.raw_text.length > 100 ? '...' : '') : 'No content available')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Entry Detail */}
          <div className="flex-1 overflow-y-auto p-6 bg-white">
            {selectedEntry ? (
              <div className="animate-fade-in">
                <div className="mb-6">
                  <h3 className="text-xl font-display font-semibold mb-2 text-neutral-900">
                    {format(new Date(selectedEntry.created_at), 'MMMM d, yyyy - h:mm a')}
                  </h3>
                </div>

                <div className="mb-6">
                  <h4 className="font-semibold text-neutral-700 mb-3">Original Entry</h4>
                  <div className="bg-neutral-50 p-4 rounded-xl whitespace-pre-wrap text-neutral-700 border border-neutral-200">
                    {selectedEntry.raw_text}
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold text-neutral-700 mb-3">Structured Insights</h4>
                  {renderStructuredData(selectedEntry.structured_data)}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-neutral-500">
                  <svg className="w-16 h-16 mx-auto mb-4 text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  <p>Select a journal entry to view details</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
import React, { useState } from 'react';
import { http } from '../../http';

interface PortfolioAIChatProps {
  portfolioId: number;
}

interface PortfolioAnalysisResponse {
  payload?: {
    answer?: string;
  };
}

const QUICK_ACTIONS = [
  'Gdzie są największe ryzyka?',
  'Co warto dokupić?',
  'Co rozważyć do sprzedaży?',
];

const PortfolioAIChat: React.FC<PortfolioAIChatProps> = ({ portfolioId }) => {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submitQuestion = async (value: string) => {
    const trimmed = value.trim();

    if (!trimmed || loading) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await http.post<PortfolioAnalysisResponse>('/api/ai/portfolio-analysis', {
        portfolio_id: portfolioId,
        question: trimmed,
      });

      setAnswer(response.payload?.answer ?? 'Brak odpowiedzi od AI.');
    } catch (err) {
      console.error('Failed to fetch AI portfolio analysis', err);
      setError('Nie udało się pobrać odpowiedzi AI. Spróbuj ponownie.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submitQuestion(question);
  };

  const handleQuickAction = async (quickQuestion: string) => {
    setQuestion(quickQuestion);
    await submitQuestion(quickQuestion);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">🤖 Zapytaj AI o portfel</h3>

      <div className="flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((quickAction) => (
          <button
            key={quickAction}
            type="button"
            onClick={() => {
              void handleQuickAction(quickAction);
            }}
            disabled={loading}
            className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {quickAction}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={4}
          placeholder="Wpisz własne pytanie o portfel..."
          disabled={loading}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:cursor-not-allowed disabled:bg-gray-100"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
        >
          Zapytaj
        </button>
      </form>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
          <span>Analizuję portfel...</span>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded-md border border-gray-200 bg-white p-4">
        <p className="whitespace-pre-wrap text-sm text-gray-900">{answer || 'Odpowiedź AI pojawi się tutaj.'}</p>
      </div>
    </div>
  );
};

export default PortfolioAIChat;

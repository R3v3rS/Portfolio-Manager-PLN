import React, { useState } from 'react';
import { http } from '../../http';

interface PortfolioAIChatProps {
  portfolioId: number;
}

interface PortfolioAnalysisResponse {
  answer?: string;
  analysis_meta?: {
    positions_count?: number;
    subportfolios_count?: number;
  };
}

const QUICK_ACTIONS = [
  {
    group: '📊 Analiza',
    questions: [
      'Oceń mój portfel w skali 1-10 i uzasadnij',
      'Czy moje sub-portfele mają sens jako strategia?',
      'Podsumuj stan portfela w 5 punktach',
    ],
  },
  {
    group: '⚠️ Ryzyko',
    questions: [
      'Gdzie jest największa koncentracja ryzyka?',
      'Co się stanie z portfelem jeśli rynek spadnie 20%?',
      'Które pozycje nie pasują do swojego sub-portfela?',
    ],
  },
  {
    group: '💡 Akcja',
    questions: [
      'Co dokupić za wolną gotówkę?',
      'Co rozważyłbyś sprzedać i dlaczego?',
      'Jak poprawić dywersyfikację bez dużych zmian?',
    ],
  },
];

const PortfolioAIChat: React.FC<PortfolioAIChatProps> = ({ portfolioId }) => {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [includeSubportfolios, setIncludeSubportfolios] = useState(true);
  const [analysisMeta, setAnalysisMeta] = useState<{ positionsCount: number; subportfoliosCount: number } | null>(null);

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
        include_subportfolios: includeSubportfolios,
      });

      setAnswer(response.answer ?? 'Brak odpowiedzi od AI.');
      setAnalysisMeta({
        positionsCount: response.analysis_meta?.positions_count ?? 0,
        subportfoliosCount: response.analysis_meta?.subportfolios_count ?? 0,
      });
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

      <div className="space-y-3">
        {QUICK_ACTIONS.map((group) => (
          <div key={group.group} className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">{group.group}</h4>
            <div className="flex flex-wrap gap-2">
              {group.questions.map((quickAction) => (
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
          </div>
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
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={includeSubportfolios}
            onChange={(event) => setIncludeSubportfolios(event.target.checked)}
            disabled={loading}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          Uwzględnij sub-portfele
        </label>
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
        {analysisMeta && answer && (
          <p className="mb-2 text-xs text-gray-500">
            Analizowano: {analysisMeta.positionsCount} pozycji w {analysisMeta.subportfoliosCount} sub-portfelach
          </p>
        )}
        <p className="whitespace-pre-wrap text-sm text-gray-900">{answer || 'Odpowiedź AI pojawi się tutaj.'}</p>
      </div>
    </div>
  );
};

export default PortfolioAIChat;

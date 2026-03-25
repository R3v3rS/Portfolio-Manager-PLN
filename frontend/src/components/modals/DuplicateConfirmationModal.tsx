import React, { useState } from 'react';
import { XtbImportConflict } from '../../api';
import { AlertTriangle, Check, X } from 'lucide-react';
import { cn } from '../../lib/utils';

interface Props {
  conflicts: XtbImportConflict[];
  onConfirm: (confirmedHashes: string[]) => void;
  onCancel: () => void;
}

const DuplicateConfirmationModal: React.FC<Props> = ({ conflicts, onConfirm, onCancel }) => {
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());

  const toggleIndex = (idx: number) => {
    const next = new Set(selectedIndices);
    if (next.has(idx)) {
      next.delete(idx);
    } else {
      next.add(idx);
    }
    setSelectedIndices(next);
  };

  const handleConfirm = () => {
    // Send back the hashes of selected conflicts (could include same hash multiple times)
    const confirmedHashes = Array.from(selectedIndices).map(idx => conflicts[idx].row_hash);
    onConfirm(confirmedHashes);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="w-full max-w-4xl rounded-lg bg-white shadow-xl dark:bg-gray-900 my-8">
        <div className="p-6 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3 text-amber-600 mb-2">
            <AlertTriangle className="h-6 w-6" />
            <h3 className="text-xl font-bold">Wykryto potencjalne duplikaty</h3>
          </div>
          <p className="text-gray-600 dark:text-gray-400">
            Poniższe transakcje z pliku wydają się być już w bazie danych lub powtarzają się wewnątrz pliku. 
            Zaznacz te, które mimo to chcesz zaimportować. Pozostałe zostaną pominięte.
          </p>
        </div>

        <div className="p-6 max-h-[60vh] overflow-y-auto">
          <div className="space-y-6">
            {conflicts.map((conflict, idx) => (
              <div 
                key={conflict.row_hash + idx} 
                className={cn(
                  "border rounded-lg p-4 transition-colors",
                  selectedIndices.has(idx) 
                    ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20" 
                    : "border-gray-200 dark:border-gray-800"
                )}
              >
                <div className="flex items-start gap-4">
                  <div className="mt-1">
                    <input
                      type="checkbox"
                      checked={selectedIndices.has(idx)}
                      onChange={() => toggleIndex(idx)}
                      className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Importowana transakcja */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Dane z pliku</h4>
                      <div className="bg-white dark:bg-gray-800 p-3 rounded border border-gray-100 dark:border-gray-700 text-sm">
                        <div className="grid grid-cols-2 gap-1">
                          <span className="text-gray-500">Data:</span>
                          <span className="font-medium">{conflict.import_data.date}</span>
                          <span className="text-gray-500">Instrument:</span>
                          <span className="font-medium">{conflict.import_data.ticker}</span>
                          <span className="text-gray-500">Typ:</span>
                          <span className="font-medium">{conflict.import_data.type}</span>
                          <span className="text-gray-500">Ilość:</span>
                          <span className="font-medium">{conflict.import_data.quantity}</span>
                          <span className="text-gray-500">Kwota:</span>
                          <span className="font-medium text-blue-600">{conflict.import_data.amount.toFixed(2)} PLN</span>
                        </div>
                      </div>
                    </div>

                    {/* Istniejący mecz */}
                    <div>
                      <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">
                        {conflict.conflict_type === 'database_duplicate' ? 'Znaleziono w bazie' : 'Inny wiersz w pliku'}
                      </h4>
                      <div className="bg-amber-50 dark:bg-amber-900/10 p-3 rounded border border-amber-100 dark:border-amber-900/30 text-sm">
                        <div className="grid grid-cols-2 gap-1">
                          <span className="text-gray-500">Źródło:</span>
                          <span className="font-medium italic">{conflict.existing_match.source}</span>
                          <span className="text-gray-500">Data:</span>
                          <span className="font-medium">{conflict.existing_match.date}</span>
                          <span className="text-gray-500">Typ:</span>
                          <span className="font-medium">{conflict.existing_match.type}</span>
                          <span className="text-gray-500">Ilość:</span>
                          <span className="font-medium">{conflict.existing_match.quantity}</span>
                          <span className="text-gray-500">Kwota:</span>
                          <span className="font-medium">{conflict.existing_match.amount.toFixed(2)} PLN</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 border-t border-gray-200 dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50 rounded-b-lg">
          <div className="text-sm text-gray-500">
            Zaznaczono: <span className="font-bold text-gray-900 dark:text-gray-100">{selectedIndices.size}</span> z {conflicts.length}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-700"
            >
              Anuluj import
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              {selectedIndices.size > 0 ? (
                <>
                  <Check className="h-4 w-4" />
                  Importuj wybrane ({selectedIndices.size})
                </>
              ) : (
                <>
                  <X className="h-4 w-4" />
                  Pomiń wszystkie duplikaty
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DuplicateConfirmationModal;

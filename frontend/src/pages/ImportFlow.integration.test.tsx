import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ImportXtbCsvButton } from './PortfolioDetails';

const {
  importXtbCsvMock,
  normalizeXtbImportErrorMock,
  createStagingSessionMock,
  deleteSessionMock,
  bookSessionMock,
  assignRowMock,
  assignAllMock,
  rejectRowMock,
} = vi.hoisted(() => ({
  importXtbCsvMock: vi.fn(),
  normalizeXtbImportErrorMock: vi.fn(),
  createStagingSessionMock: vi.fn(),
  deleteSessionMock: vi.fn(),
  bookSessionMock: vi.fn(),
  assignRowMock: vi.fn(),
  assignAllMock: vi.fn(),
  rejectRowMock: vi.fn(),
}));

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    portfolioApi: {
      ...actual.portfolioApi,
      importXtbCsv: importXtbCsvMock,
    },
    normalizeXtbImportError: normalizeXtbImportErrorMock,
  };
});

vi.mock('../api_import_staging', () => ({
  createStagingSession: createStagingSessionMock,
  deleteSession: deleteSessionMock,
  bookSession: bookSessionMock,
  assignRow: assignRowMock,
  assignAll: assignAllMock,
  rejectRow: rejectRowMock,
}));

describe('Import flow with staging modal integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    normalizeXtbImportErrorMock.mockReturnValue({ message: 'Import failed', missingSymbols: [] });
    importXtbCsvMock.mockResolvedValue({ ok: true, message: 'ok', missingSymbols: [] });

    createStagingSessionMock.mockResolvedValue({
      session_id: 'sess-1',
      portfolio_id: 1,
      rows: [
        {
          id: 11,
          ticker: 'AAPL',
          type: 'BUY',
          quantity: 2,
          price: 100,
          total_value: 200,
          date: '2026-01-01',
          status: 'pending',
          conflict_type: null,
          conflict_details: null,
          target_sub_portfolio_id: null,
          row_hash: 'h1',
        },
      ],
      summary: { total: 1, pending: 1, conflicts: 0, rejected: 0, missing_symbols: [] },
    });

    bookSessionMock.mockResolvedValue({
      booked: 1,
      booked_tx_only: 0,
      skipped_conflicts: 0,
      rejected: 0,
      errors: [],
    });

    deleteSessionMock.mockResolvedValue({ deleted: 1 });
    assignRowMock.mockResolvedValue({});
    assignAllMock.mockResolvedValue({ assigned: 0, skipped: 0 });
    rejectRowMock.mockResolvedValue({});

    vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
  });

  const renderImportButton = () => {
    const onSuccess = vi.fn();
    const utils = render(
      <ImportXtbCsvButton
        portfolioId={1}
        onSuccess={onSuccess}
        subPortfolios={[{ id: 2, name: 'Sub A', account_type: 'STANDARD', current_cash: 0, total_deposits: 0, savings_rate: 0 }]}
      />
    );

    return { ...utils, onSuccess };
  };

  it('tryb Poczekalnia (domyślny) otwiera modal stagingu po uploadzie', async () => {
    const { container } = renderImportButton();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [new File(['x'], 'import.csv', { type: 'text/csv' })] } });

    await waitFor(() => expect(createStagingSessionMock).toHaveBeenCalled());
    expect(await screen.findByText('Poczekalnia importu')).toBeInTheDocument();
  });

  it('tryb Bezpośredni używa starego flow bez modala', async () => {
    const { container, onSuccess } = renderImportButton();

    fireEvent.click(screen.getByLabelText(/Bezpośredni/i));
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['x'], 'direct.csv', { type: 'text/csv' })] } });

    await waitFor(() => expect(importXtbCsvMock).toHaveBeenCalled());
    expect(createStagingSessionMock).not.toHaveBeenCalled();
    expect(screen.queryByText('Poczekalnia importu')).not.toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalled();
  });

  it('modal staging → klik Anuluj import wywołuje deleteSession', async () => {
    const { container } = renderImportButton();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [new File(['x'], 'import.csv', { type: 'text/csv' })] } });
    await screen.findByText('Poczekalnia importu');

    fireEvent.click(screen.getByRole('button', { name: 'Anuluj import' }));

    await waitFor(() => expect(deleteSessionMock).toHaveBeenCalledWith('sess-1'));
    await waitFor(() => expect(screen.queryByText('Poczekalnia importu')).not.toBeInTheDocument());
  });

  it('modal staging → klik Zaksięguj wywołuje bookSession i zamyka modal', async () => {
    const { container, onSuccess } = renderImportButton();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [new File(['x'], 'import.csv', { type: 'text/csv' })] } });
    await screen.findByText('Poczekalnia importu');

    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));

    await waitFor(() => expect(bookSessionMock).toHaveBeenCalledWith('sess-1', []));
    await waitFor(() => expect(screen.queryByText('Poczekalnia importu')).not.toBeInTheDocument());
    expect(onSuccess).toHaveBeenCalled();
  });
});

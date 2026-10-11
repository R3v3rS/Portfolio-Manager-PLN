import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ImportXtbCsvButton } from './PortfolioDetails';
import AdminPortfolioTools from './admin/AdminPortfolioTools';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const {
  importXtbCsvMock,
  normalizeXtbImportErrorMock,
  createStagingSessionMock,
  deleteSessionMock,
  bookSessionMock,
  assignRowMock,
  assignAllMock,
  getSessionMock,
  rejectRowMock,
  listSessionsMock,
  refreshSymbolsMock,
  listPortfoliosMock,
} = vi.hoisted(() => ({
  importXtbCsvMock: vi.fn(),
  normalizeXtbImportErrorMock: vi.fn(),
  createStagingSessionMock: vi.fn(),
  deleteSessionMock: vi.fn(),
  bookSessionMock: vi.fn(),
  assignRowMock: vi.fn(),
  assignAllMock: vi.fn(),
  getSessionMock: vi.fn(),
  rejectRowMock: vi.fn(),
  listSessionsMock: vi.fn(),
  refreshSymbolsMock: vi.fn(),
  listPortfoliosMock: vi.fn(),
}));

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    portfolioApi: {
      ...actual.portfolioApi,
      importXtbCsv: importXtbCsvMock,
      list: listPortfoliosMock,
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
  getSession: getSessionMock,
  rejectRow: rejectRowMock,
  listSessions: listSessionsMock,
  refreshSymbols: refreshSymbolsMock,
}));

describe('Import flow with staging modal integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listSessionsMock.mockResolvedValue([]);
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
    getSessionMock.mockResolvedValue({
      session_id: 'sess-1',
      portfolio_id: 1,
      rows: [],
      summary: { total: 0, pending: 0, conflicts: 0, rejected: 0, missing_symbols: [] },
    });
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

  it('oryginalny XLSX trafia do podglądu bez automatycznego księgowania', async () => {
    const { container, onSuccess } = renderImportButton();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.accept).toBe('.csv,.xlsx');
    const file = new File(['xlsx'], 'IKE.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    fireEvent.change(input, { target: { files: [file] } });
    await screen.findByText('Poczekalnia importu');
    expect(createStagingSessionMock).toHaveBeenCalledWith(1, file, undefined, 'staging');
    expect(bookSessionMock).not.toHaveBeenCalled();
    expect(importXtbCsvMock).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('skrót z pulpitu wznawia konkretną zapisaną sesję bez ponownego importu pliku', async () => {
    listPortfoliosMock.mockResolvedValue({ portfolios: [{ id: 1, name: 'Main', account_type: 'STANDARD', children: [] }] });
    listSessionsMock.mockResolvedValue([{ session_id: 'sess-1', source_file: 'import.csv', summary: { pending: 1 } }]);
    render(<MemoryRouter initialEntries={['/admin/portfolio/1?import_session=sess-1']}><Routes><Route path="/admin/portfolio/:id" element={<AdminPortfolioTools/>}/></Routes></MemoryRouter>);
    expect(await screen.findByText('Poczekalnia importu')).toBeInTheDocument();
    expect(getSessionMock).toHaveBeenCalledWith('sess-1');
    expect(createStagingSessionMock).not.toHaveBeenCalled();
    expect(bookSessionMock).not.toHaveBeenCalled();
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

  it('modal staging → księgowanie pozostawia podsumowanie do sprawdzenia', async () => {
    const { container, onSuccess } = renderImportButton();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [new File(['x'], 'import.csv', { type: 'text/csv' })] } });
    await screen.findByText('Poczekalnia importu');

    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));

    await waitFor(() => expect(bookSessionMock).toHaveBeenCalledWith('sess-1', []));
    expect(await screen.findByText('Podsumowanie księgowania')).toBeInTheDocument();
    expect(screen.getByText('Poczekalnia importu')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Zamknij$/ }));
    await waitFor(() => expect(screen.queryByText('Poczekalnia importu')).not.toBeInTheDocument());
    expect(onSuccess).toHaveBeenCalled();
  });

  it('wznawia zapisany import i zamyka podgląd bez anulowania sesji', async () => {
    const session = await createStagingSessionMock();
    listSessionsMock.mockResolvedValue([{session_id: session.session_id, source_file: 'saved.csv', created_at: '2026-01-01', summary: session.summary}]);
    getSessionMock.mockResolvedValue(session);
    renderImportButton();
    expect(await screen.findByText('Niedokończone importy (1)')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Niedokończone importy (1)'));
    fireEvent.click(screen.getByRole('button', {name: 'Wznów import'}));
    expect(await screen.findByText('Poczekalnia importu')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Zapisz na później'}));
    await waitFor(() => expect(screen.queryByText('Poczekalnia importu')).not.toBeInTheDocument());
    expect(deleteSessionMock).not.toHaveBeenCalled();
    expect(bookSessionMock).not.toHaveBeenCalled();
  });

  it('konflikt w trybie bezpośrednim otwiera tę samą sesję do decyzji', async () => {
    const session = await createStagingSessionMock();
    importXtbCsvMock.mockResolvedValue({ok: true, status: 'warning', missingSymbols: [], session});
    const {container, onSuccess} = renderImportButton();
    fireEvent.click(screen.getByLabelText(/Bezpośredni/i));
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {target: {files: [new File(['x'], 'direct.csv')]}});
    expect(await screen.findByText('Poczekalnia importu')).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(bookSessionMock).not.toHaveBeenCalled();
  });

  it('odświeżanie portfeli po księgowaniu nie usuwa podsumowania w Centrum narzędzi', async () => {
    listPortfoliosMock.mockResolvedValueOnce({portfolios: [{id: 1, name: 'Main', account_type: 'STANDARD', children: []}]});
    listPortfoliosMock.mockImplementationOnce(() => new Promise(() => {}));
    render(<MemoryRouter initialEntries={['/admin/portfolio/1']}><Routes><Route path="/admin/portfolio/:id" element={<AdminPortfolioTools />} /></Routes></MemoryRouter>);
    await screen.findByRole('button', {name: 'Import XTB CSV / XLSX'});
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {target: {files: [new File(['x'], 'import.csv')]}});
    await screen.findByText('Poczekalnia importu');
    fireEvent.click(screen.getByRole('button', {name: 'Zaksięguj zatwierdzone'}));
    expect(await screen.findByText('Podsumowanie księgowania')).toBeInTheDocument();
    await waitFor(() => expect(listPortfoliosMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText('Poczekalnia importu')).toBeInTheDocument();
    expect(deleteSessionMock).not.toHaveBeenCalled();
  });
});

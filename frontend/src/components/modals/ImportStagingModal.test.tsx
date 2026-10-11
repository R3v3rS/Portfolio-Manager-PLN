import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ImportStagingModal from './ImportStagingModal';
import type { StagingSession } from '../../types/importStaging';
import { HttpError } from '../../http';

const {
  assignAllMock,
  getSessionMock,
  assignRowMock,
  rejectRowMock,
  bookSessionMock,
  refreshSymbolsMock,
  createMappingMock,
} = vi.hoisted(() => ({
  assignAllMock: vi.fn(),
  getSessionMock: vi.fn(),
  assignRowMock: vi.fn(),
  rejectRowMock: vi.fn(),
  bookSessionMock: vi.fn(),
  refreshSymbolsMock: vi.fn(),
  createMappingMock: vi.fn(),
}));

vi.mock('../../api_import_staging', () => ({
  assignAll: assignAllMock,
  getSession: getSessionMock,
  assignRow: assignRowMock,
  rejectRow: rejectRowMock,
  bookSession: bookSessionMock,
  refreshSymbols: refreshSymbolsMock,
}));
vi.mock('../../api_symbol_map', () => ({symbolMapApi: {create: createMappingMock}}));

const createBaseSession = (): StagingSession => ({
  session_id: 'sess-1',
  portfolio_id: 1,
  rows: [
    {
      id: 1,
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
      row_hash: 'hash-1',
    },
  ],
  summary: { total: 1, pending: 1, conflicts: 0, rejected: 0, missing_symbols: [] },
});

describe('ImportStagingModal assignAll synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSessionMock.mockResolvedValue({ ...createBaseSession(), rows: [], summary: {total: 0, pending: 0, conflicts: 0, rejected: 0, missing_symbols: []} });
    vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    assignRowMock.mockResolvedValue({});
    rejectRowMock.mockResolvedValue({});
    bookSessionMock.mockResolvedValue({ booked: 0, booked_tx_only: 0, skipped_conflicts: 0, rejected: 0, errors: [] });
  });

  const renderModal = ({
    session = createBaseSession(),
    onCancel = vi.fn(),
    onCloseAfterBooking,
  }: {
    session?: StagingSession;
    onCancel?: () => void;
    onCloseAfterBooking?: () => void;
  } = {}) => {
    render(
      <ImportStagingModal
        session={session}
        subPortfolios={[{ id: 2, name: 'Sub A' }]}
        onBook={vi.fn()}
        onCancel={onCancel}
        onCloseAfterBooking={onCloseAfterBooking}
      />
    );
  };

  const runAssignAll = async () => {
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Przypisz wszystkie' }));
    await waitFor(() => expect(assignAllMock).toHaveBeenCalledWith('sess-1', 2));
  };

  it('saves a missing ticker in the preview and reuses the same session', async () => {
    const session = createBaseSession();
    session.rows[0] = {...session.rows[0], ticker:'XYZ.PL', status:'rejected', conflict_type:'missing_symbol'};
    session.summary = {...session.summary, pending:0, rejected:1, missing_symbols:['XYZ.PL']};
    createMappingMock.mockResolvedValue({});
    refreshSymbolsMock.mockResolvedValue({...createBaseSession(), rows:[{...createBaseSession().rows[0], ticker:'XYZ.WA'}]});
    renderModal({session});
    fireEvent.change(screen.getByRole('textbox', {name:'Ticker notowań dla XYZ.PL'}), {target:{value:'xyz.wa'}});
    fireEvent.click(screen.getByRole('button', {name:'Zapisz powiązania i odśwież'}));
    await waitFor(() => expect(createMappingMock).toHaveBeenCalledWith({symbol_input:'XYZ.PL',ticker:'XYZ.WA',currency:'PLN'}));
    expect(refreshSymbolsMock).toHaveBeenCalledWith('sess-1');
    expect(await screen.findByText('XYZ.WA')).toBeInTheDocument();
    expect(bookSessionMock).not.toHaveBeenCalled();
  });

  it('does not allow history confirmation when a broker operation id has conflicting data', () => {
    const session = createBaseSession();
    session.rows[0].conflict_type = 'source_mismatch';
    renderModal({session});
    expect(screen.getByText('Identyfikator operacji ma inne dane — sprawdź źródło')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name:'Zatwierdź historycznie'})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name:'Zaksięguj zatwierdzone'})).toBeDisabled();
  });

  it('pokazuje konflikty z backendu po assignAll i pozwala je potwierdzić historycznie', async () => {
    assignAllMock.mockResolvedValue({ assigned: 1, skipped: 0 });
    getSessionMock.mockResolvedValue({
      ...createBaseSession(),
      rows: [
        {
          ...createBaseSession().rows[0],
          conflict_type: 'database_duplicate',
          conflict_details: { duplicated_tx_id: 10 },
          target_sub_portfolio_id: 2,
        },
      ],
      summary: { total: 1, pending: 1, conflicts: 1, rejected: 0, missing_symbols: [] },
    });

    renderModal();
    await runAssignAll();

    expect(await screen.findByText('1 konfliktów')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pomiń duplikat' })).toBeInTheDocument();
  });

  it('dla pełnego assigned bez konfliktów nie pokazuje akcji potwierdzania konfliktu', async () => {
    assignAllMock.mockResolvedValue({ assigned: 1, skipped: 0 });
    getSessionMock.mockResolvedValue({
      ...createBaseSession(),
      rows: [
        {
          ...createBaseSession().rows[0],
          status: 'assigned',
          target_sub_portfolio_id: 2,
        },
      ],
      summary: { total: 1, pending: 0, conflicts: 0, rejected: 0, missing_symbols: [] },
    });

    renderModal();
    await runAssignAll();

    expect(await screen.findByText('0 konfliktów')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Pomiń duplikat' })).not.toBeInTheDocument();
  });

  it('przy błędzie API pokazuje komunikat i nie zmienia rows', async () => {
    assignAllMock.mockRejectedValue(new Error('Boom'));

    renderModal();
    await runAssignAll();

    expect(await screen.findByRole('alert')).toHaveTextContent('Boom');
    expect(getSessionMock).not.toHaveBeenCalled();
    expect(screen.getByText('Oczekuje')).toBeInTheDocument();
    expect(screen.queryByText('Przypisano')).not.toBeInTheDocument();
  });

  it('po pomyślnym booking kliknięcie Zamknij wywołuje onCloseAfterBooking i nie wywołuje onCancel', async () => {
    const onCloseAfterBooking = vi.fn();
    const onCancel = vi.fn();
    bookSessionMock.mockResolvedValue({ booked: 1, booked_tx_only: 0, skipped_conflicts: 0, rejected: 0, errors: [] });

    renderModal({ onCancel, onCloseAfterBooking });

    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    expect(await screen.findByText('Podsumowanie księgowania')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Zamknij' }));

    expect(onCloseAfterBooking).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('po booking bez onCloseAfterBooking wykonuje fallback do onCancel', async () => {
    const onCancel = vi.fn();
    bookSessionMock.mockResolvedValue({ booked: 1, booked_tx_only: 0, skipped_conflicts: 0, rejected: 0, errors: [] });

    renderModal({ onCancel });

    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    expect(await screen.findByText('Podsumowanie księgowania')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Zamknij' }));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('po częściowym księgowaniu pokazuje konflikt zwrócony przez serwer i pozwala kontynuować', async () => {
    const updated = createBaseSession();
    updated.rows[0].conflict_type = 'database_duplicate';
    updated.summary.conflicts = 1;
    bookSessionMock.mockResolvedValue({ booked: 0, booked_tx_only: 0, skipped_conflicts: 1, rejected: 0, errors: [], session: updated });
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    expect(await screen.findByText('Podsumowanie księgowania')).toBeInTheDocument();
    expect(screen.getByText('Duplikat w bazie')).toBeInTheDocument();
    expect(screen.getByText('Oczekuje')).toBeInTheDocument();
    expect(getSessionMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Rozwiąż pozostałe wiersze' }));
    fireEvent.click(screen.getByRole('button', { name: 'Pomiń duplikat' }));
    expect(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' })).toBeEnabled();
  });

  it('po przypisaniu pozwala zatwierdzić sprzedaż tylko do historii', async () => {
    const session = createBaseSession();
    session.rows[0] = { ...session.rows[0], type: 'SELL', status: 'assigned', conflict_type: 'insufficient_qty' };
    renderModal({ session });
    fireEvent.click(screen.getByRole('button', { name: 'Zatwierdź historycznie' }));
    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    await waitFor(() => expect(bookSessionMock).toHaveBeenCalledWith('sess-1', [1]));
  });

  it('pokazuje powód wycofania księgowania bez zmiany statusów', async () => {
    bookSessionMock.mockRejectedValue(new HttpError('Booking failed', 422, {error: {details: {row_errors: ['Brak kursu USD/PLN.']}}}));
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Księgowanie wycofane. Brak kursu USD/PLN.');
    expect(screen.getByText('Oczekuje')).toBeInTheDocument();
    expect(screen.queryByText('Podsumowanie księgowania')).not.toBeInTheDocument();
  });

  it('nie ponawia zapisu po błędzie odczytu następującym po udanym księgowaniu', async () => {
    getSessionMock.mockRejectedValue(new Error('Read failed'));
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Księgowanie zapisane');
    expect(screen.getByText('Podsumowanie księgowania')).toBeInTheDocument();
    expect(bookSessionMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Zaksięguj zatwierdzone' })).toBeDisabled();
  });

  it('ujawnia nieobsługiwane wiersze oraz brak osobnej prowizji', () => {
    const session = createBaseSession();
    session.unsupported_rows = [{row_number: 2, type: 'Tax', reason: 'Nieobsługiwany typ'}];
    session.warnings = ['Brak danych o prowizji.'];
    renderModal({session});
    expect(screen.getByText(/Nieobsługiwane wiersze: 1/)).toBeInTheDocument();
    expect(screen.getByText('Brak danych o prowizji.')).toBeInTheDocument();
  });
});

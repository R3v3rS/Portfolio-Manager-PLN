import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ImportStagingModal from './ImportStagingModal';
import type { StagingSession } from '../../types/importStaging';

const {
  assignAllMock,
  getSessionMock,
  assignRowMock,
  rejectRowMock,
  bookSessionMock,
} = vi.hoisted(() => ({
  assignAllMock: vi.fn(),
  getSessionMock: vi.fn(),
  assignRowMock: vi.fn(),
  rejectRowMock: vi.fn(),
  bookSessionMock: vi.fn(),
}));

vi.mock('../../api_import_staging', () => ({
  assignAll: assignAllMock,
  getSession: getSessionMock,
  assignRow: assignRowMock,
  rejectRow: rejectRowMock,
  bookSession: bookSessionMock,
}));

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
    expect(screen.getByRole('button', { name: 'Zatwierdź historycznie' })).toBeInTheDocument();
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
    expect(screen.queryByRole('button', { name: 'Zatwierdź historycznie' })).not.toBeInTheDocument();
  });

  it('przy błędzie API pokazuje alert i nie zmienia rows', async () => {
    const alertSpy = vi.spyOn(window, 'alert');
    assignAllMock.mockRejectedValue(new Error('Boom'));

    renderModal();
    await runAssignAll();

    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith('Boom'));
    expect(getSessionMock).not.toHaveBeenCalled();
    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.queryByText('assigned')).not.toBeInTheDocument();
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
});

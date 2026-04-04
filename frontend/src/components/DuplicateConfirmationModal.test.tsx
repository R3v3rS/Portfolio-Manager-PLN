import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import DuplicateConfirmationModal from './modals/DuplicateConfirmationModal';

const conflicts = [
  {
    row_hash: 'h1',
    conflict_type: 'database_duplicate' as const,
    import_data: { date: '2026-01-10', ticker: 'AAPL', amount: 100, type: 'BUY', quantity: 1 },
    existing_match: { id: 1, date: '2026-01-10', amount: 100, type: 'BUY', quantity: 1, source: 'db' },
  },
  {
    row_hash: 'h2',
    conflict_type: 'file_internal_duplicate' as const,
    import_data: { date: '2026-01-11', ticker: 'MSFT', amount: 200, type: 'BUY', quantity: 2 },
    existing_match: { id: null, date: '2026-01-11', amount: 200, type: 'BUY', quantity: 2, source: 'csv' },
  },
];

describe('DuplicateConfirmationModal', () => {
  it('toggles selected conflicts and confirms selected hashes', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(<DuplicateConfirmationModal conflicts={conflicts} onConfirm={onConfirm} onCancel={vi.fn()} />);

    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]);
    await user.click(screen.getByRole('button', { name: /importuj wybrane/i }));

    expect(onConfirm).toHaveBeenCalledWith(['h1']);
    expect(screen.getByText(/zaznaczono:/i)).toHaveTextContent('1 z 2');
  });

  it('calls onCancel and allows skipping all duplicates', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();

    render(<DuplicateConfirmationModal conflicts={conflicts} onConfirm={onConfirm} onCancel={onCancel} />);

    await user.click(screen.getByRole('button', { name: /anuluj import/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: /pomiń wszystkie duplikaty/i }));
    expect(onConfirm).toHaveBeenCalledWith([]);
  });
});

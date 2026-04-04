import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Empty from '../components/Empty';

describe('Empty', () => {
  it('renders fallback empty state label', () => {
    render(<Empty />);
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });
});

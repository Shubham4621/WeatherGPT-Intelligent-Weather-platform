import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Historical from './Historical';
import { LanguageContext } from '../i18n';

describe('Historical page', () => {
  it('renders period selectors and controlled unavailable response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'unavailable', location: 'Dhule', reason: 'Historical weather provider is not configured' }) }));
    render(<LanguageContext.Provider value={{ language: 'en', setLanguage: () => undefined }}><Historical /></LanguageContext.Provider>);
    expect(Boolean(screen.getByLabelText('Location'))).toBe(true);
    expect(Boolean(screen.getByLabelText('Start date'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(Boolean(screen.getByText('Historical data unavailable'))).toBe(true));
    expect(Boolean(screen.getByText(/provider is not configured/))).toBe(true);
    vi.unstubAllGlobals();
  });
});

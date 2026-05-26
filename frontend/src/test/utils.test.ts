/**
 * Utility function tests
 */
import { describe, it, expect } from 'vitest';
import { formatShortDate, formatFullDate } from '../utils/dateUtils';

describe('dateUtils', () => {
  describe('formatShortDate', () => {
    it('formats ISO date strings', () => {
      const result = formatShortDate('2024-01-15T10:30:00Z');
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
      expect(result).not.toBe('Invalid date');
    });

    it('handles empty string', () => {
      const result = formatShortDate('');
      expect(result).toBe('Invalid date');
    });

    it('handles invalid date', () => {
      const result = formatShortDate('not-a-date');
      expect(result).toBe('Invalid date');
    });
  });

  describe('formatFullDate', () => {
    it('formats ISO date strings', () => {
      const result = formatFullDate('2024-01-15T10:30:00Z');
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
      expect(result).not.toBe('Invalid date');
    });

    it('handles empty string', () => {
      const result = formatFullDate('');
      expect(result).toBe('Invalid date');
    });
  });
});

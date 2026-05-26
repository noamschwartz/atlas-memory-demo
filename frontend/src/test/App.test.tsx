/**
 * App component tests
 * 
 * Basic smoke tests to ensure the app structure is correct.
 * Note: Full rendering requires providers (EUI, Branding) which 
 * need additional setup. These tests verify the basic structure.
 */
import { describe, it, expect } from 'vitest';
import App from '../App';

describe('App', () => {
  it('exports a valid React component', () => {
    expect(App).toBeDefined();
    expect(typeof App).toBe('function');
  });

  it('component has a name', () => {
    // React components should have a displayName or name
    expect(App.name).toBeTruthy();
  });
});

describe('Module Structure', () => {
  it('can import App module', async () => {
    const module = await import('../App');
    expect(module.default).toBeDefined();
  });

  it('can import branding module', async () => {
    const module = await import('../branding');
    expect(module).toBeDefined();
  });

  it('can import utils module', async () => {
    const module = await import('../utils/dateUtils');
    expect(module.formatShortDate).toBeDefined();
    expect(module.formatFullDate).toBeDefined();
  });
});

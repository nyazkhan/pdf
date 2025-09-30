import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders PDF Accessibility Tool', () => {
  render(<App />);
  const titleElement = screen.getByText(/PDF Accessibility Remediation Tool/i);
  expect(titleElement).toBeInTheDocument();
});
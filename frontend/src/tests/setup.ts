/**
 * Test setup and configuration
 */

import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock framer-motion for tests
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children }: any) => children,
    button: ({ children }: any) => children,
    span: ({ children }: any) => children,
  },
}));

// Global test utilities
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

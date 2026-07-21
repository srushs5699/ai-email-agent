import "@testing-library/jest-dom/vitest";
import { vi } from 'vitest'

// The production client intentionally rejects missing Supabase configuration.
// Provide inert public values before test modules import that client so tests do
// not depend on a developer's local .env.local file.
vi.stubEnv('VITE_SUPABASE_URL', 'https://test-project.supabase.co')
vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'test-publishable-key')

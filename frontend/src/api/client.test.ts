import { describe, it, expect } from 'vitest'

describe('api client', () => {
  it('exports uploadDocument function', async () => {
    const { uploadDocument } = await import('./client')
    expect(typeof uploadDocument).toBe('function')
  })
})

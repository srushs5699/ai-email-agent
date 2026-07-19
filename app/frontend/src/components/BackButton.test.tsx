import { fireEvent, render, screen } from '@testing-library/react'
import { BrowserRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { BackButton } from './BackButton'

function renderButton() {
  return render(<BrowserRouter><Routes><Route path="/resumes" element={<BackButton fallback="/" />} /><Route path="/" element={<p>Dashboard</p>} /><Route path="/history" element={<p>Previous page</p>} /></Routes></BrowserRouter>)
}

afterEach(() => window.history.replaceState({}, '', '/'))

describe('BackButton', () => {
  it('uses its safe fallback when there is no in-app history entry', () => {
    window.history.replaceState({ idx: 0 }, '', '/resumes')
    renderButton()
    fireEvent.click(screen.getByRole('button', { name: '← Back' }))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('uses browser history when a previous entry exists', async () => {
    window.history.replaceState({ idx: 0 }, '', '/history')
    window.history.pushState({ idx: 1 }, '', '/resumes')
    renderButton()
    fireEvent.click(screen.getByRole('button', { name: '← Back' }))
    expect(await screen.findByText('Previous page')).toBeInTheDocument()
  })
})

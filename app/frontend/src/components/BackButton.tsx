import { useNavigate } from 'react-router'

export function BackButton({ fallback = '/' }: { fallback?: string }) {
  const navigate = useNavigate()

  function goBack(): void {
    if (window.history.state?.idx > 0) {
      navigate(-1)
      return
    }
    navigate(fallback)
  }

  return <button className="back-button" onClick={goBack} type="button">← Back</button>
}

import { useEffect, useState } from 'react'

import {
  deleteResume,
  listResumes,
  uploadResume,
  type ResumeMetadata,
} from '../api/resumes'
import {
  clearSelectedResumeId,
  getSelectedResumeId,
  setSelectedResumeId,
} from '../lib/selectedResume'
import './ResumeLibraryPage.css'

function formatFileSize(bytes: number): string {
  return `${(bytes / 1024).toFixed(1)} KB`
}

function formatUploadDate(value: string): string {
  return new Date(value).toLocaleDateString()
}

export function ResumeLibraryPage() {
  const [resumes, setResumes] = useState<ResumeMetadata[]>([])
  const [selectedResumeId, setSelectedResumeState] = useState<string | null>(
    getSelectedResumeId(),
  )
  const [file, setFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    void listResumes()
      .then((loadedResumes) => {
        setResumes(loadedResumes)
      })
      .catch(() => {
        setErrorMessage('Unable to load your resumes. Please try again.')
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [])

  function selectResume(resumeId: string): void {
    setSelectedResumeId(resumeId)
    setSelectedResumeState(resumeId)
  }

  async function handleUpload(): Promise<void> {
    if (!file) {
      setErrorMessage('Choose a PDF resume before uploading.')
      return
    }

    setErrorMessage('')
    setIsUploading(true)
    try {
      const uploadedResume = await uploadResume(file)
      setResumes((currentResumes) => [uploadedResume, ...currentResumes])
      selectResume(uploadedResume.id)
      setFile(null)
    } catch {
      setErrorMessage(
        'Unable to upload this resume. Use a text-based PDF within the size limit.',
      )
    } finally {
      setIsUploading(false)
    }
  }

  async function handleDelete(resume: ResumeMetadata): Promise<void> {
    setErrorMessage('')
    try {
      await deleteResume(resume.id)
      setResumes((currentResumes) =>
        currentResumes.filter((currentResume) => currentResume.id !== resume.id),
      )
      if (selectedResumeId === resume.id) {
        clearSelectedResumeId()
        setSelectedResumeState(null)
      }
    } catch {
      setErrorMessage('Unable to delete this resume. Please try again.')
    }
  }

  return (
    <main className="page-container resume-page">
      <header className="page-header"><h1>Resume Library</h1><p>Upload a text-based PDF and select the resume you want to use for outreach.</p></header>
      <section className="resume-upload-card" aria-labelledby="upload-resume-heading"><h2 id="upload-resume-heading">Add a resume</h2><p>Choose a text-based PDF within the supported size limit.</p><div className="resume-upload-controls"><label htmlFor="resume-file">Resume PDF</label><input
        accept="application/pdf,.pdf"
        id="resume-file"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        type="file"
      /><button className="button button--primary" disabled={isUploading} onClick={() => void handleUpload()} type="button">
        {isUploading ? 'Uploading…' : 'Upload resume'}
      </button></div></section>

      {errorMessage && <p className="alert" role="alert">{errorMessage}</p>}

      <section className="resume-list-section" aria-labelledby="your-resumes-heading"><h2 id="your-resumes-heading">Your resumes</h2>
      {isLoading && <p>Loading resumes…</p>}
      {!isLoading && resumes.length === 0 && (
        <div className="empty-state"><h2>No resumes yet</h2><p>No resumes yet. Upload a PDF to get started.</p></div>
      )}
      <ul className="resume-list">
        {resumes.map((resume) => (
          <li key={resume.id}><div><strong>{resume.name}</strong><p>{formatFileSize(resume.file_size_bytes)} · uploaded {formatUploadDate(resume.created_at)} {selectedResumeId === resume.id && <span className="status-badge status-badge--success">(selected)</span>}</p></div><div className="resume-actions"><button className="button button--secondary" onClick={() => selectResume(resume.id)} type="button">
              Select
            </button>
            <button className="button button--danger" onClick={() => void handleDelete(resume)} type="button">
              Delete
            </button></div>
          </li>
        ))}
      </ul></section>
    </main>
  )
}

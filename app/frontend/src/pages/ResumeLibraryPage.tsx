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
    <main>
      <h1>Resume Library</h1>
      <p>Upload a text-based PDF to use for outreach emails.</p>

      <label htmlFor="resume-file">Resume PDF</label>
      <input
        accept="application/pdf,.pdf"
        id="resume-file"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        type="file"
      />
      <button disabled={isUploading} onClick={() => void handleUpload()} type="button">
        {isUploading ? 'Uploading…' : 'Upload resume'}
      </button>

      {errorMessage && <p role="alert">{errorMessage}</p>}

      <h2>Your resumes</h2>
      {isLoading && <p>Loading resumes…</p>}
      {!isLoading && resumes.length === 0 && (
        <p>No resumes yet. Upload a PDF to get started.</p>
      )}
      <ul>
        {resumes.map((resume) => (
          <li key={resume.id}>
            <strong>{resume.name}</strong> — {formatFileSize(resume.file_size_bytes)} —
            uploaded {formatUploadDate(resume.created_at)}
            {selectedResumeId === resume.id && <span> (selected)</span>}
            <button onClick={() => selectResume(resume.id)} type="button">
              Select
            </button>
            <button onClick={() => void handleDelete(resume)} type="button">
              Delete
            </button>
          </li>
        ))}
      </ul>
    </main>
  )
}

# Step 3 – Project Context and Technical Setup

## Status

**Completed**

This document records the technical and development decisions finalized during Step 3.

## 1. Existing Resources

- GitHub account available
- New GitHub repository must be created
- Google Cloud should be configured from scratch
- Gmail account available
- Apollo account available
- No OpenAI API account or credits configured yet
- No custom domain yet
- No existing frontend or backend code
- Application will be built from scratch

## 2. Selected Technology Stack

- **Frontend:** React with TypeScript
- **Backend:** Python with FastAPI
- **Database:** Supabase PostgreSQL
- **Authentication:** Supabase Auth with Google OAuth
- **PDF storage:** Supabase Storage
- **Backend hosting:** Google Cloud Run
- **AI provider:** OpenAI
- **AI model:** GPT-5.3
- **Email delivery:** Gmail API
- **Task queue:** Supabase PostgreSQL database queue

The stack should prioritize fast development, low cost, easy maintenance, and future scalability.

## 3. AI Development Tools

- **ChatGPT:** planning, architecture, reviews, testing strategy, and troubleshooting
- **Codex:** primary implementation, repository changes, feature development, and debugging
- **Cursor:** code navigation, learning, review, and smaller edits

## 4. PostgreSQL Responsibilities

Supabase PostgreSQL will store structured data such as:

- User records and settings
- Resume metadata
- Talent bases
- Companies and job details
- Recruiter and contact details
- Generated and edited email drafts
- Approval, rejection, and sending status
- Queue state
- Retry and failure data
- Outreach history
- References to PDF files

## 5. Resume File Storage

Supabase Storage will store the actual PDF resume files.

It is object/blob storage. PostgreSQL will store metadata and the storage path, while the PDF itself remains in the storage bucket.

**Version 1 accepts PDF resumes only.**

## 6. Backend Hosting

The FastAPI backend will run on Google Cloud Run.

The intended setup includes:

- Serverless deployment
- Scale-to-zero behavior where supported
- Secure connection to Supabase
- Credentials stored as environment variables or secrets
- Separate development and production configuration where practical

## 7. Authentication

Version 1 will use **Google Sign-In only**, implemented through Supabase Auth with Google OAuth.

A separate application password will not be required.

## 8. Gmail Integration

The application will use the Gmail API through Google OAuth.

Workflow:

1. User signs in with Google.
2. User grants Gmail permission.
3. Application generates a personalized email draft.
4. User reviews the draft.
5. User may edit, approve, or reject it.
6. Application sends the email only after approval.

The application must never store the user's Gmail password.

## 9. Queue Architecture

Version 1 will use a PostgreSQL-backed queue in Supabase.

Requirements:

- Maximum of 10 queued tasks
- Process tasks in order
- Pause and resume
- Resume from the current queued task
- Pending, processing, completed, and failed states
- Retry failed tasks
- Delete failed tasks
- Preserve state across backend restarts
- Prevent duplicate processing
- Require email review before sending

Redis, Celery, and Google Cloud Tasks are not required for Version 1.

## Final Architecture

```text
React + TypeScript Frontend
            |
            v
FastAPI Backend on Google Cloud Run
            |
            +--> Supabase Auth with Google OAuth
            |
            +--> Supabase PostgreSQL
            |      - Application data
            |      - Queue records
            |      - Draft and status history
            |
            +--> Supabase Storage
            |      - PDF resumes
            |
            +--> Apollo
            |      - Contact discovery using available free credits
            |
            +--> OpenAI GPT-5.3
            |      - Personalized email generation
            |
            +--> Gmail API
                   - Send user-approved emails
```

## Completion

All nine Step 3 questions are complete.

The next stage is **Step 4: break the project into implementation phases, tasks, dependencies, validation checks, and a practical build order.**

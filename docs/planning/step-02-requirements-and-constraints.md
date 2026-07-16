# Step 2: Requirements and Constraints

## Purpose of This Document

This document defines the requirements, restrictions, and constraints for the first version of the AI Email Agent.

It builds on the product definition completed in Step 1 and should be used as a source of truth during planning, architecture, development, testing, and deployment.

---

## Must Include

### 1. Processing Queue

The first version must include a Processing Queue.

The Processing Queue must:

- Accept up to 10 LinkedIn post URLs at one time
- Start only when I manually begin the queue
- Process items one by one
- Continue processing other items when one item fails
- Allow me to pause the queue
- Allow me to resume the queue later
- Restart the current unfinished task from the beginning when the queue resumes
- Avoid reprocessing tasks that were already completed
- Move successfully processed tasks to the Review Queue
- Move unsuccessful tasks to the Failed Tasks queue

### 2. Review Queue

The first version must include a Review Queue.

The Review Queue must:

- Display every generated Gmail draft before it is sent
- Show the To address
- Show all CC addresses
- Show the subject
- Show the full email body
- Show the attached resume name
- Allow me to edit the To address
- Allow me to edit CC addresses
- Allow me to edit the subject
- Allow me to edit the email body
- Keep website edits synchronized with the Gmail draft
- Allow me to send the email
- Allow me to reject the draft
- Allow me to delete the draft without sending it

The application must never send an email until I explicitly approve that individual draft.

### 3. Failed Tasks Queue

The first version must include a Failed Tasks queue.

The Failed Tasks queue must:

- Receive tasks that cannot be completed
- Save the original LinkedIn URL
- Mark regular failures as **Failed**
- Mark duplicate tasks as **Duplicate**
- Mark tasks with no available email as **No email available**
- Allow me to retry failed tasks
- Allow me to delete failed tasks
- Prevent one failed task from stopping the rest of the Processing Queue

### 4. Resume Library

The application must include a private resume library.

The resume library must:

- Accept PDF files only
- Allow multiple resumes to be uploaded
- Save resumes for reuse
- Allow me to rename resumes
- Allow me to delete resumes
- Allow me to select one resume before starting a queue
- Use the selected resume for every task in that queue
- Allow a different resume to be selected for the next queue

### 5. Authentication

The application must require login.

The first version will use:

- A separate email-and-password login for the application
- A single private user account
- Protected access to resumes, queues, drafts, and integrations

The application login must be separate from Gmail, LinkedIn, and Apollo credentials.

### 6. Gmail Integration

The application must integrate with Gmail.

It must:

- Create a Gmail draft as soon as an outreach email is generated
- Attach the resume selected for that queue
- Keep the website version and Gmail draft synchronized
- Send the email immediately when I click the green approval button
- Remove successfully sent items from the application
- Leave the sent email available in Gmail's Sent folder
- Avoid storing a separate sent-email history in the application

### 7. Apollo Integration

The first version will use Apollo's available free credits.

The application must:

- Use Apollo only while free credits remain available
- Stop new Apollo lookups when the free credits are exhausted
- Display the following message clearly on the main page:

> Apollo credits are exhausted.

- Avoid guessing or inventing email addresses
- Allow me to decide later whether to upgrade Apollo or use another method

When Apollo returns multiple email addresses:

- Use a work or company-domain email in the To field when available
- Place the remaining available addresses in CC
- If no work email exists, use one personal email in To
- Place remaining personal emails in CC
- Allow unverified emails to proceed
- Clearly show when an email is unverified
- Require my approval before sending

### 8. LinkedIn and Job Description Handling

The application must not ask me for LinkedIn credentials.

It should:

- Accept a LinkedIn post URL
- Extract or receive the post author's name
- Extract or receive the LinkedIn post content
- Extract or receive the author's profile URL
- Detect a job-description link when present
- Ask me to paste the job description when the link cannot be opened
- Ask me to paste the job description when no link is available
- Allow me to select **No job description available**
- Continue using the LinkedIn post and selected resume when no job description exists

The application must not depend on storing my LinkedIn password or session credentials.

### 9. AI Email Generation

The AI component must:

- Use one fixed model selected during development
- Store the model name in configuration
- Allow the model to be changed later through code and redeployment
- Compare the selected resume, LinkedIn post, and job description
- Generate a personalized subject and email body
- Follow the approved outreach-email structure
- Describe me as a **Software Developer with four years of experience**
- Select four relevant experience points
- Keep the tone friendly, informal, playful, and professional
- Vary creative analogies instead of repeating the same wording
- Generate a short LinkedIn message when no email is found
- Never invent unsupported facts

The model is responsible for analyzing supplied content and generating text.

It is not responsible for directly logging in to LinkedIn, clicking through websites, or retrieving Apollo data.

### 10. Duplicate Prevention

The application must detect duplicate tasks.

When the same LinkedIn URL or recipient appears again:

- Do not generate or send another email
- Move the item to Failed Tasks
- Mark it as **Duplicate**
- Require me to review or delete it

### 11. Queue Completion

The system must mark a queue as complete only when:

- Processing Queue contains zero tasks
- Review Queue contains zero tasks
- Failed Tasks contains zero tasks

The queue must not be marked complete while unresolved items remain anywhere in the application.

---

## Must Avoid

The application must never:

- Send an email without my explicit approval
- Ask me to provide my Gmail password
- Ask me to provide my LinkedIn password
- Ask me to provide my Apollo account password
- Ask me to directly share personal login credentials for external websites
- Store third-party passwords
- Expose API keys in frontend code
- Commit secrets to GitHub
- Invent my work experience
- Invent technologies, projects, dates, metrics, education, or achievements
- Invent recipient details
- Invent company details
- Invent job requirements
- Invent email addresses
- Continue Apollo lookups after free credits are exhausted
- Process more than 10 URLs in one queue
- Accept resume files other than PDF
- Send duplicate outreach
- Let one failed task stop the entire queue
- Mark the task complete while any queue still contains items
- Continue AI generation after the application's internal spending limit is reached

---

## Constraints

### 1. Monthly Budget

The complete application should cost no more than:

**$7 per month**

This budget includes:

- AI API usage
- Cloud hosting
- Cloud database
- Cloud file storage
- Secret storage
- Apollo usage
- Any other required paid service

The first version should use:

- Google Cloud free-tier services where practical
- Gmail API without a separate per-email fee
- Apollo free credits
- A low-cost AI model
- Efficient prompts and minimal AI calls

If a service requires a paid plan that would exceed the $7 limit, the application should stop that feature and show a clear error rather than silently increasing cost.

### 2. AI Spending Protection

The application must include AI cost controls.

It should:

- Track estimated AI usage
- Track estimated monthly AI cost
- Use a soft warning before the maximum is reached
- Stop new AI generation requests at the application level once the configured limit is reached
- Show a visible message that AI generation has been paused because the monthly budget was reached
- Avoid unnecessary regeneration calls
- Use one AI call per email whenever practical
- Avoid repeatedly sending the full resume when a structured summary can be reused

The provider's project budget or billing alert should be treated as an additional warning, not the only stopping mechanism.

### 3. Queue Size

The maximum number of LinkedIn URLs in one queue is:

**10**

This is a fixed requirement for the first version.

### 4. Resume File Type

The resume library will accept:

**PDF only**

DOCX and other file formats are not required for version one.

### 5. Platform

The application will be cloud-hosted.

It must not depend on my local machine remaining online.

The first version is:

- Desktop-first
- Designed primarily for use in a desktop browser
- Allowed to open in a mobile browser
- Not required to have a fully optimized mobile interface

### 6. Deployment

The application should be deployable from the GitHub repository.

Configuration should allow:

- Secure environment variables
- Cloud deployment
- Model replacement through configuration
- Safe secret management
- Future changes without redesigning the entire application

### 7. User Scope

The first version is:

- Personal
- Single-user
- Private
- Not a public multi-user product

Multi-user accounts, billing, team access, and public registration are outside the first version.

---

## External Service Failure Rules

### Apollo Credits Exhausted

When Apollo free credits are exhausted:

- Stop Apollo email lookups
- Do not guess an address
- Display **Apollo credits are exhausted**
- Keep the remaining tasks unresolved until I decide what to do

### AI Budget Reached

When the internal AI spending limit is reached:

- Stop new AI generation requests
- Pause queue processing for tasks that require AI
- Display a clear budget warning
- Do not continue spending automatically

### Gmail Failure

When Gmail draft creation or sending fails:

- Do not mark the task as sent
- Move the task to Failed Tasks
- Allow me to retry it

### LinkedIn or Job Content Failure

When required LinkedIn content cannot be obtained:

- Do not stop the whole queue
- Move the affected task to Failed Tasks when it cannot be resolved
- Continue processing the remaining tasks

When job-description content is missing:

- Ask me to paste it
- Allow me to confirm that no job description is available
- Continue with the LinkedIn post and selected resume after my confirmation

---

## First-Version Success Criteria

Step 2 is satisfied when the first version:

1. Includes a Processing Queue.
2. Includes a Review Queue.
3. Includes a Failed Tasks queue.
4. Limits each queue to 10 LinkedIn URLs.
5. Accepts PDF resumes only.
6. Supports multiple stored resumes.
7. Allows resume rename and deletion.
8. Requires a separate application login.
9. Allows the Processing Queue to pause and resume.
10. Restarts only the current unfinished task when resumed.
11. Allows failed tasks to be retried or deleted.
12. Allows drafts to be edited, rejected, deleted, or sent.
13. Works primarily in a desktop browser.
14. Can open in a mobile browser.
15. Uses Apollo free credits until exhausted.
16. Shows an Apollo-credit error when required.
17. Remains within the $7 monthly budget.
18. Includes application-level AI cost controls.
19. Never requests or stores external service passwords.
20. Never sends an email without explicit approval.
21. Never marks the queue complete until all three queues are empty.

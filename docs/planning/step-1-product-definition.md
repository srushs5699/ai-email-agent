# Step 1: Define What I Want

## Task

I want to create a personal AI-assisted web application that prepares and sends job-outreach emails on my behalf using LinkedIn post URLs.

I will submit up to 10 LinkedIn post URLs at a time and manually start the processing queue. The application will process each LinkedIn post, generate a personalized outreach email, locate the post author’s email through Apollo, create a Gmail draft, and place the email in a Review Queue.

The application must never send an email automatically. I must review each email and click the green approval button before it is sent.

---

## Purpose

The purpose of this application is to automate the repetitive parts of job-outreach emailing while keeping me responsible for reviewing and approving every message.

The application should reduce the manual work involved in:

* Reading LinkedIn hiring posts
* Finding recipient information
* Reviewing job descriptions
* Matching my resume to the opportunity
* Writing personalized emails
* Creating Gmail drafts
* Attaching the appropriate resume
* Sending approved messages

---

## Audience

The first version is a private, single-user application for my personal use.

The people receiving the generated emails will generally be:

* Recruiters
* Hiring managers
* Employees sharing open positions
* LinkedIn users who publish job or hiring posts

The application may later be expanded for other job seekers, but the first version will support only me.

---

## Final Deliverable

The final deliverable will be a working personal website with the following workflow.

### 1. Resume Library

The application will allow me to upload and save multiple resumes in a private resume library.

Before starting a new processing queue, I will select one resume. Every email generated within that queue will use the selected resume.

After the queue is completed, I can start another queue and select a different resume.

### 2. LinkedIn URL Submission

I can submit up to 10 LinkedIn post URLs at one time.

The queue will not run automatically at a scheduled time. I will manually click a button whenever I want the application to begin processing the submitted URLs.

### 3. LinkedIn Information Extraction

For every submitted URL, the application should obtain:

* The LinkedIn post author’s name
* The LinkedIn post content
* The author’s LinkedIn profile
* The job-description link, when one is included
* The job-description content, when available

The application should not require or store my LinkedIn username or password.

A browser-based method may use my existing logged-in LinkedIn session to read the post. A manual option to paste the LinkedIn post content should also be available when the post cannot be accessed.

### 4. Job-Description Handling

When the LinkedIn post contains a job-description link, the application should attempt to read it.

When the link exists but cannot be opened, the application should ask me to paste the job description manually.

When no job-description link exists, the application should also ask me to paste the job description.

I must be able to select an option stating:

**No job description available**

When I select that option, the application should continue using only:

* The LinkedIn post
* The selected resume

A missing job description should not prevent the remaining queue items from being processed.

### 5. Recipient Email Retrieval

The application should use Apollo to retrieve the LinkedIn post author’s available email addresses.

I will connect Apollo using an appropriate integration or API credential. My Apollo account password should not be stored directly in the application.

When a work or company-domain email is available:

* Place the work or domain email in the **To** field.
* Place any remaining available email addresses in **CC**.

When no work or domain email is available:

* Place one available personal email in the **To** field.
* Place any remaining personal emails in **CC**.

The application may use an email even when Apollo marks it as unverified. The Review Queue must clearly show that the address is unverified.

An unverified email should still receive a generated draft and may be sent after I approve it.

### 6. No Email Available

When Apollo cannot find any email address:

* Move the item to the **Failed Tasks** queue.
* Show the message **No email available**.
* Generate a short LinkedIn message that I can manually copy and send to the person.

The LinkedIn message should:

* Be no more than four or five lines
* Briefly introduce me
* Mention my relevant experience in approximately two lines
* State my interest in the opportunity
* Request a conversation or quick call
* Remain unsent so that I can copy it manually

### 7. Email Generation

The application should write a personalized email using:

* The LinkedIn post
* The job description, when available
* The resume selected for that queue
* My approved professional information
* The recipient’s name and company

The email should describe me as:

**A Software Developer with four years of experience**

The application must not invent experience, technologies, achievements, metrics, education, personal information, recipient details, company information, or job requirements.

It must use only information supported by:

* The selected resume
* The LinkedIn post
* The available job description
* My approved profile information
* Apollo’s recipient data

### 8. Email Style and Structure

The email should follow the general structure of my approved sample while remaining flexible and personalized.

The structure should include:

1. A greeting using the recipient’s first name
2. A friendly opening
3. A playful reference to discovering the opportunity on LinkedIn
4. A sentence explaining why the opportunity caught my attention
5. My location, education, availability, and relocation flexibility when relevant
6. A statement that I am a Software Developer with four years of experience
7. Four concise lines describing the most relevant parts of my background
8. An ending that expresses interest in speaking or contributing
9. My fixed signature

The tone should be:

* Friendly
* Informal
* Playful
* Professional
* Personalized
* Easy to read

The application may use creative analogies such as a trailer, story, journey, chapters, blueprint, or another suitable idea.

It should not repeatedly use the exact “Season 1,” “Season 2,” and “career trailer” language in every email.

### 9. Fixed Email Signature

Every email must end with:

Best regards,
Srushti Shinde
Phone: (608) 217-2116
LinkedIn: https://www.linkedin.com/in/srushtisanjayshinde/

No other contact details should be included in the standard signature.

### 10. Gmail Draft Creation

As soon as an email is generated, the application should create a draft in my Gmail account.

The website’s Review Queue and the Gmail draft must stay synchronized.

When I edit the email on the website, the same Gmail draft should be updated.

The selected resume must be attached to the Gmail draft.

The application must connect to Gmail through an approved authorization method rather than storing my Gmail password.

### 11. Processing Queue

The Processing Queue contains LinkedIn URLs that are waiting to be processed or are currently being processed.

As each item is completed:

* It should leave the Processing Queue.
* A successfully generated email should enter the Review Queue.
* An unsuccessful item should enter Failed Tasks.
* The application should continue to the next item.

One failed item must never stop the entire queue.

### 12. Review Queue

The Review Queue contains emails that have been successfully generated and are waiting for my review.

For every email, I must be able to review and edit:

* To email address
* CC email addresses
* Subject
* Email body
* Attached resume name

The application should show the complete subject and email body before I approve it.

### 13. Approval and Sending

Each item in the Review Queue will have a green approval button.

Clicking the green button should:

* Send that individual Gmail draft immediately
* Use the currently displayed To and CC addresses
* Use the currently displayed subject and email body
* Attach the resume selected for that queue
* Require no additional confirmation screen

The application must never send an email until I click the green button for that specific email.

After Gmail confirms that the email was sent:

* Remove the item from the Review Queue.
* Do not save a separate sent copy in the application.
* Keep the sent email available through Gmail’s Sent folder.

### 14. Failed Tasks Queue

Any item that cannot be successfully completed will move to the **Failed Tasks** queue.

A regular unsuccessful item should display:

**Failed**

When no email is found, it should display:

**No email available**

When an item is a duplicate, it should display:

**Duplicate**

The application should save the original LinkedIn URL in Failed Tasks so I can review it later.

Failed items must not interrupt the processing of the remaining URLs.

I should be able to review, resolve, retry, or remove Failed Tasks.

### 15. Duplicate Handling

The application must prevent duplicate outreach.

When the same LinkedIn URL or the same recipient appears again:

* Do not generate another sendable email.
* Move the item to Failed Tasks.
* Mark it as **Duplicate**.

The duplicate must be reviewed or removed before the overall task can be considered complete.

### 16. Queue Completion

A queue is not complete merely because the Processing Queue and Review Queue are empty.

The entire task is complete only when:

* Processing Queue contains zero tasks
* Review Queue contains zero tasks
* Failed Tasks contains zero tasks

This means that every submitted item must eventually be:

* Successfully processed, reviewed, and sent
* Corrected and retried
* Manually resolved
* Or removed from Failed Tasks by me

Only when all three queue counts are zero should the application display the task as:

**Complete**

---

## Definition of Done

The first version of the application is complete when I can:

1. Upload and save multiple resumes in a private resume library.
2. Select one resume for each new queue.
3. Submit up to 10 LinkedIn post URLs.
4. Manually start the queue.
5. Extract the author’s name, post content, profile, and available job-description information.
6. Provide a job description manually when needed.
7. Continue without a job description when I explicitly confirm that none is available.
8. Retrieve available recipient emails through Apollo.
9. Place a domain email in To and other addresses in CC.
10. Use personal emails when no domain email exists.
11. Generate a short LinkedIn message when no email is available.
12. Generate personalized, truthful outreach emails using the selected resume.
13. Create Gmail drafts immediately.
14. Keep website edits synchronized with Gmail drafts.
15. Display generated emails in a Review Queue.
16. Allow me to edit To, CC, subject, and email body.
17. Attach the selected resume.
18. Send an email only when I click its green approval button.
19. Remove successfully sent emails from the application.
20. Continue processing after individual failures.
21. Move unsuccessful or duplicate items to Failed Tasks.
22. Prevent duplicate emails.
23. Mark the overall task complete only when all three queues contain zero tasks.

The application is not ready for use until the complete workflow works correctly from LinkedIn URL submission through Gmail delivery, while preserving my final approval before every email is sent.

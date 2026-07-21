import { describe, expect, it } from 'vitest'
import { extractLinkedInPost, extractJobLink, extractPostText, isSupportedPostUrl, normalizeUrl } from '../src/extraction/extract'

function page(body: string): Document {
  document.body.innerHTML = body
  return document
}
const source = 'https://www.linkedin.com/feed/update/urn:li:activity:123?trk=feed'
const post = `<article data-urn="urn:li:activity:123"><a class="update-components-actor__name" href="/company/acme/">Acme Corp</a><div class="update-components-text">We are hiring!\nApply today.</div><a href="/jobs/view/99">Apply for this role</a><div class="comments">Comment by Ignore Person</div></article><article data-urn="urn:li:activity:456"><div class="update-components-text">Suggested post never capture</div></article>`
describe('LinkedIn extraction', () => {
  it('normalizes supported post URLs and removes tracking', () => { expect(normalizeUrl('https://www.linkedin.com/feed/update/urn:li:activity:1?trk=x', 'https://www.linkedin.com')!).not.toContain('trk='); expect(isSupportedPostUrl('https://www.linkedin.com/posts/acme_role-1')).toBe(true) })
  it('marks unsupported pages without losing source URL', () => { const result = extractLinkedInPost(page('<main>Home navigation</main>'), 'https://www.linkedin.com/feed/'); expect(result.supported).toBe(false); expect(result.payload.sourceUrl).toContain('/feed/') })
  it('handles LinkedIn profile pages as unsupported rather than throwing', () => { const result = extractLinkedInPost(page('<main>Profile content</main>'), 'https://www.linkedin.com/in/reena-soni-83508522a/'); expect(result.supported).toBe(false); expect(result.payload.warnings.join(' ')).toMatch(/not appear to be a supported LinkedIn post page/i) })
  it('captures company author, scoped visible text, and ranked job link', () => { const result = extractLinkedInPost(page(post), source); expect(result.payload).toMatchObject({ authorName: 'Acme Corp', authorProfileUrl: 'https://www.linkedin.com/company/acme/', postText: 'We are hiring!\nApply today.', jobDescriptionUrl: 'https://www.linkedin.com/jobs/view/99' }); expect(result.payload.postText).not.toContain('Comment') })
  it('ranks deterministic job candidates and normalizes relative links', () => { const root = page(`<article><a href="/jobs/view/2">Apply</a><a href="https://careers.example.com/role">Careers</a></article>`).querySelector('article')!; expect(extractJobLink(root, 'https://www.linkedin.com/post/1').value).toContain('/jobs/view/2') })
  it('handles missing fields and selector layout fallbacks safely', () => { const result = extractLinkedInPost(page('<article aria-label="post"><p>Unstructured content</p></article>'), source); expect(result.payload.authorName).toBeUndefined(); expect(result.payload.postText).toBeUndefined(); expect(result.payload.warnings.length).toBeGreaterThan(0) })
  it('does not use page navigation or unrelated feed content as post text', () => { const root = page('<article><div class="feed-shared-update-v2__description">Target post</div></article><nav>Home Messaging</nav>').querySelector('article')!; expect(extractPostText(root).value).toBe('Target post') })
})

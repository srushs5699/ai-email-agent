export const POST_SELECTORS = [
  'article[data-urn*="activity"]', '[data-urn*="activity"][role="article"]',
  '.feed-shared-update-v2', '[data-id*="urn:li:activity"]', 'article'
]
export const AUTHOR_SELECTORS = [
  '[data-test-id="actor-name"]', '.update-components-actor__name', '.feed-shared-actor__name',
  'a[href*="/in/"] span[dir="ltr"]', 'a[href*="/company/"] span[dir="ltr"]'
]
export const TEXT_SELECTORS = [
  '[data-test-id="main-feed-activity-card__commentary"]', '.update-components-text',
  '.feed-shared-update-v2__description', '[data-test-id="commentary"]'
]

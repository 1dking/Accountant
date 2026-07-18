/**
 * Sales-page runtime config.
 *
 * DEMO_WEBHOOK_KEY is the inbound-lead webhook key of the production
 * "Website Leads" form (Forms → Website webhook). The demo-request form on the
 * sales page POSTs straight to /api/forms/webhook/<key>, which files the lead as
 * a contact and fires FORM_SUBMITTED automations — the page dogfoods the
 * product's own lead capture.
 *
 * Null hides the demo form (the CTA degrades to Log in only). The key is baked
 * at deploy time after generating it in prod; it is not a secret in the
 * credential sense — any visitor's browser sees it in the POST — rotating it in
 * the Forms UI kills spam if it's ever abused.
 */
export const DEMO_WEBHOOK_KEY: string | null =
  'XnBT4djwloxogpksqOjziF21wQOQO5JK5rRYgzQxyMA'

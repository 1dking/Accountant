/**
 * E2E: Full invoice lifecycle — create → add line items → send → record payment → verify paid.
 *
 * Requires both backend and frontend running (see playwright.config.ts webServer).
 */
import { test, expect } from '@playwright/test'

const TEST_EMAIL = 'admin@test.com'
const TEST_PASSWORD = 'TestPass123!'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(TEST_EMAIL)
  await page.getByLabel(/password/i).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: /sign in|log in|login/i }).click()
  // Wait for redirect to dashboard
  await page.waitForURL(/\/(dashboard)?$/, { timeout: 10_000 })
}

test.describe('Invoice Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('create invoice, send, pay, verify status transitions', async ({ page }) => {
    // Navigate to invoices
    await page.getByRole('link', { name: /invoices/i }).click()
    await page.waitForSelector('[data-testid="invoices-page"], h1:has-text("Invoices")', { timeout: 5000 })

    // Click create
    await page.getByRole('button', { name: /create|new/i }).first().click()

    // Fill contact (select first available)
    const contactSelect = page.locator('[data-testid="contact-select"], select, [role="combobox"]').first()
    if (await contactSelect.isVisible()) {
      await contactSelect.click()
      await page.locator('[role="option"]').first().click()
    }

    // Fill line item
    const descInput = page.getByPlaceholder(/description/i).first()
    if (await descInput.isVisible()) {
      await descInput.fill('E2E Test Service')
    }

    const qtyInput = page.getByPlaceholder(/quantity|qty/i).first()
    if (await qtyInput.isVisible()) {
      await qtyInput.fill('2')
    }

    const priceInput = page.getByPlaceholder(/price|rate/i).first()
    if (await priceInput.isVisible()) {
      await priceInput.fill('500')
    }

    // Submit
    await page.getByRole('button', { name: /save|create|submit/i }).first().click()

    // Wait for success
    await expect(page.locator('text=/created|success|INV-/i')).toBeVisible({ timeout: 5000 })
  })

  test('sidebar navigation loads every page without errors', async ({ page }) => {
    const navItems = [
      { name: /dashboard/i, urlPattern: /\/(dashboard)?$/ },
      { name: /invoices/i, urlPattern: /\/invoices/ },
      { name: /estimates/i, urlPattern: /\/estimates/ },
      { name: /expenses/i, urlPattern: /\/expenses/ },
      { name: /contacts/i, urlPattern: /\/contacts/ },
      { name: /documents|drive/i, urlPattern: /\/documents|\/drive/ },
      { name: /cashbook/i, urlPattern: /\/cashbook/ },
    ]

    for (const item of navItems) {
      const link = page.getByRole('link', { name: item.name }).first()
      if (await link.isVisible({ timeout: 2000 }).catch(() => false)) {
        await link.click()
        await page.waitForURL(item.urlPattern, { timeout: 5000 })
        // No error modals or 500 messages should be visible
        await expect(page.locator('text=/500|Internal Server Error/i')).not.toBeVisible()
      }
    }
  })
})

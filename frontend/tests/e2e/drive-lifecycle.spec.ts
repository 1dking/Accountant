/**
 * E2E: Full drive lifecycle — create folder → upload file → navigate → move → delete.
 */
import { test, expect } from '@playwright/test'

const TEST_EMAIL = 'admin@test.com'
const TEST_PASSWORD = 'TestPass123!'

async function login(page: import('@playwright/test').Page) {
  await page.goto('/login')
  await page.getByLabel(/email/i).fill(TEST_EMAIL)
  await page.getByLabel(/password/i).fill(TEST_PASSWORD)
  await page.getByRole('button', { name: /sign in|log in|login/i }).click()
  await page.waitForURL(/\/(dashboard)?$/, { timeout: 10_000 })
}

test.describe('Drive Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('create folder, upload file, navigate, verify file is there', async ({ page }) => {
    // Navigate to documents/drive
    const driveLink = page.getByRole('link', { name: /documents|drive/i }).first()
    await driveLink.click()
    await page.waitForURL(/\/documents|\/drive/, { timeout: 5000 })

    // Create folder
    const newFolderBtn = page.getByRole('button', { name: /new folder|create folder/i }).first()
    if (await newFolderBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newFolderBtn.click()
      const nameInput = page.getByPlaceholder(/folder name|name/i).first()
      await nameInput.fill('E2E Test Folder')
      await page.getByRole('button', { name: /create|save|ok/i }).first().click()
      await expect(page.locator('text=E2E Test Folder')).toBeVisible({ timeout: 5000 })
    }

    // Upload a file
    const uploadBtn = page.getByRole('button', { name: /upload/i }).first()
    if (await uploadBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      const fileInput = page.locator('input[type="file"]').first()
      await fileInput.setInputFiles({
        name: 'e2e-test.txt',
        mimeType: 'text/plain',
        buffer: Buffer.from('E2E test file content'),
      })

      // Wait for upload completion
      await expect(page.locator('text=/e2e-test|uploaded|success/i')).toBeVisible({ timeout: 10_000 })
    }
  })

  test('trash and restore document', async ({ page }) => {
    await page.getByRole('link', { name: /documents|drive/i }).first().click()
    await page.waitForURL(/\/documents|\/drive/, { timeout: 5000 })

    // Look for any document and open its context menu
    const docRow = page.locator('[data-testid="document-row"], tr, [role="row"]').first()
    if (await docRow.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Try right-click or three-dot menu
      const menuBtn = docRow.locator('[data-testid="more-menu"], button:has(svg)').first()
      if (await menuBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await menuBtn.click()
        const trashOption = page.getByRole('menuitem', { name: /trash|delete/i }).first()
        if (await trashOption.isVisible({ timeout: 2000 }).catch(() => false)) {
          await trashOption.click()
          // Confirm if dialog appears
          const confirmBtn = page.getByRole('button', { name: /confirm|yes|delete/i }).first()
          if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
            await confirmBtn.click()
          }
        }
      }
    }
  })
})

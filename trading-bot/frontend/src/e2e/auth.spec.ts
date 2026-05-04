import { test, expect } from '@playwright/test'

test.describe('Authentication flow', () => {
  test('redirects unauthenticated users to /login', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
  })

  test('shows error on invalid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"]', 'baduser')
    await page.fill('input[type="password"]', 'wrongpass')
    await page.click('button[type="submit"]')
    await expect(page.getByText(/invalid credentials/i)).toBeVisible({ timeout: 5000 })
  })
})

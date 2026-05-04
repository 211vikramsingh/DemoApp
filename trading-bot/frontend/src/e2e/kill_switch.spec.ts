import { test, expect } from '@playwright/test'

// These tests assume the dev server is running and a test user is seeded
test.describe('Kill Switch E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept API calls for kill — avoid real broker calls
    await page.route('/api/kill/', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scope: 'global', positions_closed: 1, orders_cancelled: 2,
          timestamp: new Date().toISOString(), instrument: null, trade_id: null,
        }),
      })
    )
    await page.route('/api/auth/login', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: 'test-token', token_type: 'bearer' }),
      })
    )
    await page.route('/api/users/me', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'u1', username: 'testuser', email: 'test@test.com', role: 'user', is_active: true }),
      })
    )

    await page.goto('/login')
    await page.fill('input[type="text"]', 'testuser')
    await page.fill('input[type="password"]', 'TestPass1!')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
  })

  test('KILL button is visible in the header', async ({ page }) => {
    await expect(page.getByRole('button', { name: /kill/i })).toBeVisible()
  })

  test('Ctrl+Shift+K opens the kill modal', async ({ page }) => {
    await page.keyboard.press('Control+Shift+K')
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('clicking KILL opens modal, cancel closes it', async ({ page }) => {
    await page.getByRole('button', { name: /kill/i }).first().click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByText('Cancel').click()
    await expect(page.getByRole('dialog')).not.toBeVisible()
  })

  test('global kill shows confirmation step before executing', async ({ page }) => {
    await page.getByRole('button', { name: /kill/i }).first().click()
    await page.getByText('execute global kill').click()
    await expect(page.getByText(/CONFIRM:/i)).toBeVisible()
  })
})

import { expect, test, type Page } from '@playwright/test';

const auditIssues: string[] = [];
let expectedIssuePatterns: RegExp[] = [];

async function attachAudit(page: Page) {
  page.on('console', (message) => {
    if (message.type() === 'error') {
      auditIssues.push(`[console:${message.type()}] ${message.text()}`);
    }
  });
  page.on('pageerror', (error) => {
    auditIssues.push(`[pageerror] ${error.message}`);
  });
  page.on('requestfailed', (request) => {
    const failure = request.failure();
    auditIssues.push(`[requestfailed] ${request.method()} ${request.url()} ${failure?.errorText || ''}`.trim());
  });
  page.on('response', (response) => {
    if (response.status() >= 400 && !response.url().includes('/socket.io/')) {
      auditIssues.push(`[http:${response.status()}] ${response.request().method()} ${response.url()}`);
    }
  });
}

test.beforeEach(async ({ page }) => {
  expectedIssuePatterns = [];
  await attachAudit(page);
});

test.afterEach(async () => {
  const unexpectedIssues = auditIssues.filter((issue) => {
    return !expectedIssuePatterns.some((pattern) => pattern.test(issue));
  });
  expect(unexpectedIssues, unexpectedIssues.join('\n')).toEqual([]);
  auditIssues.length = 0;
  expectedIssuePatterns = [];
});

test('guest can register, login, send a message, toggle theme, and logout', async ({ page }) => {
  const memberMessage = 'browser e2e member message';

  await page.goto('/');
  await expect(page.getByRole('heading', { name: /permission boundary/i })).toBeVisible();
  await expect(page.locator('meta[name="csrf-token"]')).toHaveCount(1);

  await expect(page.locator('#password')).toHaveAttribute('type', 'password');
  await page.locator('#password').fill('Password123');
  await page.getByRole('button', { name: 'Dark' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Light' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(page.locator('#password')).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Hide password' }).click();
  await expect(page.locator('#password')).toHaveAttribute('type', 'password');
  await page.locator('#password').fill('');

  await page.getByRole('button', { name: 'Register' }).click();
  await page.locator('#username').fill(`member${Date.now()}`);
  await page.locator('#email').fill(`member${Date.now()}@example.com`);
  await page.locator('#password').fill('Password123');
  await page.getByRole('button', { name: 'Create Account' }).click();
  await expect(page.getByRole('alert')).toHaveText(/Registered successfully/i);

  await page.locator('#username').fill('normaluser');
  await page.locator('#password').fill('Password123');
  await page.getByRole('button', { name: 'Enter Workspace' }).click();

  await expect(page.getByRole('heading', { name: 'Realtime room for active members.' })).toBeVisible();
  await expect(page.locator('#msgInput')).toBeVisible();

  await page.locator('#msgInput').fill(memberMessage);
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Message sent to connected members.')).toBeVisible();
  await expect(page.locator('#messages').getByText(memberMessage)).toBeVisible();

  await page.getByRole('button', { name: 'Dark' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Light' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');

  await page.locator('#messageSearch').fill('browser e2e');
  await expect(page.locator('#messages').getByText(memberMessage)).toBeVisible();

  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page.getByRole('button', { name: 'Enter Workspace' })).toBeVisible();
});

test('invalid login shows useful feedback without navigation', async ({ page }) => {
  expectedIssuePatterns = [
    /^\[http:401\] POST http:\/\/127\.0\.0\.1:5100\/login$/,
    /^\[console:error\] Failed to load resource: the server responded with a status of 401/,
  ];

  await page.goto('/');
  await page.locator('#username').fill('normaluser');
  await page.locator('#password').fill('WrongPassword999');
  await page.getByRole('button', { name: 'Enter Workspace' }).click();

  await expect(page.getByRole('alert')).toHaveText('Invalid username or password');
  await expect(page.getByRole('button', { name: 'Enter Workspace' })).toBeVisible();
});

test('admin can use moderation console but cannot see member messages', async ({ page }) => {
  await page.goto('/');
  await page.locator('#username').fill('admin');
  await page.locator('#password').fill('AdminPass123!');
  await page.getByRole('button', { name: 'Enter Workspace' }).click();

  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole('heading', { name: 'Manage access, not conversations.' })).toBeVisible();
  await expect(page.getByText('browser e2e member message')).toHaveCount(0);

  await page.locator('#searchInput').fill('normaluser');
  await expect(page.getByText('normaluser')).toBeVisible();

  await page.getByRole('button', { name: 'Refresh' }).click();
  await expect(page.getByText('Member roster refreshed.')).toBeVisible();

  await page.locator('#quickUsername').fill('normaluser');
  await page.locator('#quickBanBtn').click();
  await expect(page.getByText('normaluser updated successfully.')).toBeVisible();
  await expect(page.locator('#memberList').getByText('Banned')).toBeVisible();

  await page.locator('#quickUsername').fill('normaluser');
  await page.locator('#quickUnbanBtn').click();
  await expect(page.getByText('normaluser updated successfully.')).toBeVisible();
  await expect(page.locator('#memberList').getByText('Active')).toBeVisible();

  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page.getByRole('button', { name: 'Enter Workspace' })).toBeVisible();
});

test('banned member loses the message stream immediately', async ({ browser }) => {
  const memberContext = await browser.newContext();
  const adminContext = await browser.newContext();
  const memberPage = await memberContext.newPage();
  const adminPage = await adminContext.newPage();

  try {
    await memberPage.goto('/');
    await memberPage.locator('#username').fill('normaluser');
    await memberPage.locator('#password').fill('Password123');
    await memberPage.getByRole('button', { name: 'Enter Workspace' }).click();

    await expect(memberPage.getByRole('heading', { name: 'Realtime room for active members.' })).toBeVisible();
    await expect(memberPage.locator('#msgInput')).toBeVisible();
    await expect(memberPage.locator('#messages').getByText('welcome to the browser audit stream')).toBeVisible();

    await adminPage.goto('/');
    await adminPage.locator('#username').fill('admin');
    await adminPage.locator('#password').fill('AdminPass123!');
    await adminPage.getByRole('button', { name: 'Enter Workspace' }).click();
    await expect(adminPage).toHaveURL(/\/admin$/);

    await adminPage.locator('#quickUsername').fill('normaluser');
    await adminPage.locator('#quickBanBtn').click();
    await expect(adminPage.getByText('normaluser updated successfully.')).toBeVisible();

    await expect(memberPage.getByRole('heading', { name: 'Your member session has been closed.' })).toBeVisible();
    await expect(memberPage.getByText('Your account has been banned. You have been removed from the member workspace.')).toBeVisible();
    await expect(memberPage.getByText('Access revoked. The member stream is now locked.')).toBeVisible();
    await expect(memberPage.locator('#msgInput')).toHaveCount(0);
    await expect(memberPage.locator('#messages').getByText('welcome to the browser audit stream')).toHaveCount(0);
  } finally {
    await memberContext.close();
    await adminContext.close();
  }
});

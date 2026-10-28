// The whole scholarship approval chain in a real browser, one role after another, with a numbered screenshot
// of every screen in e2e/screenshots/ (look through them instead of clicking everything by hand).
// The data comes from the backend's seed_e2e command: application 1 (Ali Khan) waits at Placement verification.
import { mkdirSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const PASSWORD = 'E2e-Test-Passw0rd!'
const PDF = { name: 'bank-statement-full.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n%%EOF\n') }
const BANK = '6. Bank Statement(s) - Last Six Months'
const SHOTS = new URL('./screenshots/', import.meta.url)
mkdirSync(SHOTS, { recursive: true })

let shotNumber = 0
async function shot(page, name) {
  shotNumber += 1
  const file = `${String(shotNumber).padStart(2, '0')}-${name}.png`
  await page.screenshot({ path: new URL(file, SHOTS).pathname.replace(/^\/([A-Za-z]:)/, '$1'), fullPage: true })
}

async function login(page, email) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible()
}

async function openCase(page, queueLink) {
  await page.getByRole('link', { name: queueLink }).click()
  await page.getByRole('link', { name: 'Ali Khan' }).click()
  await expect(page.getByRole('heading', { name: 'Ali Khan', level: 1 })).toBeVisible()
}

async function act(page, action, { remarks = '', percentage } = {}) {
  const panel = page.getByRole('form', { name: 'Decision' })
  const select = panel.getByLabel('Action')
  await select.selectOption({ label: action })
  if (percentage !== undefined) await panel.getByLabel(/Scholarship percentage/).fill(String(percentage))
  if (remarks) await panel.getByLabel(/Remarks/).fill(remarks)
  await panel.getByRole('button', { name: action }).click()
}

test('a scholarship case goes through the whole approval chain', async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept()) // "Forward all" asks for confirmation

  // ---------- 1. Placement checks the files, flags a section and returns the case ----------
  await login(page, 'placement@e2e.test')
  await shot(page, 'placement-dashboard')
  await page.getByRole('link', { name: 'My work: Scholarship applications' }).click()
  await expect(page.getByRole('link', { name: 'Ali Khan' })).toBeVisible()
  await shot(page, 'placement-queue')
  await page.getByRole('link', { name: 'Ali Khan' }).click()
  await expect(page.getByRole('heading', { name: 'Ali Khan', level: 1 })).toBeVisible()
  await shot(page, 'placement-case')

  const bank = page.getByRole('listitem', { name: BANK })
  await bank.getByRole('button', { name: 'Needs clarification' }).click()
  await bank.getByLabel(/What is unclear/).fill('Only the first page was uploaded; upload all six months.')
  await bank.getByRole('button', { name: 'Save' }).click()
  await expect(bank.getByText('Needs clarification', { exact: true }).first()).toBeVisible()

  const corrections = page.getByRole('form', { name: 'Request a correction' })
  await corrections.getByLabel('Section').selectOption('accommodation')
  await corrections.getByLabel(/What should the student correct/).fill('Plot size does not match the utility bill.')
  await corrections.getByRole('button', { name: 'Flag section' }).click()
  await expect(page.getByText(/Plot size does not match the utility bill\./)).toBeVisible()

  await act(page, 'Verify and send to DAC')
  await expect(page.getByRole('alert')).toContainText('cannot be verified yet')
  await shot(page, 'placement-verify-refused-with-reasons')

  await act(page, 'Return to student', { remarks: 'Please correct the two items below and resubmit.' })
  await expect(page.getByRole('status')).toContainText('Returned to student')
  await shot(page, 'placement-returned')

  // ---------- 2. The student sees what to fix, corrects only that, and resubmits ----------
  await login(page, 'student@e2e.test')
  await page.getByRole('link', { name: 'Scholarship applications' }).click()
  await shot(page, 'student-home-make-corrections')
  await page.getByRole('link', { name: 'Make corrections' }).click()
  const banner = page.getByRole('region', { name: 'Returned for corrections' })
  await expect(banner).toContainText('Plot size does not match the utility bill.')
  await shot(page, 'student-returned-banner')

  await banner.getByRole('link', { name: 'Correct' }).click()
  await page.getByLabel('House plot size (sq. ft.)').fill('1350')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Resubmit when all corrections are done')
  await shot(page, 'student-corrected-accommodation')

  await page.goto('/scholarships/1/personal')
  await expect(page.getByText(/was not flagged by the Placement Office/)).toBeVisible()
  await shot(page, 'student-unflagged-step-locked')

  await page.goto('/scholarships/1/documents')
  const myBank = page.getByRole('listitem', { name: BANK })
  await expect(myBank.getByText(/Placement Office: Only the first page/)).toBeVisible()
  await myBank.getByTestId('Replace scan.pdf').setInputFiles(PDF)
  await expect(myBank.getByText('bank-statement-full.pdf')).toBeVisible()
  await shot(page, 'student-replaced-bank-statement')

  await page.goto('/scholarships/1/review')
  await page.getByLabel(/What did you change/).fill('Corrected the plot size and uploaded all six statements.')
  await page.getByRole('button', { name: 'Resubmit application' }).click()
  await page.getByRole('button', { name: 'Yes, resubmit' }).click()
  await expect(page.getByRole('status')).toContainText('sent back to the Placement Office')
  await shot(page, 'student-resubmitted')

  // ---------- 3. Placement verifies every file, receives Form 2 and sends the case to the DAC ----------
  await login(page, 'placement@e2e.test')
  await openCase(page, 'My work: Scholarship applications')
  const verifyButtons = page.locator('.file-review').getByRole('button', { name: 'Verified' })
  while (await verifyButtons.count() > 0) {
    const before = await verifyButtons.count()
    await verifyButtons.first().click()
    await expect(verifyButtons).toHaveCount(before - 1)
  }
  await page.getByRole('button', { name: 'Mark original received' }).click()
  await expect(page.getByText(/Original received on/)).toBeVisible()
  await shot(page, 'placement-all-verified')
  await act(page, 'Verify and send to DAC', { remarks: 'All documents checked.' })
  await expect(page.getByRole('status')).toContainText('DAC review')

  // ---------- 4. The DAC interviews and shortlists ----------
  await login(page, 'dac@e2e.test')
  await openCase(page, 'My work: DAC review queue')
  const interview = page.getByRole('form', { name: 'DAC interview' })
  await interview.getByLabel('Interview remarks').fill('Father is a clerk with five dependants; need is genuine.')
  await interview.getByRole('button', { name: 'Save interview' }).click()
  await expect(interview.getByText('Interview saved.')).toBeVisible()
  await shot(page, 'dac-interview')
  await act(page, 'Shortlist', { remarks: 'Recommended.', percentage: 60 })
  await expect(page.getByText(/has left your queue/)).toBeVisible()
  await shot(page, 'dac-shortlisted')

  // ---------- 5. Placement forwards all shortlisted cases ----------
  await login(page, 'placement@e2e.test')
  await page.getByRole('link', { name: 'My work: Scholarship applications' }).click()
  await page.getByRole('button', { name: 'Forward all shortlisted to the Director' }).click()
  await expect(page.getByText('Forwarded 1 case to the Director.')).toBeVisible()
  await shot(page, 'placement-forwarded')

  // ---------- 6. Director (changes the percentage), Registrar and VC approve ----------
  for (const [email, queue, percentage] of [['director@e2e.test', 'My work: Director review queue', 50],
    ['registrar@e2e.test', 'My work: Registrar review queue'], ['vc@e2e.test', 'My work: VC review queue']]) {
    await login(page, email)
    await openCase(page, queue)
    await expect(page.getByRole('region', { name: 'DAC interview' })).toContainText('five dependants')
    await shot(page, `${email.split('@')[0]}-case`)
    await act(page, 'Approve', { percentage, remarks: percentage ? 'Half the tuition fee is enough.' : '' })
    await expect(page.getByText(/has left your queue/)).toBeVisible()
  }

  // ---------- 7. The student sees the approval ----------
  await login(page, 'student@e2e.test')
  await page.goto('/scholarships/1/status')
  await expect(page.getByText('Approved by the Vice Chancellor.')).toBeVisible()
  await expect(page.getByText('Scholarship: 50% of the semester tuition fee.')).toBeVisible()
  await shot(page, 'student-approved-status')
})

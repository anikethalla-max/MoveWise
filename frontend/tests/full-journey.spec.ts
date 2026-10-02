import { test, expect } from '@playwright/test';
import path from 'node:path';

test('synthetic relocation journey across four agents', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText(/Deterministic evaluation simulation/i)).toBeVisible();
  await page.getByRole('button', {name:'Get started'}).click();
  await page.getByLabel('Destination city').fill('Bengaluru');
  await page.getByLabel('Moving date').fill('2027-01-15');
  await page.getByLabel('Monthly spending limit (₹)').fill('50000');
  await page.getByLabel('Upfront spending limit (₹)').fill('100000');
  await page.getByLabel('Housing preferences').fill('furnished Indiranagar');
  await page.getByRole('button', {name:'Save profile'}).click();
  await expect(page.getByText('Saved successfully.')).toBeVisible();

  await page.getByRole('button', {name:'housing', exact:true}).click();
  for (const [name, locality, rent, deposit] of [
    ['Synthetic home A','Indiranagar','30000','80000'],
    ['Synthetic home B','Whitefield','42000','110000'],
    ['Synthetic home C','Koramangala','36000','95000'],
  ]) {
    await page.getByLabel('Name', {exact:true}).fill(name);
    await page.getByLabel('Locality').fill(locality);
    await page.getByLabel('Rent (₹)').fill(rent);
    await page.getByLabel('Maintenance (₹)').fill('2000');
    await page.getByLabel('Deposit (₹)').fill(deposit);
    await page.getByLabel('Notes').fill('Synthetic test example; not a live listing.');
    await page.getByRole('button', {name:'Add home'}).click();
    await expect(page.getByRole('heading', {name})).toBeVisible();
  }
  await page.getByRole('button', {name:'budget', exact:true}).click();
  for (const [field,value] of [['utilities','2000'],['food','8000'],['transport','3000'],['miscellaneous','2000'],['moving costs','5000'],['setup costs','3000']]) {
    await page.getByLabel(`${field} (₹)`).fill(value);
  }
  await page.getByRole('button', {name:'Save budget'}).click();
  await page.getByRole('button', {name:'housing', exact:true}).click();
  await page.screenshot({path:path.resolve('../docs/screenshots/housing-mock.png'),fullPage:true});

  await page.getByRole('link', {name:'Documents'}).click();
  await page.getByLabel('Upload a document').setInputFiles(path.resolve('../data/demo/synthetic-rental-agreement.txt'));
  await expect(page.getByText(/synthetic-rental-agreement.txt.*ready/i)).toBeVisible({timeout:15000});
  await page.getByLabel('Your question').fill('What is the refundable deposit?');
  await page.getByRole('button', {name:'Ask question'}).click();
  await expect(page.getByText(/INR 80,000/)).toBeVisible();
  await page.getByRole('button', {name:/synthetic-rental-agreement.txt/}).click();
  await expect(page.getByText(/refundable security deposit/i)).toBeVisible();
  await page.screenshot({path:path.resolve('../docs/screenshots/documents-mock.png'),fullPage:true});

  await page.goto('/housing-advisor');
  await page.getByLabel('Your question').fill('Compare my homes for budget and preferences');
  await page.getByRole('button', {name:'Compare homes'}).click();
  await expect(page.getByRole('heading', {name:'Recommended homes'})).toBeVisible();
  await page.getByRole('button', {name:'Select this home'}).first().click();

  await page.goto('/plan');
  await page.getByRole('button', {name:'Generate plan preview'}).click();
  await expect(page.getByRole('heading', {name:/Review proposed version/})).toBeVisible();
  await page.getByRole('button', {name:'Confirm changes'}).click();
  await expect(page.getByRole('heading', {name:/Current plan/})).toBeVisible();

  await page.goto('/assistant');
  await page.getByLabel('Your request').fill('Compare my homes, explain the agreement deposit, and update my moving plan');
  await page.getByRole('button', {name:'Send'}).click();
  await expect(page.getByText('housing · completed', {exact:true})).toBeVisible({timeout:30000});
  await expect(page.getByText('document · completed', {exact:true})).toBeVisible();
  await expect(page.getByText('planning · completed', {exact:true})).toBeVisible();
  await expect(page.getByText(/Proposed plan version/)).toBeVisible();
  await page.getByRole('button', {name:'Confirm changes'}).click();
  await page.screenshot({path:path.resolve('../docs/screenshots/assistant-mock.png'),fullPage:true});
  await page.reload();
  await expect(page.getByRole('heading', {name:'MoveWise Assistant'})).toBeVisible();
});

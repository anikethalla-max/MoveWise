import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./tests',
  fullyParallel:false,
  use:{baseURL:'http://localhost:3000'},
  webServer:[
    {command:'python scripts/e2e_server.py',cwd:'../backend',url:'http://localhost:8000/api/v1/health',reuseExistingServer:false,timeout:120000},
    {command:'npm run dev',url:'http://localhost:3000',reuseExistingServer:false,timeout:120000,
      env:{NEXT_PUBLIC_API_URL:'http://localhost:8000/api/v1',NEXT_PUBLIC_EVALUATION_MOCK_MODE:'true'}},
  ],
});

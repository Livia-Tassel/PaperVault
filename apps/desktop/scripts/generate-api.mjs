import { writeFile } from 'node:fs/promises';
import openapiTS, { astToString } from 'openapi-typescript';

const base = process.env.PAPERVAULT_API_URL || 'http://127.0.0.1:8765/api/v1';
const token = process.env.PAPERVAULT_API_TOKEN || 'dev-token';
const response = await fetch(`${base}/openapi.json`, { headers: { Authorization: `Bearer ${token}` } });
if (!response.ok) throw new Error(`OpenAPI schema request failed (${response.status})`);
const schema = await response.json();
const types = await openapiTS(schema, { defaultNonNullable: false });
await writeFile(new URL('../src/api.generated.ts', import.meta.url), astToString(types));
console.log('Generated src/api.generated.ts from the running backend schema.');

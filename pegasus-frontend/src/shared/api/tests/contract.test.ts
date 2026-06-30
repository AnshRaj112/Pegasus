import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
const syncScript = path.join(repoRoot, 'scripts', 'sync_openapi_contract.py');

describe('API contract', () => {
  it('frontend HTTP clients only call paths declared in api/openapi.yaml', () => {
    const output = execSync(`python3 "${syncScript}" --check-frontend`, {
      cwd: repoRoot,
      encoding: 'utf8',
    });
    expect(output).toContain('Frontend clients are covered');
  });
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {
  loadManifest,
  validateManifest,
  validateSkill,
  validateSkillPack,
  getCatalog,
} from '../src/catalog.js';

test('catalog: validates real repository manifest and skills', () => {
  const rootDir = path.resolve(import.meta.dirname, '..');
  const catalog = getCatalog(rootDir);
  assert.equal(catalog.manifest.name, 'sigmaskills');
  assert.equal(catalog.manifest.version, '0.1.0');
  assert.equal(catalog.manifest.schemaVersion, 1);
  assert.ok(Array.isArray(catalog.skills));
  assert.ok(catalog.skills.length >= 1);

  for (const skill of catalog.skills) {
    assert.ok(skill.id);
    assert.ok(skill.title);
    assert.ok(skill.description);
    assert.match(skill.revision, /^[a-f0-9]{64}$/);
    assert.ok(skill.files);
    assert.ok(Object.keys(skill.files).length > 0);
  }
});

test('catalog: rejects manifest with missing schemaVersion or version or name', () => {
  assert.throws(
    () => validateManifest({ name: 'sigmaskills', skills: [] }),
    /missing schemaVersion/i,
  );
  assert.throws(
    () => validateManifest({ schemaVersion: 1, skills: [] }),
    /missing name/i,
  );
  assert.throws(
    () => validateManifest({ schemaVersion: 1, name: 'sigmaskills' }),
    /missing version/i,
  );
  assert.throws(
    () => validateManifest({ schemaVersion: 1, name: 'sigmaskills', version: '0.1.0' }),
    /missing skills array/i,
  );
});

test('catalog: rejects skill with missing SKILL.md', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-missing-skillmd-'));
  try {
    const skillDir = path.join(tmpDir, 'badskill');
    fs.mkdirSync(skillDir, { recursive: true });
    assert.throws(
      () => validateSkill(skillDir, { id: 'badskill', title: 'Bad Skill' }),
      /missing SKILL\.md/i,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('catalog: rejects skill with mismatched frontmatter name', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-mismatch-'));
  try {
    const skillDir = path.join(tmpDir, 'badskill');
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(
      path.join(skillDir, 'SKILL.md'),
      '---\nname: differentskill\ndescription: Some desc\n---\n# Bad Skill\n\n## Personal instructions\n\n<sigmaskills-custom>\n</sigmaskills-custom>\n',
      'utf8',
    );
    assert.throws(
      () => validateSkill(skillDir, { id: 'badskill', title: 'Bad Skill' }),
      /frontmatter name 'differentskill' does not match skill id 'badskill'/i,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('catalog: rejects skill with missing agents/openai.yaml', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-missing-yaml-'));
  try {
    const skillDir = path.join(tmpDir, 'goodskill');
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(
      path.join(skillDir, 'SKILL.md'),
      '---\nname: goodskill\ndescription: Valid description\n---\n# Good Skill\n\n## Personal instructions\n\n<sigmaskills-custom>\n</sigmaskills-custom>\n',
      'utf8',
    );
    assert.throws(
      () => validateSkill(skillDir, { id: 'goodskill', title: 'Good Skill' }),
      /missing agents\/openai\.yaml/i,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('catalog: rejects skill with missing references directory when required', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-missing-ref-'));
  try {
    const skillDir = path.join(tmpDir, 'refskill');
    fs.mkdirSync(path.join(skillDir, 'agents'), { recursive: true });
    fs.writeFileSync(
      path.join(skillDir, 'SKILL.md'),
      '---\nname: refskill\ndescription: Valid description\n---\n# Ref Skill\n\n## Personal instructions\n\n<sigmaskills-custom>\n</sigmaskills-custom>\n',
      'utf8',
    );
    fs.writeFileSync(
      path.join(skillDir, 'agents', 'openai.yaml'),
      'display_name: Ref Skill\ndefault_prompt: $refskill\nallow_implicit_invocation: true\n',
      'utf8',
    );
    assert.throws(
      () => validateSkill(skillDir, { id: 'refskill', title: 'Ref Skill', needsReferences: true }),
      /missing required references\/ directory/i,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('catalog: rejects skill with malformed customization block', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-bad-custom-'));
  try {
    const skillDir = path.join(tmpDir, 'customskill');
    fs.mkdirSync(path.join(skillDir, 'agents'), { recursive: true });
    fs.writeFileSync(
      path.join(skillDir, 'SKILL.md'),
      '---\nname: customskill\ndescription: Valid description\n---\n# Custom Skill\n',
      'utf8',
    );
    fs.writeFileSync(
      path.join(skillDir, 'agents', 'openai.yaml'),
      'display_name: Custom Skill\ndefault_prompt: $customskill\nallow_implicit_invocation: true\n',
      'utf8',
    );
    assert.throws(
      () => validateSkill(skillDir, { id: 'customskill', title: 'Custom Skill' }),
      /missing required section: '## Personal instructions'/i,
    );
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('catalog: dynamic catalog discovery does not hardcode skill count', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sigma-cat-dynamic-'));
  try {
    const manifest = {
      schemaVersion: 1,
      name: 'sigmaskills',
      version: '0.1.0',
      skills: [
        { id: 'custom1', title: 'Custom 1', needsReferences: false },
        { id: 'custom2', title: 'Custom 2', needsReferences: false },
      ],
    };
    fs.writeFileSync(path.join(tmpDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');

    for (const skill of manifest.skills) {
      const sDir = path.join(tmpDir, skill.id);
      fs.mkdirSync(path.join(sDir, 'agents'), { recursive: true });
      fs.writeFileSync(
        path.join(sDir, 'SKILL.md'),
        `---\nname: ${skill.id}\ndescription: Description for ${skill.id}\n---\n# ${skill.title}\n\n## Personal instructions\n\n<sigmaskills-custom>\n</sigmaskills-custom>\n`,
        'utf8',
      );
      fs.writeFileSync(
        path.join(sDir, 'agents', 'openai.yaml'),
        `display_name: ${skill.title}\ndefault_prompt: $${skill.id}\nallow_implicit_invocation: true\n`,
        'utf8',
      );
    }

    const catalog = getCatalog(tmpDir);
    assert.equal(catalog.skills.length, 2);
    assert.equal(catalog.skills[0].id, 'custom1');
    assert.equal(catalog.skills[1].id, 'custom2');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

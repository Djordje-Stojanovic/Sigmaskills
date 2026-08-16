import assert from 'node:assert/strict';
import test from 'node:test';
import {
  CUSTOM_BLOCK_START,
  CUSTOM_BLOCK_END,
  SECTION_HEADING,
  validateCustomizationBlock,
  extractCustomContent,
  injectCustomContent,
} from '../src/customization.js';

test('customization: validates well-formed empty custom block', () => {
  const md = `# Sample Skill\n\nSome body text.\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`;
  const result = validateCustomizationBlock(md, 'sample');
  assert.equal(result.valid, true);
  assert.equal(result.customContent, '');
});

test('customization: validates and extracts populated custom block with multiline unicode and XML-like text', () => {
  const custom = '  - Prefer TypeScript.\n  <note>Be extra thorough</note>\n  • Unicode bullet & "quotes"\n';
  const md = `# Sample Skill\n\nSome body text.\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${custom}${CUSTOM_BLOCK_END}\n`;
  const result = validateCustomizationBlock(md, 'sample');
  assert.equal(result.valid, true);
  assert.equal(result.customContent, custom);
  assert.equal(extractCustomContent(md), custom);
});

test('customization: rejects missing section heading', () => {
  const md = `# Sample Skill\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /missing required section: '## Personal instructions'/i,
  );
});

test('customization: rejects missing start tag', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_END}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /missing opening '<sigmaskills-custom>' marker/i,
  );
});

test('customization: rejects missing end tag', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /missing closing '<\/sigmaskills-custom>' marker/i,
  );
});

test('customization: rejects duplicate start tag', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /multiple '<sigmaskills-custom>' markers/i,
  );
});

test('customization: rejects duplicate end tag', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n${CUSTOM_BLOCK_END}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /multiple '<\/sigmaskills-custom>' markers/i,
  );
});

test('customization: rejects reversed markers', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_END}\n${CUSTOM_BLOCK_START}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /closing marker appears before opening marker/i,
  );
});

test('customization: rejects markers placed before ## Personal instructions heading', () => {
  const md = `${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n# Sample Skill\n\n${SECTION_HEADING}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /markers must appear inside the '## Personal instructions' section/i,
  );
});

test('customization: rejects nested markers', () => {
  const md = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}${CUSTOM_BLOCK_START}${CUSTOM_BLOCK_END}${CUSTOM_BLOCK_END}\n`;
  assert.throws(
    () => validateCustomizationBlock(md, 'sample'),
    /multiple '<sigmaskills-custom>' markers/i,
  );
});

test('customization: injectCustomContent replaces custom block byte-for-byte', () => {
  const base = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`;
  const custom = 'My specific instructions.\nLine 2.\n';
  const injected = injectCustomContent(base, custom);
  assert.equal(
    injected,
    `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${custom}${CUSTOM_BLOCK_END}\n`,
  );
  assert.equal(extractCustomContent(injected), custom);
});

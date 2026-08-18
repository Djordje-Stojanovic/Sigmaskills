import assert from 'node:assert/strict';
import test from 'node:test';
import {
  CUSTOM_BLOCK_START,
  CUSTOM_BLOCK_END,
  SECTION_HEADING,
  validateCustomizationBlock,
  extractCustomContent,
  extractRawCustomContent,
  injectCustomContent,
  injectRawCustomContent,
  diagnoseCustomizationMarkers,
  applyProposedRepair,
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

test('customization: raw bytes between tags survive inject including CRLF and no final newline', () => {
  const base = `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`;
  const raw = '\r\n  keep   spaces\r\n# heading\n<note>xml</note>\nno-final-newline';
  const injected = injectRawCustomContent(base, raw, 'sample');
  assert.equal(extractRawCustomContent(injected, 'sample'), raw);
  assert.equal(
    injected.slice(
      injected.indexOf(CUSTOM_BLOCK_START) + CUSTOM_BLOCK_START.length,
      injected.indexOf(CUSTOM_BLOCK_END),
    ),
    raw,
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

test('customization: diagnose offers exact empty-block repair for missing markers and never classifies nearby user text', () => {
  const md = `# Sample Skill\n\nKeep this prose.\n\n${SECTION_HEADING}\n\nuser notes with • unicode and <note>xml</note>\n`;
  const diagnosis = diagnoseCustomizationMarkers(md, 'sample');
  assert.equal(diagnosis.status, 'malformed');
  assert.equal(diagnosis.shape, 'missing-markers');
  assert.equal(diagnosis.repairable, true);
  assert.equal(
    diagnosis.proposedRepair,
    `# Sample Skill\n\nKeep this prose.\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\nuser notes with • unicode and <note>xml</note>\n`,
  );
  assert.equal(extractCustomContent(diagnosis.proposedRepair, 'sample'), '');
  assert.match(diagnosis.proposedRepair, /user notes with • unicode and <note>xml<\/note>/);
});

test('customization: diagnose preserves CRLF when inserting a missing empty block', () => {
  const md = `# Sample Skill\r\n\r\n${SECTION_HEADING}\r\n`;
  const diagnosis = diagnoseCustomizationMarkers(md, 'sample');
  assert.equal(diagnosis.repairable, true);
  assert.equal(
    diagnosis.proposedRepair,
    `# Sample Skill\r\n\r\n${SECTION_HEADING}\r\n\r\n${CUSTOM_BLOCK_START}\r\n${CUSTOM_BLOCK_END}\r\n`,
  );
});

test('customization: diagnose inserts the heading before a unique well-ordered marker pair', () => {
  const md = `# Sample Skill\n${CUSTOM_BLOCK_START}\nkeep\n${CUSTOM_BLOCK_END}\n`;
  const diagnosis = diagnoseCustomizationMarkers(md, 'sample');
  assert.equal(diagnosis.shape, 'missing-heading');
  assert.equal(diagnosis.repairable, true);
  assert.equal(
    diagnosis.proposedRepair,
    `# Sample Skill\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\nkeep\n${CUSTOM_BLOCK_END}\n`,
  );
  assert.equal(extractCustomContent(diagnosis.proposedRepair, 'sample'), 'keep\n');
});

test('customization: diagnose swaps reversed empty markers and refuses reversed markers that enclose user text', () => {
  const empty = `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_END}\n${CUSTOM_BLOCK_START}\n`;
  const emptyDiagnosis = diagnoseCustomizationMarkers(empty, 'sample');
  assert.equal(emptyDiagnosis.shape, 'reversed');
  assert.equal(emptyDiagnosis.repairable, true);
  assert.equal(
    emptyDiagnosis.proposedRepair,
    `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`,
  );

  const classified = `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_END}\nmine\n${CUSTOM_BLOCK_START}\n`;
  const classifiedDiagnosis = diagnoseCustomizationMarkers(classified, 'sample');
  assert.equal(classifiedDiagnosis.shape, 'reversed');
  assert.equal(classifiedDiagnosis.repairable, false);
  assert.equal(classifiedDiagnosis.proposedRepair, undefined);
});

test('customization: duplicate, nested, and one-sided markers are malformed and not repairable', () => {
  const cases = [
    `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`,
    `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}${CUSTOM_BLOCK_START}${CUSTOM_BLOCK_END}${CUSTOM_BLOCK_END}\n`,
    `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}\n`,
    `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_END}\n`,
  ];
  for (const md of cases) {
    const diagnosis = diagnoseCustomizationMarkers(md, 'sample');
    assert.equal(diagnosis.status, 'malformed');
    assert.equal(diagnosis.repairable, false);
  }
});

test('customization: marker-like text and mixed line endings stay exact and are not guessed', () => {
  const custom = 'Use <sigmaskills-customization> as a phrase and keep </not-a-marker>.\n';
  const md = `# Sample Skill\n\n${SECTION_HEADING}\r\n\n${CUSTOM_BLOCK_START}\n${custom}${CUSTOM_BLOCK_END}\n`;
  const diagnosis = diagnoseCustomizationMarkers(md, 'sample');
  assert.equal(diagnosis.status, 'valid');
  assert.equal(diagnosis.customContent, custom);

  const mixedMissing = `# Sample Skill\r\n\n${SECTION_HEADING}\nbody\r\n`;
  const repaired = diagnoseCustomizationMarkers(mixedMissing, 'sample');
  assert.equal(repaired.repairable, true);
  assert.equal(extractCustomContent(repaired.proposedRepair, 'sample'), '');
  assert.match(repaired.proposedRepair, /body/);
});

test('customization: applyProposedRepair writes only approved bytes and rejects editor or invalid repairs', () => {
  const missing = `# Sample Skill\n\n${SECTION_HEADING}\n`;
  const repaired = applyProposedRepair(missing, 'sample');
  assert.equal(
    repaired,
    `# Sample Skill\n\n${SECTION_HEADING}\n\n${CUSTOM_BLOCK_START}\n${CUSTOM_BLOCK_END}\n`,
  );

  assert.throws(
    () => applyProposedRepair(`# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}\n`, 'sample'),
    /invalid repair/i,
  );

  assert.throws(
    () => applyProposedRepair(missing, 'sample', {
      editor: () => { throw new Error('editor failed'); },
    }),
    /editor failed/,
  );

  assert.throws(
    () => applyProposedRepair(missing, 'sample', {
      editor: () => `# Sample Skill\n\n${SECTION_HEADING}\n${CUSTOM_BLOCK_START}\n`,
    }),
    /invalid repair|editor/i,
  );
});

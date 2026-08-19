export const CUSTOM_BLOCK_START = '<sigmaskills-custom>';
export const CUSTOM_BLOCK_END = '</sigmaskills-custom>';
export const SECTION_HEADING = '## Personal instructions';

/**
 * Validate that markdown content contains exactly one well-formed customization block
 * under the '## Personal instructions' section.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @returns {{ valid: boolean, customContent: string }}
 */
export function validateCustomizationBlock(markdownContent, skillId = 'skill') {
  if (typeof markdownContent !== 'string') {
    throw new TypeError(`${skillId}: markdown content must be a string`);
  }

  const headingIndex = markdownContent.indexOf(SECTION_HEADING);
  if (headingIndex === -1) {
    throw new Error(`${skillId}: missing required section: '${SECTION_HEADING}'`);
  }

  // Count occurrences of tags in the entire file
  const startMatches = markdownContent.match(new RegExp(escapeRegExp(CUSTOM_BLOCK_START), 'g')) || [];
  const endMatches = markdownContent.match(new RegExp(escapeRegExp(CUSTOM_BLOCK_END), 'g')) || [];

  if (startMatches.length === 0) {
    throw new Error(`${skillId}: missing opening '${CUSTOM_BLOCK_START}' marker`);
  }
  if (startMatches.length > 1) {
    throw new Error(`${skillId}: multiple '${CUSTOM_BLOCK_START}' markers found`);
  }
  if (endMatches.length === 0) {
    throw new Error(`${skillId}: missing closing '${CUSTOM_BLOCK_END}' marker`);
  }
  if (endMatches.length > 1) {
    throw new Error(`${skillId}: multiple '${CUSTOM_BLOCK_END}' markers found`);
  }

  const startIndex = markdownContent.indexOf(CUSTOM_BLOCK_START);
  const endIndex = markdownContent.indexOf(CUSTOM_BLOCK_END);

  if (startIndex < headingIndex || endIndex < headingIndex) {
    throw new Error(`${skillId}: markers must appear inside the '${SECTION_HEADING}' section`);
  }

  if (endIndex < startIndex) {
    throw new Error(`${skillId}: closing marker appears before opening marker`);
  }

  const customContent = markdownContent.slice(
    startIndex + CUSTOM_BLOCK_START.length,
    endIndex,
  );

  // If there is a leading newline after <sigmaskills-custom>, strip it if it's the standard container newline,
  // but keep custom content as extracted
  let normalizedCustomContent = customContent;
  if (normalizedCustomContent.startsWith('\r\n')) {
    normalizedCustomContent = normalizedCustomContent.slice(2);
  } else if (normalizedCustomContent.startsWith('\n')) {
    normalizedCustomContent = normalizedCustomContent.slice(1);
  }

  return {
    valid: true,
    customContent: normalizedCustomContent,
    rawCustomContent: customContent,
  };
}

function countOccurrences(haystack, needle) {
  let count = 0;
  let index = 0;
  while (needle && (index = haystack.indexOf(needle, index)) !== -1) {
    count += 1;
    index += needle.length;
  }
  return count;
}

function dominantEol(markdown) {
  return markdown.includes('\r\n') ? '\r\n' : '\n';
}

function isWhitespaceOnly(text) {
  return text.length === 0 || /^[\r\n \t]*$/.test(text);
}

function stripLeadingEols(text) {
  let index = 0;
  while (index < text.length) {
    if (text.startsWith('\r\n', index)) index += 2;
    else if (text[index] === '\n') index += 1;
    else break;
  }
  return text.slice(index);
}

function insertEmptyBlockAfterHeading(markdown) {
  const eol = dominantEol(markdown);
  const headingIndex = markdown.indexOf(SECTION_HEADING);
  const headingEnd = headingIndex + SECTION_HEADING.length;
  const rest = stripLeadingEols(markdown.slice(headingEnd));
  return `${markdown.slice(0, headingEnd)}${eol}${eol}${CUSTOM_BLOCK_START}${eol}${CUSTOM_BLOCK_END}${eol}${rest}`;
}

function insertHeadingBeforeStart(markdown) {
  const eol = dominantEol(markdown);
  const startIndex = markdown.indexOf(CUSTOM_BLOCK_START);
  return `${markdown.slice(0, startIndex)}${SECTION_HEADING}${eol}${eol}${markdown.slice(startIndex)}`;
}

function swapReversedWhitespacePair(markdown) {
  const endIndex = markdown.indexOf(CUSTOM_BLOCK_END);
  const startIndex = markdown.indexOf(CUSTOM_BLOCK_START);
  const mid = markdown.slice(endIndex + CUSTOM_BLOCK_END.length, startIndex);
  return `${markdown.slice(0, endIndex)}${CUSTOM_BLOCK_START}${mid}${CUSTOM_BLOCK_END}${markdown.slice(startIndex + CUSTOM_BLOCK_START.length)}`;
}

/**
 * Diagnose marker shapes without guessing user-text boundaries.
 * Unique mechanical repairs never wrap existing user bytes as Skill Customization.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @returns {{
 *   status: 'valid' | 'empty' | 'absent' | 'malformed',
 *   shape: string,
 *   error?: string,
 *   repairable: boolean,
 *   proposedRepair?: string,
 *   customContent?: string,
 * }}
 */
export function diagnoseCustomizationMarkers(markdownContent, skillId = 'skill') {
  if (typeof markdownContent !== 'string') {
    return {
      status: 'malformed',
      shape: 'not-string',
      error: `${skillId}: markdown content must be a string`,
      repairable: false,
    };
  }

  const startCount = countOccurrences(markdownContent, CUSTOM_BLOCK_START);
  const endCount = countOccurrences(markdownContent, CUSTOM_BLOCK_END);
  const headingIndex = markdownContent.indexOf(SECTION_HEADING);

  try {
    const result = validateCustomizationBlock(markdownContent, skillId);
    return {
      status: result.customContent ? 'valid' : 'empty',
      shape: 'well-formed',
      repairable: false,
      customContent: result.customContent,
    };
  } catch (err) {
    const error = err.message;
    if (startCount === 0 && endCount === 0 && headingIndex !== -1) {
      return {
        status: 'malformed',
        shape: 'missing-markers',
        error,
        repairable: true,
        proposedRepair: insertEmptyBlockAfterHeading(markdownContent),
      };
    }
    if (startCount === 0 && endCount === 0 && headingIndex === -1) {
      return {
        status: 'malformed',
        shape: 'missing-markers',
        error,
        repairable: false,
      };
    }
    if (headingIndex === -1 && startCount === 1 && endCount === 1) {
      const startIndex = markdownContent.indexOf(CUSTOM_BLOCK_START);
      const endIndex = markdownContent.indexOf(CUSTOM_BLOCK_END);
      if (startIndex < endIndex) {
        return {
          status: 'malformed',
          shape: 'missing-heading',
          error,
          repairable: true,
          proposedRepair: insertHeadingBeforeStart(markdownContent),
        };
      }
    }
    if (startCount === 1 && endCount === 1) {
      const startIndex = markdownContent.indexOf(CUSTOM_BLOCK_START);
      const endIndex = markdownContent.indexOf(CUSTOM_BLOCK_END);
      if (endIndex < startIndex) {
        const mid = markdownContent.slice(endIndex + CUSTOM_BLOCK_END.length, startIndex);
        const repairable = isWhitespaceOnly(mid) && headingIndex !== -1 && endIndex > headingIndex;
        return {
          status: 'malformed',
          shape: 'reversed',
          error,
          repairable,
          proposedRepair: repairable ? swapReversedWhitespacePair(markdownContent) : undefined,
        };
      }
    }
    let shape = 'malformed';
    if (startCount > 1 && endCount > 1) shape = 'nested';
    else if (startCount > 1) shape = 'duplicate-start';
    else if (endCount > 1) shape = 'duplicate-end';
    else if (startCount === 0) shape = 'missing-start';
    else if (endCount === 0) shape = 'missing-end';
    else if (headingIndex === -1) shape = 'missing-heading';
    else if (markdownContent.indexOf(CUSTOM_BLOCK_START) < headingIndex) shape = 'outside-section';
    return {
      status: 'malformed',
      shape,
      error,
      repairable: false,
    };
  }
}

/**
 * Return exact approved repair bytes. Never infers marker boundaries.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @param {{ editor?: (bytes: string) => string }} [options]
 * @returns {string}
 */
export function applyProposedRepair(markdownContent, skillId = 'skill', options = {}) {
  const diagnosis = diagnoseCustomizationMarkers(markdownContent, skillId);
  if (!diagnosis.repairable || typeof diagnosis.proposedRepair !== 'string') {
    throw new Error(`${skillId}: invalid repair; marker boundaries cannot be inferred`);
  }
  let bytes = diagnosis.proposedRepair;
  if (typeof options.editor === 'function') {
    bytes = options.editor(bytes);
  }
  if (typeof bytes !== 'string') {
    throw new Error(`${skillId}: editor produced invalid repair bytes`);
  }
  const after = diagnoseCustomizationMarkers(bytes, skillId);
  if (after.status !== 'valid' && after.status !== 'empty') {
    throw new Error(`${skillId}: editor produced invalid repair`);
  }
  return bytes;
}

/**
 * Inspect customization markers without guessing. Absent markers stay absent;
 * malformed markers are reported and never repaired.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @returns {{ status: 'absent' | 'empty' | 'valid' | 'malformed', customContent?: string, error?: string }}
 */
export function inspectCustomizationBlock(markdownContent, skillId = 'skill') {
  if (typeof markdownContent !== 'string') {
    return { status: 'malformed', error: `${skillId}: markdown content must be a string` };
  }

  const hasStart = markdownContent.includes(CUSTOM_BLOCK_START);
  const hasEnd = markdownContent.includes(CUSTOM_BLOCK_END);
  if (!hasStart && !hasEnd) {
    return { status: 'absent' };
  }

  try {
    const result = validateCustomizationBlock(markdownContent, skillId);
    return {
      status: result.customContent ? 'valid' : 'empty',
      customContent: result.customContent,
    };
  } catch (err) {
    return { status: 'malformed', error: err.message };
  }
}

/**
 * Extract the user-customized instructions from a skill markdown string.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @returns {string}
 */
export function extractCustomContent(markdownContent, skillId = 'skill') {
  const result = validateCustomizationBlock(markdownContent, skillId);
  return result.customContent;
}

/**
 * Exact bytes between the customization markers, including leading newlines.
 *
 * @param {string} markdownContent
 * @param {string} [skillId]
 * @returns {string}
 */
export function extractRawCustomContent(markdownContent, skillId = 'skill') {
  validateCustomizationBlock(markdownContent, skillId);
  const startIndex = markdownContent.indexOf(CUSTOM_BLOCK_START);
  const endIndex = markdownContent.indexOf(CUSTOM_BLOCK_END);
  return markdownContent.slice(startIndex + CUSTOM_BLOCK_START.length, endIndex);
}

/**
 * Replace bytes between customization markers without normalizing newlines.
 *
 * @param {string} baseMarkdownContent
 * @param {string} rawCustomContent
 * @param {string} [skillId]
 * @returns {string}
 */
export function injectRawCustomContent(baseMarkdownContent, rawCustomContent, skillId = 'skill') {
  validateCustomizationBlock(baseMarkdownContent, skillId);
  const startIndex = baseMarkdownContent.indexOf(CUSTOM_BLOCK_START);
  const endIndex = baseMarkdownContent.indexOf(CUSTOM_BLOCK_END);
  return `${baseMarkdownContent.slice(0, startIndex + CUSTOM_BLOCK_START.length)}${rawCustomContent}${baseMarkdownContent.slice(endIndex)}`;
}

/**
 * Inject user-customized instructions into a base skill markdown string.
 *
 * @param {string} baseMarkdownContent
 * @param {string} customContent
 * @param {string} [skillId]
 * @returns {string}
 */
export function injectCustomContent(baseMarkdownContent, customContent, skillId = 'skill') {
  validateCustomizationBlock(baseMarkdownContent, skillId);

  const startIndex = baseMarkdownContent.indexOf(CUSTOM_BLOCK_START);
  const endIndex = baseMarkdownContent.indexOf(CUSTOM_BLOCK_END);

  const before = baseMarkdownContent.slice(0, startIndex + CUSTOM_BLOCK_START.length);
  const after = baseMarkdownContent.slice(endIndex);

  const formattedCustom = customContent ? `\n${customContent}` : '\n';
  return `${before}${formattedCustom}${after}`;
}

export function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}


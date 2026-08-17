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


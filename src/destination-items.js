import { UNIVERSAL_PROJECT_DESTINATION, searchHosts } from './destinations.js';

export function visibleDestinationItems(items, cursor, limit) {
  if (!items.length || items.length <= limit) {
    return { items, start: 0, total: items.length };
  }
  const half = Math.floor(limit / 2);
  let start = Math.max(0, cursor - half);
  if (start + limit > items.length) start = items.length - limit;
  return {
    items: items.slice(start, start + limit),
    start,
    total: items.length,
  };
}

export function destinationRowTitle(item) {
  const detectedMark = item.detected || (item.hosts || []).some((host) => host.detected)
    ? ' [detected]'
    : '';
  if (item.kind === 'host') {
    return `${item.relativeRoot}  ${item.displayName} (${item.id})${detectedMark}`;
  }
  const hosts = item.hosts || [];
  const detectedCount = hosts.filter((host) => host.detected).length;
  if (item.universal) {
    const extra = detectedCount ? ` · ${detectedCount} detected` : '';
    return `${item.relativeRoot}  (universal default · ${hosts.length} hosts${extra})`;
  }
  if (hosts.length <= 2) {
    const names = hosts.map((host) => host.displayName).join(', ');
    const ids = hosts.map((host) => host.id).join(', ');
    return `${item.relativeRoot}  ${names} (${ids})${detectedMark}`;
  }
  return `${item.relativeRoot}  ${hosts[0].displayName} +${hosts.length - 1}${detectedMark}`;
}

export function selectableGroups(groups) {
  return groups.filter((group) => group.selectable);
}

export function pickerItems(groups, query) {
  if (query) {
    const matches = searchHosts(groups, query).filter((host) => host.relativeRoot);
    const byRoot = new Map();
    for (const host of matches) {
      const existing = byRoot.get(host.relativeRoot);
      if (!existing) {
        byRoot.set(host.relativeRoot, {
          kind: 'host',
          id: host.id,
          displayName: host.displayName,
          relativeRoot: host.relativeRoot,
          absoluteRoot: host.group?.absoluteRoot || '',
          detected: host.detected,
          universal: host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION,
          hosts: [host],
        });
        continue;
      }
      existing.hosts.push(host);
      existing.detected = existing.detected || host.detected;
      existing.kind = 'group';
      existing.universal = existing.universal || host.relativeRoot === UNIVERSAL_PROJECT_DESTINATION;
    }
    return [...byRoot.values()];
  }
  return selectableGroups(groups).map((group) => ({
    kind: 'group',
    relativeRoot: group.relativeRoot,
    absoluteRoot: group.absoluteRoot,
    universal: group.universal,
    hosts: group.hosts,
  }));
}

export function isSearchChar(key) {
  if (!key) return false;
  if (key.name === 'space' || key.name === 'return' || key.name === 'escape') return false;
  const ch = key.ch || '';
  if (ch.length === 1 && /[A-Za-z0-9._/-]/.test(ch)) return true;
  return Boolean(key.name && key.name.length === 1 && /[A-Za-z0-9._/-]/.test(key.name));
}

export type CachedBrowseFile = {
  id: string;
  name: string;
  objectName: string;
  type: 'file' | 'folder';
  size: string;
  sizeBytes: number | null;
  createdAt: string;
  modifiedAt: string;
  owner: string;
  createdBy: string;
  bucket?: string;
  connectionId?: string;
};

export type BrowsePathSnapshot = {
  entries: CachedBrowseFile[];
  parentPrefix: string | null;
  error: string | null;
  fetchedAt: number;
};

const STORAGE_KEY = 'pegasus.validation.connectionBrowseCache';
const CACHE_TTL_MS = 30 * 60 * 1000;
const MAX_CONNECTIONS = 20;
const MAX_PATHS_PER_CONNECTION = 80;

type ConnectionBrowseCache = {
  paths: Record<string, BrowsePathSnapshot>;
};

type BrowseCacheStore = Record<string, ConnectionBrowseCache>;

const memoryStore = new Map<string, BrowsePathSnapshot>();

export const normalizeBrowseBucket = (bucket: string | null | undefined): string =>
  (bucket ?? '').trim();

const pathKey = (bucket: string | null | undefined, prefix: string): string =>
  `${normalizeBrowseBucket(bucket)}:${prefix}`;

const memoryKey = (
  connectionId: string,
  bucket: string | null | undefined,
  prefix: string,
): string => `${connectionId}:${pathKey(bucket, prefix)}`;

const readStore = (): BrowseCacheStore => {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as BrowseCacheStore;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
};

const writeStore = (store: BrowseCacheStore) => {
  const connectionIds = Object.keys(store);
  if (connectionIds.length > MAX_CONNECTIONS) {
    const ranked = connectionIds
      .map((id) => ({
        id,
        latest: Math.max(...Object.values(store[id]?.paths ?? {}).map((p) => p.fetchedAt), 0),
      }))
      .sort((a, b) => b.latest - a.latest)
      .slice(0, MAX_CONNECTIONS);
    const trimmed: BrowseCacheStore = {};
    for (const { id } of ranked) trimmed[id] = store[id];
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    return;
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store));
};

const trimConnectionPaths = (connection: ConnectionBrowseCache): ConnectionBrowseCache => {
  const keys = Object.keys(connection.paths);
  if (keys.length <= MAX_PATHS_PER_CONNECTION) return connection;
  const ranked = keys
    .sort((a, b) => connection.paths[b].fetchedAt - connection.paths[a].fetchedAt)
    .slice(0, MAX_PATHS_PER_CONNECTION);
  const paths: Record<string, BrowsePathSnapshot> = {};
  for (const key of ranked) paths[key] = connection.paths[key];
  return { paths };
};

const readSessionPath = (
  connectionId: string,
  bucket: string | null | undefined,
  prefix: string,
): BrowsePathSnapshot | null => {
  const connection = readStore()[connectionId];
  if (!connection) return null;
  return connection.paths[pathKey(bucket, prefix)] ?? null;
};

export const getConnectionBrowsePath = (
  connectionId: string,
  bucket: string | null | undefined,
  prefix: string,
): BrowsePathSnapshot | null => {
  const mem = memoryStore.get(memoryKey(connectionId, bucket, prefix));
  if (mem) return mem;
  const session = readSessionPath(connectionId, bucket, prefix);
  if (session) {
    memoryStore.set(memoryKey(connectionId, bucket, prefix), session);
  }
  return session;
};

export const isBrowsePathFresh = (entry: BrowsePathSnapshot): boolean =>
  Date.now() - entry.fetchedAt < CACHE_TTL_MS;

export const setConnectionBrowsePath = (
  connectionId: string,
  bucket: string | null | undefined,
  prefix: string,
  snapshot: Omit<BrowsePathSnapshot, 'fetchedAt'>,
) => {
  const stored: BrowsePathSnapshot = { ...snapshot, fetchedAt: Date.now() };
  const normalizedBucket = normalizeBrowseBucket(bucket);
  const key = pathKey(normalizedBucket, prefix);

  memoryStore.set(memoryKey(connectionId, normalizedBucket, prefix), stored);

  const store = readStore();
  const existing = store[connectionId] ?? { paths: {} };
  const paths = { ...existing.paths, [key]: stored };
  store[connectionId] = trimConnectionPaths({ paths });
  writeStore(store);
};

export const clearConnectionBrowseCache = () => {
  memoryStore.clear();
  sessionStorage.removeItem(STORAGE_KEY);
};

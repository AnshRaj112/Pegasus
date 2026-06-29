/** Resolve the in-app path when using createHashRouter (window.location.pathname is not the route). */
export const getRouterPath = (): string => {
  if (typeof window === 'undefined') return '/';

  const hash = window.location.hash;
  if (!hash || hash === '#') return '/';

  const path = hash.startsWith('#') ? hash.slice(1) : hash;
  return path.startsWith('/') ? path : `/${path}`;
};

/**
 * Hash routing expects URLs like `http://host:port/#/login`.
 * Any non-root pathname (e.g. `/sdfghj#/login`) is invalid.
 */
export const isValidAppPathname = (pathname: string): boolean => {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  return normalized === '/';
};

export const hasInvalidAppPathname = (): boolean => {
  if (typeof window === 'undefined') return false;
  return !isValidAppPathname(window.location.pathname);
};

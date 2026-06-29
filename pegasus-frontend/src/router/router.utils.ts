/** Resolve the in-app path when using createHashRouter (window.location.pathname is not the route). */
export const getRouterPath = (): string => {
  if (typeof window === 'undefined') return '/';

  const hash = window.location.hash;
  if (!hash || hash === '#') return '/';

  const path = hash.startsWith('#') ? hash.slice(1) : hash;
  return path.startsWith('/') ? path : `/${path}`;
};

export type SnippetSectionKey = 'mismatches' | 'extras' | 'missing';

export const SNIPPET_SECTION_KEYS: SnippetSectionKey[] = ['mismatches', 'extras', 'missing'];

export type SectionRowPagination = {
  rowPage: number;
  itemsPerPage: number;
};

export type SectionTabularPagination = SectionRowPagination & {
  colPage: number;
};

export const createRowPaginationState = (): Record<SnippetSectionKey, SectionRowPagination> => ({
  mismatches: { rowPage: 0, itemsPerPage: 10 },
  extras: { rowPage: 0, itemsPerPage: 10 },
  missing: { rowPage: 0, itemsPerPage: 10 },
});

export const createTabularPaginationState = (): Record<SnippetSectionKey, SectionTabularPagination> => ({
  mismatches: { rowPage: 0, itemsPerPage: 10, colPage: 0 },
  extras: { rowPage: 0, itemsPerPage: 10, colPage: 0 },
  missing: { rowPage: 0, itemsPerPage: 10, colPage: 0 },
});

export const paginateRows = <T,>(rows: T[], pagination: SectionRowPagination): T[] => {
  const { rowPage, itemsPerPage } = pagination;
  return rows.slice(rowPage * itemsPerPage, (rowPage + 1) * itemsPerPage);
};

export const totalRowPages = (rowCount: number, itemsPerPage: number): number =>
  Math.max(1, Math.ceil(rowCount / itemsPerPage));

export const clampRowPage = (rowPage: number, rowCount: number, itemsPerPage: number): number => {
  const maxPage = totalRowPages(rowCount, itemsPerPage) - 1;
  return Math.min(rowPage, Math.max(0, maxPage));
};

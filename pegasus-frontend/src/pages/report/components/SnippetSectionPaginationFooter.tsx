import React from 'react';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';

import {
  SectionRowPagination,
  SnippetSectionKey,
  clampRowPage,
  totalRowPages,
} from './snippetSectionPagination';
import styles from './SnippetSectionPagination.module.scss';

type SnippetSectionPaginationFooterProps = {
  sectionKey: SnippetSectionKey;
  sectionLabel: string;
  rowCount: number;
  pagination: SectionRowPagination;
  isLoading?: boolean;
  note?: string;
  onChange: (section: SnippetSectionKey, patch: Partial<SectionRowPagination>) => void;
};

export const SnippetSectionPaginationFooter: React.FC<SnippetSectionPaginationFooterProps> = ({
  sectionKey,
  sectionLabel,
  rowCount,
  pagination,
  isLoading = false,
  note,
  onChange,
}) => {
  const { rowPage, itemsPerPage } = pagination;
  const pages = totalRowPages(rowCount, itemsPerPage);

  return (
    <div className={styles.footer}>
      <span className={styles.footerNote}>
        {note ?? `${sectionLabel} — page ${rowCount ? rowPage + 1 : 0} of ${pages}`}
      </span>
      <div className={styles.footerControls}>
        <div className={styles.rowsPerPage}>
          Rows per page:
          <select
            value={itemsPerPage}
            onChange={(e) => onChange(sectionKey, {
              itemsPerPage: Number(e.target.value),
              rowPage: 0,
            })}
            className={styles.rowsPerPageSelect}
          >
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>
        <div className={styles.pagination}>
          <button
            type="button"
            disabled={rowPage <= 0}
            onClick={() => rowPage > 0 && onChange(sectionKey, { rowPage: rowPage - 1 })}
            className={`${styles.paginationIcon} ${rowPage <= 0 ? styles.paginationIconDisabled : styles.paginationIconEnabled}`}
          >
            <LeftOutlined />
          </button>
          <span className={styles.paginationLabel}>
            {isLoading ? '—' : (rowCount ? rowPage + 1 : 0)}
            <span className={styles.paginationDivider}>/</span>
            {isLoading ? '—' : pages}
          </span>
          <button
            type="button"
            disabled={rowPage >= pages - 1}
            onClick={() => rowPage < pages - 1 && onChange(sectionKey, { rowPage: rowPage + 1 })}
            className={`${styles.paginationIcon} ${rowPage >= pages - 1 ? styles.paginationIconDisabled : styles.paginationIconEnabled}`}
          >
            <RightOutlined />
          </button>
        </div>
      </div>
    </div>
  );
};

export const clampSectionRowPagination = <T extends SectionRowPagination>(
  sections: Record<SnippetSectionKey, T>,
  rowCounts: Record<SnippetSectionKey, number>,
): Record<SnippetSectionKey, T> => {
  let changed = false;
  const next = { ...sections };
  for (const key of Object.keys(sections) as SnippetSectionKey[]) {
    const clamped = clampRowPage(sections[key].rowPage, rowCounts[key], sections[key].itemsPerPage);
    if (clamped !== sections[key].rowPage) {
      next[key] = { ...sections[key], rowPage: clamped };
      changed = true;
    }
  }
  return changed ? next : sections;
};

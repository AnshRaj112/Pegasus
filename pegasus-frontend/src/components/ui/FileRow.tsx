import React from 'react';
import styles from './FileRow.module.scss';

export interface FileExplorerItem {
  id: string;
  name: string;
  size: string;
  modified: string;
  status: 'Ready' | 'Scanning';
}

interface FileRowProps {
  file: FileExplorerItem;
  isSelected: boolean;
  onToggleSelect: (id: string) => void;
}

export const FileRow: React.FC<FileRowProps> = ({ file, isSelected, onToggleSelect }) => {
  return (
    <tr
      onClick={() => onToggleSelect(file.id)}
      className={`${styles.row} ${isSelected ? styles.rowSelected : ''}`}
    >
      <td className={styles.checkboxCell} onClick={(e) => e.stopPropagation()}>
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(file.id)}
          className={styles.checkbox}
        />
      </td>
      <td className={styles.nameCell}>
        <span
          className={`material-symbols-outlined ${styles.fileIcon} ${isSelected ? styles.fileIconSelected : ''}`}
        >
          description
        </span>
        {file.name}
      </td>
      <td className={styles.metaCell}>
        {file.size}
      </td>
      <td className={styles.metaCell}>
        {file.modified}
      </td>
      <td className={styles.statusCell}>
        <span className={file.status === 'Ready' ? 'badgeReady' : 'badgeScanning'}>
          {file.status}
        </span>
      </td>
    </tr>
  );
};

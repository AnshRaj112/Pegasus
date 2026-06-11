import React from 'react';

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
      className={isSelected ? "rowSelected" : ""}
      style={{ borderBottom: '1px solid var(--outline-variant)' }}
    >
      <td style={{ padding: 'var(--md)', width: '40px' }} onClick={(e) => e.stopPropagation()}>
        <input 
          type="checkbox" 
          checked={isSelected}
          onChange={() => onToggleSelect(file.id)}
          style={{ accentColor: 'var(--primary)', cursor: 'pointer' }}
        />
      </td>
      <td style={{ padding: 'var(--md)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 'var(--xs)' }}>
        <span 
          className="material-symbols-outlined" 
          style={{ color: isSelected ? 'var(--primary)' : 'var(--outline)' }}
        >
          description
        </span>
        {file.name}
      </td>
      <td style={{ padding: 'var(--md)', fontFamily: 'var(--font-code-sm)', fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>
        {file.size}
      </td>
      <td style={{ padding: 'var(--md)', fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>
        {file.modified}
      </td>
      <td style={{ padding: 'var(--md)' }}>
        <span className={file.status === 'Ready' ? "badgeReady" : "badgeScanning"}>
          {file.status}
        </span>
      </td>
    </tr>
  );
};

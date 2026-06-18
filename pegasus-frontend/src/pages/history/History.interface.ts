export interface ValidationLogItem {
  id: string;
  sourceFile: string;
  sourceUri: string;
  targetTable: string;
  targetUri: string;
  rowCount: string;
  duration: string;
  status: 'Success' | 'Fail' | 'Pass';
}

export interface MappingLogItem {
  id: string;
  sourceSchema: string;
  sourcePath: string;
  targetSchema: string;
  targetPath: string;
  status: 'Active' | 'Draft' | 'Archived';
}

export interface HistoryReducerState {
  activeTab: 'validation' | 'mapping';
  searchQuery: string;
  pageSize: number;
  validationLogs: {
    data: ValidationLogItem[];
    total: number;
    page: number;
    isFetching: boolean;
    error: string | null;
  };
  mappingLogs: {
    data: MappingLogItem[];
    total: number;
    page: number;
    isFetching: boolean;
    error: string | null;
  };
}

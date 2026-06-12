import { type ValidationLogItem, type MappingLogItem } from './History.interface';

class HistoryService {
  async fetchValidationLogs(): Promise<ValidationLogItem[]> {
    // TODO: Replace with Axios call
    return [];
  }

  async fetchMappingLogs(): Promise<MappingLogItem[]> {
    // TODO: Replace with Axios call
    return [];
  }

  // async deleteLogRecord(type: 'validation' | 'mapping', id: string): Promise<boolean> {
  //   // TODO: Replace with Axios call
  //   return true;
  // }
}

export const historyService = new HistoryService();
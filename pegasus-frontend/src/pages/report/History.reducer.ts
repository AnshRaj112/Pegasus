import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type HistoryReducerState } from './History.interface';

export const initialState: HistoryReducerState = {
  activeTab: 'validation',
  searchQuery: '',
  validationLogs: {
    data: [
      { id: 'v1', sourceFile: 'production_sales_v2.parquet', sourceUri: 's3://data-warehouse/raw/2024/05/22/sales/sales_v2.parquet', targetTable: 'dim_sales_fact', targetUri: 'snowflake://PROD_DB/TRANSFORMED/PUBLIC/DIM_SALES_FACT', rowCount: '42,109,221 rows', duration: '2m 14s', status: 'Success' },
      { id: 'v2', sourceFile: 'customer_master_full.csv', sourceUri: 'gs://internal-audit/temp/customers_20240520.csv', targetTable: 'CRM_CORE_STAGING', targetUri: 'postgres://prod-cluster:5432/crm/staging/customer_master', rowCount: '1,244,000 rows', duration: '48s', status: 'Fail' },
      { id: 'v3', sourceFile: 'inventory_snapshot.avro', sourceUri: 's3://supply-chain/snapshots/inventory_0521.avro', targetTable: 'STG_INVENTORY', targetUri: 'redshift://analytics-dw/sc_stg/inventory_records', rowCount: '850,200 rows', duration: '1m 05s', status: 'Pass' }
    ],
    isFetching: false,
    error: null
  },
  mappingLogs: {
    data: [
      { id: 'm1', sourceSchema: 'Legacy_Orders_Schema', sourcePath: 'mysql://legacy-orders/schema_v1_2', targetSchema: 'Modern_Unified_Orders', targetPath: 'snowflake://UNIFIED/SCHEMAS/ORDERS_CORE', status: 'Active' },
      { id: 'm2', sourceSchema: 'External_API_Payload_v4', sourcePath: 'json://api-gateway/docs/v4/users.json', targetSchema: 'USER_PROFILE_TRANSFORM', targetPath: 'bigquery://prod-data/identity/users_v4', status: 'Draft' },
      { id: 'm3', sourceSchema: 'Deprecated_Customer_Feed', sourcePath: 'ftp://legacy-reports/customer_v1.csv', targetSchema: 'ARCHIVED_CUSTOMERS', targetPath: 's3://archive-storage/2023/customers/', status: 'Archived' }
    ],
    isFetching: false,
    error: null
  }
};

const historySlice = createSlice({
  name: 'history',
  initialState,
  reducers: {
    setActiveTab: (state, action: PayloadAction<'validation' | 'mapping'>) => {
      state.activeTab = action.payload;
      state.searchQuery = ''; // Reset search when switching tabs
    },
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.searchQuery = action.payload;
    },
    deleteValidationLog: (state, action: PayloadAction<string>) => {
      state.validationLogs.data = state.validationLogs.data.filter(log => log.id !== action.payload);
    },
    deleteMappingLog: (state, action: PayloadAction<string>) => {
      state.mappingLogs.data = state.mappingLogs.data.filter(log => log.id !== action.payload);
    },
    // Future-proofing fetch actions
    fetchHistoryRequest: (state) => {
      state.validationLogs.isFetching = true;
      state.mappingLogs.isFetching = true;
    }
  }
});

export const historyActions = { ...historySlice.actions };
export default historySlice.reducer;
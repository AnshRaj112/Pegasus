import { AxiosResponse } from 'axios';

import {
  Api,
  CloudBrowseRequest,
  CloudBrowseResponse,
  CloudConnection,
  CloudFileProfileRequest,
  CloudFileProfileResponse,
  FixedWidthLayoutPreviewResponse,
  LocalColumnPreviewResponse,
  SaveDraftRequest,
  ValidateRequest,
  ValidationHistoryDetail,
} from '../../shared/api/Api';

export const ValidationServiceApi = {
  browseCloud: (body: CloudBrowseRequest): Promise<AxiosResponse<CloudBrowseResponse>> =>
    Api.browseCloud(body),

  listCloudConnections: (): Promise<AxiosResponse<CloudConnection[]>> =>
    Api.listCloudConnections(),

  profileCloudFile: (body: CloudFileProfileRequest): Promise<AxiosResponse<CloudFileProfileResponse>> =>
    Api.profileCloudFile(body),

  previewValidationColumns: (body: ValidateRequest): Promise<AxiosResponse<LocalColumnPreviewResponse>> =>
    Api.previewValidationColumns(body),

  previewFixedWidthLayout: (body: ValidateRequest): Promise<AxiosResponse<FixedWidthLayoutPreviewResponse>> =>
    Api.previewFixedWidthLayout(body),

  saveValidationDraft: (body: SaveDraftRequest): Promise<AxiosResponse<ValidationHistoryDetail>> =>
    Api.saveValidationDraft(body),

  submitValidation: Api.submitValidation,
  pollJob: Api.getValidationJob,
  fetchMismatches: Api.getValidationMismatches,
  pollUntilComplete: async (jobId: string) => {
    const result = await Api.pollValidationUntilComplete(jobId);
    return {
      jobId,
      runId: result.run_id ?? null,
      status: 'Complete' as const,
      results: result,
    };
  },
};

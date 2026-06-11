import { Api } from '../../shared/api/Api';

/** @deprecated Import from `shared/api/Api` directly */
export const ValidationServiceApi = {
  browseLocal: Api.browseLocal,
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
  detectLocalFile: Api.detectLocalFile,
  previewLocalColumns: Api.previewLocalColumns,
  saveDraft: Api.saveValidationDraft,
};

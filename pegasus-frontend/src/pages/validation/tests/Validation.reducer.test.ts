import validationReducer, { initialState, validationActions } from '../Validation.reducer'
import {
  cloudConnectionsError,
  cloudConnectionsLoading,
  cloudConnectionsSuccess,
  mockBrowseResponse,
  mockCloudConnection,
  mockHistoryDetail,
  mockSaveDraftPayload,
  mockSourceCloud,
  mockValidationResult,
  submitValidationLoading,
  submitValidationSuccess,
  validationFormWithFiles,
} from '../Validation.mockData'

describe('Validation reducer', () => {
  it('returns initial state for unknown action', () => {
    expect(validationReducer(undefined, { type: 'unknown' })).toEqual(initialState)
  })

  describe('wizard navigation', () => {
    it('sets wizard step on setWizardStep', () => {
      expect(validationReducer(initialState, validationActions.setWizardStep(2)).currentStep).toBe(2)
    })

    it('sets step 1 validity on setStep1Valid', () => {
      expect(validationReducer(initialState, validationActions.setStep1Valid(true)).isStep1Valid).toBe(true)
    })

    it('resets wizard on resetWizard', () => {
      const populated = {
        ...initialState,
        currentStep: 3,
        isStep1Valid: true,
        validationForm: validationFormWithFiles,
      }
      expect(validationReducer(populated, validationActions.resetWizard())).toEqual(initialState)
    })
  })

  describe('validationForm', () => {
    it('merges form patch on setValidationForm', () => {
      const result = validationReducer(
        initialState,
        validationActions.setValidationForm({ uidColumn: 'record_id', delimiter: ',' }),
      )
      expect(result.validationForm.uidColumn).toBe('record_id')
      expect(result.validationForm.delimiter).toBe(',')
    })

    it('clears overview cache when source cloud changes', () => {
      const withCache = {
        ...initialState,
        validationForm: validationFormWithFiles,
        overviewProfileCache: {
          sourceKey: 'old',
          targetKey: 'old',
          source: null,
          target: null,
          sourceError: false,
          targetError: false,
        },
      }
      const result = validationReducer(
        withCache,
        validationActions.setValidationForm({
          sourceCloud: { ...mockSourceCloud, object_name: 'data/new-source.csv' },
        }),
      )
      expect(result.overviewProfileCache).toBeNull()
    })

    it('resets fixed-width columns when source cloud changes', () => {
      const withFixedWidth = {
        ...initialState,
        validationForm: {
          ...validationFormWithFiles,
          fixedWidthColumns: [
            {
              field_name: 'id',
              source_start: 1,
              source_end: 10,
              target_start: 1,
              target_end: 10,
              field_type: 'string',
            },
          ],
          fixedWidthLineWidth: 80,
        },
      }
      const result = validationReducer(
        withFixedWidth,
        validationActions.setValidationForm({
          sourceCloud: { ...mockSourceCloud, object_name: 'data/other.csv' },
        }),
      )
      expect(result.validationForm.fixedWidthColumns).toEqual([])
      expect(result.validationForm.fixedWidthLineWidth).toBeNull()
    })
  })

  describe('submitValidation', () => {
    it('sets loading on submitValidationRequest', () => {
      expect(validationReducer(initialState, validationActions.submitValidationRequest()).validationDataState).toEqual(
        submitValidationLoading,
      )
    })

    it('stores result on submitValidationSuccess', () => {
      expect(
        validationReducer(initialState, validationActions.submitValidationSuccess(mockValidationResult)).validationDataState,
      ).toEqual(submitValidationSuccess)
    })

    it('stores error on submitValidationError', () => {
      const result = validationReducer(initialState, validationActions.submitValidationError('Validation failed'))
      expect(result.validationDataState.error).toBe('Validation failed')
      expect(result.validationDataState.isFetching).toBe(false)
    })
  })

  describe('cloud connections', () => {
    it('sets loading on listCloudConnectionsRequest', () => {
      expect(
        validationReducer(initialState, validationActions.listCloudConnectionsRequest()).cloudConnectionsState,
      ).toEqual(cloudConnectionsLoading)
    })

    it('stores connections on listCloudConnectionsSuccess', () => {
      expect(
        validationReducer(initialState, validationActions.listCloudConnectionsSuccess([mockCloudConnection])).cloudConnectionsState,
      ).toEqual(cloudConnectionsSuccess)
    })

    it('stores error on listCloudConnectionsError', () => {
      expect(
        validationReducer(initialState, validationActions.listCloudConnectionsError('Failed to load cloud connections')).cloudConnectionsState,
      ).toEqual(cloudConnectionsError)
    })
  })

  describe('browseCloud', () => {
    it('sets loading on browseCloudRequest', () => {
      const result = validationReducer(
        initialState,
        validationActions.browseCloudRequest({
          pathId: 'conn-1:test-bucket:',
          connectionId: 'conn-1',
          bucket: 'test-bucket',
          prefix: '',
        }),
      )
      expect(result.browseCloudState.isFetching).toBe(true)
      expect(result.browseCloudState.pathId).toBe('conn-1:test-bucket:')
    })

    it('stores browse data on browseCloudSuccess', () => {
      const result = validationReducer(
        initialState,
        validationActions.browseCloudSuccess({
          pathId: 'conn-1:test-bucket:',
          connectionId: 'conn-1',
          data: mockBrowseResponse,
        }),
      )
      expect(result.browseCloudState.data).toEqual(mockBrowseResponse)
      expect(result.browseCloudState.isFetching).toBe(false)
    })

    it('stores error on browseCloudError', () => {
      const result = validationReducer(
        initialState,
        validationActions.browseCloudError({ pathId: 'conn-1:test-bucket:', error: 'Browse failed' }),
      )
      expect(result.browseCloudState.error).toBe('Browse failed')
      expect(result.browseCloudState.isFetching).toBe(false)
    })
  })

  describe('saveDraft', () => {
    it('sets loading on saveDraftRequest', () => {
      const result = validationReducer(initialState, validationActions.saveDraftRequest(mockSaveDraftPayload))
      expect(result.saveDraftState.isFetching).toBe(true)
      expect(result.saveDraftState.intent).toBe('save')
    })

    it('stores draft on saveDraftSuccess and sets wizardRunId', () => {
      const result = validationReducer(initialState, validationActions.saveDraftSuccess(mockHistoryDetail))
      expect(result.wizardRunId).toBe('run-draft-1')
      expect(result.saveDraftState.data).toEqual(mockHistoryDetail)
      expect(result.saveDraftState.isFetching).toBe(false)
    })

    it('stores error on saveDraftError', () => {
      const loading = validationReducer(initialState, validationActions.saveDraftRequest(mockSaveDraftPayload))
      const result = validationReducer(loading, validationActions.saveDraftError('Save failed'))
      expect(result.saveDraftState.error).toBe('Save failed')
      expect(result.saveDraftState.isFetching).toBe(false)
    })
  })

  describe('history navigation', () => {
    it('stores pending history navigation', () => {
      const result = validationReducer(
        initialState,
        validationActions.navigateToPairHistory({
          sourcePath: 'gs://test-bucket/data/source.csv',
          targetPath: 'gs://test-bucket/data/target.csv',
        }),
      )
      expect(result.pendingHistoryNavigation).toEqual({
        sourcePath: 'gs://test-bucket/data/source.csv',
        targetPath: 'gs://test-bucket/data/target.csv',
      })
    })

    it('clears pending history navigation', () => {
      const withPending = {
        ...initialState,
        pendingHistoryNavigation: {
          sourcePath: 'gs://test-bucket/data/source.csv',
          targetPath: 'gs://test-bucket/data/target.csv',
        },
      }
      expect(validationReducer(withPending, validationActions.clearPendingHistoryNavigation()).pendingHistoryNavigation).toBeNull()
    })
  })
})

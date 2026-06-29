import { call, put } from 'redux-saga/effects'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterEach, vi } from 'vitest'

import {
  mockBrowseResponse,
  mockCloudConnection,
  mockHistoryDetail,
  mockSaveDraftPayload,
  mockSourceCloud,
  mockTargetCloud,
  validationStateStep1Ready,
} from '../Validation.mockData'
import { validationActions } from '../Validation.reducer'
import validationSaga, {
  browseCloudSaga,
  listCloudConnectionsSaga,
  previewValidationColumnsSaga,
  saveDraftSaga,
} from '../Validation.saga'
import { ValidationServiceApi } from '../Validation.service'

vi.mock('../Validation.service', () => ({
  ValidationServiceApi: {
    listCloudConnections: vi.fn(),
    browseCloud: vi.fn(),
    previewValidationColumns: vi.fn(),
    saveValidationDraft: vi.fn(),
  },
}))

vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const createAxiosResponse = <T,>(data: T) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: { headers: new AxiosHeaders() },
})

describe('Validation sagas', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('listCloudConnectionsSaga', () => {
    it('dispatches success when connections are loaded', () => {
      const iterator = listCloudConnectionsSaga()
      expect(iterator.next().value).toEqual(call(ValidationServiceApi.listCloudConnections))
      expect(iterator.next(createAxiosResponse([mockCloudConnection])).value).toEqual(
        put(validationActions.listCloudConnectionsSuccess([mockCloudConnection])),
      )
    })

    it('dispatches error when fetch fails', () => {
      const iterator = listCloudConnectionsSaga()
      iterator.next()
      const error = new Error('Network error')
      expect(iterator.throw(error).value).toEqual(
        put(validationActions.listCloudConnectionsError('Network error')),
      )
    })
  })

  describe('browseCloudSaga', () => {
    it('dispatches success when browse completes', () => {
      const action = {
        type: validationActions.browseCloudRequest.type,
        payload: {
          pathId: 'conn-1:test-bucket:',
          connectionId: 'conn-1',
          bucket: 'test-bucket',
          prefix: '',
        },
      }
      const iterator = browseCloudSaga(action)
      expect(iterator.next().value).toEqual(
        call(ValidationServiceApi.browseCloud, {
          connection_id: 'conn-1',
          bucket: 'test-bucket',
          prefix: '',
          file_format: 'auto',
        }),
      )
      expect(iterator.next(createAxiosResponse(mockBrowseResponse)).value).toEqual(
        put(
          validationActions.browseCloudSuccess({
            pathId: 'conn-1:test-bucket:',
            connectionId: 'conn-1',
            data: mockBrowseResponse,
          }),
        ),
      )
    })

    it('dispatches error when browse fails', () => {
      const action = {
        type: validationActions.browseCloudRequest.type,
        payload: {
          pathId: 'conn-1:test-bucket:',
          connectionId: 'conn-1',
          bucket: 'test-bucket',
          prefix: '',
        },
      }
      const iterator = browseCloudSaga(action)
      iterator.next()
      const error = new Error('Browse failed')
      expect(iterator.throw(error).value).toEqual(
        put(
          validationActions.browseCloudError({
            pathId: 'conn-1:test-bucket:',
            error: 'Browse failed',
          }),
        ),
      )
    })
  })

  describe('previewValidationColumnsSaga', () => {
    it('dispatches success when preview columns are loaded', () => {
      const previewData = {
        source_columns: ['id'],
        target_columns: ['id'],
        compare_columns: ['id'],
        auto_mappings: [{ source_column: 'id', target_column: 'id' }],
        unmatched_source_columns: [],
        unmatched_target_columns: [],
        delimiter: ',',
        source_samples: { id: ['1'] },
        target_samples: { id: ['1'] },
      }
      const iterator = previewValidationColumnsSaga({ type: 'test', payload: 'pair-key' }) as Generator<
        unknown,
        void,
        unknown
      >
      iterator.next()
      expect(iterator.next(validationStateStep1Ready).value).toEqual(
        call(ValidationServiceApi.previewValidationColumns, {
          source_cloud: mockSourceCloud,
          target_cloud: mockTargetCloud,
          uid_column: 'id',
          delimiter: 'auto',
          has_header: true,
        }),
      )
      expect(iterator.next(createAxiosResponse(previewData)).value).toEqual(
        put(validationActions.previewValidationColumnsSuccess({ pairKey: 'pair-key', data: previewData })),
      )
    })
  })

  describe('saveDraftSaga', () => {
    it('dispatches success when draft is saved', () => {
      const action = { type: validationActions.saveDraftRequest.type, payload: mockSaveDraftPayload }
      const iterator = saveDraftSaga(action)
      expect(iterator.next().value).toEqual(
        call(ValidationServiceApi.saveValidationDraft, mockSaveDraftPayload.draft),
      )
      expect(iterator.next(createAxiosResponse(mockHistoryDetail)).value).toEqual(
        put(validationActions.saveDraftSuccess(mockHistoryDetail)),
      )
    })

    it('dispatches error when save fails with AxiosError', () => {
      const action = { type: validationActions.saveDraftRequest.type, payload: mockSaveDraftPayload }
      const iterator = saveDraftSaga(action)
      iterator.next()
      const axiosError = new AxiosError(
        'Save failed',
        'ERR_BAD_REQUEST',
        undefined,
        undefined,
        {
          status: 500,
          statusText: 'Internal Server Error',
          headers: {},
          config: { headers: new AxiosHeaders() },
          data: { message: 'Save failed' },
        },
      )
      expect(iterator.throw(axiosError).value).toEqual(put(validationActions.saveDraftError('Save failed')))
    })
  })

  describe('validationSaga root watcher', () => {
    it('registers takeLatest watchers for validation actions', () => {
      const iterator = validationSaga()
      const first = iterator.next().value as { type: string; payload: unknown[] }
      expect(first.type).toBe('ALL')
      expect(first.payload).toHaveLength(8)
      expect(iterator.next().done).toBe(true)
    })
  })
})

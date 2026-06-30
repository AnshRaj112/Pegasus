import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { notification } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { loadValidationRunForm } from './validationRerun';
import {
  VALIDATIONS_BASE,
  parseValidationRoute,
  validationMappingPath,
  validationOverviewPath,
} from './validationRoutes';
import {
  loadValidationTabSession,
  saveValidationTabSession,
} from './validationTabStorage';
import { assessEmptyValidationFiles } from './validationEmptyFiles';
import { cloudObjectKey, resolveOverviewPreviewStatus } from './overviewPreview';
import { resolveMappingStepReady } from './mappingStepReady';
import { dispatchOverviewProfileFetch } from './overviewPrefetch';

import { FileSelectionStep } from './steps/FileSelectionStep';
import { MappingOverviewStep } from './steps/MappingOverviewStep';
import { ConfigureMappingStep } from './steps/ConfigureMappingStep';
import { resolveWizardArchiveMode, archiveUsesTabularValidation } from './archiveFormat';
import { isFixedWidthFormat } from './fixedWidthFormat';
import { resolveWizardJsonMode } from './jsonFormat';

import styles from './Validation.module.scss';

const ValidationWizardView: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { step: currentStep, runId } = parseValidationRoute(location.pathname);

  const isStep1Valid = useAppSelector((state) => state.validation.isStep1Valid);
  const { isFetching } = useAppSelector((state) => state.validation.validationDataState);
  const validationForm = useAppSelector((state) => state.validation.validationForm);
  const overviewCache = useAppSelector((state) => state.validation.overviewProfileCache);
  const overviewProfileFetchState = useAppSelector((state) => state.validation.overviewProfileFetchState);
  const wizardRunId = useAppSelector((state) => state.validation.wizardRunId);
  const saveDraftState = useAppSelector((state) => state.validation.saveDraftState);
  const previewColumnsState = useAppSelector((state) => state.validation.previewColumnsState);
  const previewFixedWidthState = useAppSelector((state) => state.validation.previewFixedWidthState);
  const overviewPreviewShown = useAppSelector((state) => state.validation.overviewPreviewShown);
  const overviewPreviewSessionKey = useAppSelector((state) => state.validation.overviewPreviewSessionKey);

  const [savingDraft, setSavingDraft] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const loadedRunIdRef = useRef<string | null>(null);
  const sessionSaveReadyRef = useRef(false);

  useLayoutEffect(() => {
    const saved = loadValidationTabSession();
    if (saved?.wizardRunId) {
      loadedRunIdRef.current = saved.wizardRunId;
    }
    sessionSaveReadyRef.current = true;
  }, []);

  useEffect(() => {
    if (!sessionSaveReadyRef.current) return;
    saveValidationTabSession({
      validationForm,
      isStep1Valid,
      wizardRunId,
      overviewProfileCache: overviewCache,
    });
  }, [validationForm, isStep1Valid, wizardRunId, overviewCache]);

  useEffect(() => {
    dispatch(validationActions.setWizardStep(currentStep));
  }, [currentStep, dispatch]);

  useEffect(() => {
    if (!runId) {
      if (!validationForm.sourceCloud && !validationForm.targetCloud) {
        loadedRunIdRef.current = null;
        dispatch(validationActions.setWizardRunId(null));
      }
      return;
    }

    if (loadedRunIdRef.current === runId) return;

    let cancelled = false;
    setLoadingRun(true);

    loadValidationRunForm(runId)
      .then((formPatch) => {
        if (cancelled) return;
        loadedRunIdRef.current = runId;
        dispatch(validationActions.setValidationForm(formPatch));
        dispatch(validationActions.setStep1Valid(Boolean(formPatch.sourceCloud && formPatch.targetCloud)));
        dispatch(validationActions.setWizardRunId(runId));
      })
      .catch((error) => {
        if (cancelled) return;
        notification.error({
          message: 'Could not open validation run',
          description: error instanceof Error ? error.message : 'Unknown run or load failed',
        });
        navigate(VALIDATIONS_BASE, { replace: true });
      })
      .finally(() => {
        if (!cancelled) setLoadingRun(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId, dispatch, navigate]);

  const buildDraftPayload = () => ({
    source_path: `gs://${validationForm.sourceCloud!.bucket}/${validationForm.sourceCloud!.object_name}`,
    target_path: `gs://${validationForm.targetCloud!.bucket}/${validationForm.targetCloud!.object_name}`,
    uid_column: validationForm.uidColumn,
    delimiter: validationForm.delimiter || 'auto',
    column_mappings: validationForm.columnMappings,
  });

  useEffect(() => {
    if (!saveDraftState.data || saveDraftState.isFetching) return;

    loadedRunIdRef.current = saveDraftState.data.run_id;

    if (saveDraftState.intent === 'proceed') {
      dispatchOverviewProfileFetch(
        dispatch,
        validationForm,
        overviewCache,
        overviewProfileFetchState,
      );
      navigate(validationOverviewPath(saveDraftState.data.run_id));
      setAdvancing(false);
    } else if (saveDraftState.intent === 'save') {
      if (currentStep === 2) {
        navigate(validationOverviewPath(saveDraftState.data.run_id), { replace: true });
      } else if (currentStep === 3) {
        navigate(validationMappingPath(saveDraftState.data.run_id), { replace: true });
      }
      setSavingDraft(false);
    }

    dispatch(validationActions.clearSaveDraftState());
  }, [saveDraftState, currentStep, navigate, dispatch, validationForm, overviewCache, overviewProfileFetchState]);

  useEffect(() => {
    if (!saveDraftState.error || saveDraftState.isFetching) return;

    if (saveDraftState.intent === 'proceed') {
      setAdvancing(false);
    } else if (saveDraftState.intent === 'save') {
      setSavingDraft(false);
    }

    dispatch(validationActions.clearSaveDraftState());
  }, [saveDraftState.error, saveDraftState.intent, saveDraftState.isFetching, dispatch]);

  const isStep2Loading = currentStep === 2 && (
    loadingRun
    || (
      overviewProfileFetchState.isFetching
      && overviewProfileFetchState.sourceKey === cloudObjectKey(validationForm.sourceCloud)
      && overviewProfileFetchState.targetKey === cloudObjectKey(validationForm.targetCloud)
    )
    || overviewCache?.sourceKey !== cloudObjectKey(validationForm.sourceCloud)
    || overviewCache?.targetKey !== cloudObjectKey(validationForm.targetCloud)
  );

  const overviewIsFixedWidth = useMemo(() => {
    if (!overviewCache?.source && !overviewCache?.target) return isFixedWidthFormat(validationForm.detectedFileFormat);
    return isFixedWidthFormat(overviewCache?.source?.suggested_file_format ?? overviewCache?.source?.file_format)
      || isFixedWidthFormat(overviewCache?.target?.suggested_file_format ?? overviewCache?.target?.file_format);
  }, [overviewCache, validationForm.detectedFileFormat]);

  const overviewIsJson = useMemo(() => resolveWizardJsonMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  }), [
    overviewCache,
    validationForm.detectedFileFormat,
    validationForm.sourceFileName,
    validationForm.targetFileName,
  ]);

  const overviewBlocksMapping = useMemo(() => {
    if (currentStep !== 2 || isStep2Loading || loadingRun) return false;
    if (!validationForm.sourceCloud || !validationForm.targetCloud) return true;
    if (overviewIsFixedWidth && validationForm.fixedWidthColumns.length === 0) return true;
    const assessment = assessEmptyValidationFiles({
      sourceSizeBytes: validationForm.sourceFileSize,
      targetSizeBytes: validationForm.targetFileSize,
      sourceProfile: overviewCache?.source ?? null,
      targetProfile: overviewCache?.target ?? null,
      profilesLoading: false,
      sourceProfileError: overviewCache?.sourceError ?? false,
      targetProfileError: overviewCache?.targetError ?? false,
    });
    return assessment?.blocksMapping ?? false;
  }, [
    currentStep,
    isStep2Loading,
    loadingRun,
    validationForm.sourceCloud,
    validationForm.targetCloud,
    validationForm.sourceFileSize,
    validationForm.targetFileSize,
    overviewCache,
    overviewIsFixedWidth,
    validationForm.fixedWidthColumns.length,
  ]);

  const overviewPreviewStatus = useMemo(() => resolveOverviewPreviewStatus({
    form: validationForm,
    cache: overviewCache,
    previewColumnsState,
    previewFixedWidthState,
  }), [validationForm, overviewCache, previewColumnsState, previewFixedWidthState]);

  const overviewPreviewSatisfied = overviewPreviewStatus.ready
    && overviewPreviewShown
    && overviewPreviewSessionKey === overviewPreviewStatus.sessionKey;

  const overviewPreviewPending = currentStep === 2
    && !overviewBlocksMapping
    && overviewPreviewStatus.kind !== 'skipped'
    && !overviewPreviewStatus.error
    && (!overviewPreviewStatus.ready || !overviewPreviewSatisfied);

  const isFixedWidth = isFixedWidthFormat(validationForm.detectedFileFormat);
  const isJson = resolveWizardJsonMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });
  const isArchive = Boolean(resolveWizardArchiveMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  }));
  const isArchiveMetadataOnly = isArchive && !archiveUsesTabularValidation({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });
  const isStep3Loading = currentStep === 3 && loadingRun;

  const mappingStepStatus = useMemo(() => resolveMappingStepReady({
    form: validationForm,
    cache: overviewCache,
    previewColumnsState,
    previewFixedWidthState,
    isJson,
    isArchiveMetadataOnly,
    isFixedWidth,
  }), [
    validationForm,
    overviewCache,
    previewColumnsState,
    previewFixedWidthState,
    isJson,
    isArchiveMetadataOnly,
    isFixedWidth,
  ]);

  const isStep3DataLoading = currentStep === 3 && mappingStepStatus.loading;
  const isStep3DataBlocked = currentStep === 3 && !mappingStepStatus.loading && !mappingStepStatus.ready;

  const isActuallyLoading = isFetching || advancing || isStep2Loading || isStep3Loading || isStep3DataLoading
    || (currentStep === 2 && overviewPreviewStatus.loading);
  const isNextButtonDisabled = isActuallyLoading
    || isStep3DataBlocked
    || (currentStep === 1 && !isStep1Valid)
    || (currentStep === 2 && (overviewBlocksMapping || overviewPreviewPending));

  const handleProceed = () => {
    if (currentStep === 1) {
      if (!isStep1Valid || !validationForm.sourceCloud || !validationForm.targetCloud) return;
      setAdvancing(true);
      dispatch(validationActions.saveDraftRequest({
        draft: buildDraftPayload(),
        intent: 'proceed',
      }));
      return;
    }

    if (currentStep === 2) {
      if (!runId || overviewBlocksMapping) return;
      if (overviewIsJson) {
        dispatch(validationActions.setValidationForm({
          detectedFileFormat: 'json',
          delimiter: 'json',
        }));
      }
      const archiveKind = resolveWizardArchiveMode({
        detectedFileFormat: validationForm.detectedFileFormat,
        sourceFileName: validationForm.sourceFileName,
        targetFileName: validationForm.targetFileName,
        sourceProfile: overviewCache?.source,
        targetProfile: overviewCache?.target,
      });
      if (archiveKind) {
        const archiveTabular = archiveUsesTabularValidation({
          detectedFileFormat: validationForm.detectedFileFormat,
          sourceFileName: validationForm.sourceFileName,
          targetFileName: validationForm.targetFileName,
          sourceProfile: overviewCache?.source,
          targetProfile: overviewCache?.target,
        });
        dispatch(validationActions.setValidationForm({
          detectedFileFormat: archiveKind,
          ...(archiveTabular ? {} : { columnMappings: [] }),
        }));
      }
      navigate(validationMappingPath(runId));
      return;
    }

    if (currentStep === 3) {
      if (isFixedWidth && validationForm.fixedWidthColumns.length === 0) {
        notification.warning({
          message: 'Fixed-width layout required',
          description: 'Configure the fixed-width column layout before running validation.',
        });
        return;
      }
      if (!isJson && !isArchiveMetadataOnly && !isFixedWidth) {
        const hasMappings = (validationForm.columnMappings?.length ?? 0) > 0;
        if (!hasMappings) {
          notification.warning({
            message: 'Column mapping required',
            description: 'Map at least one source column to a target column before running validation.',
          });
          return;
        }
      }
    }

    dispatch(validationActions.submitValidationRequest());
  };

  const handleBack = () => {
    if (currentStep === 2) {
      navigate(VALIDATIONS_BASE);
      return;
    }
    if (currentStep === 3 && runId) {
      navigate(validationOverviewPath(runId));
    }
  };

  const canSaveDraft = Boolean(
    validationForm.sourceCloud?.object_name && validationForm.targetCloud?.object_name,
  );

  const handleSaveDraft = () => {
    if (!canSaveDraft || !validationForm.sourceCloud || !validationForm.targetCloud) return;
    setSavingDraft(true);
    dispatch(validationActions.saveDraftRequest({
      draft: buildDraftPayload(),
      intent: 'save',
    }));
  };

  const renderStepContent = () => {
    if (loadingRun && runId) {
      return <div className={styles.loadingRun}>Loading validation run…</div>;
    }

    switch (currentStep) {
      case 1: return <FileSelectionStep />;
      case 2: return <MappingOverviewStep />;
      case 3: return <ConfigureMappingStep />;
      default: return <FileSelectionStep />;
    }
  };

  const proceedLabel = currentStep === 3
    ? isStep3DataLoading
      ? 'Loading mapping data…'
      : isStep3DataBlocked
        ? 'Mapping data unavailable'
      : 'Run Validation'
    : currentStep === 2
      ? overviewBlocksMapping
        ? 'Cannot proceed — empty file'
        : overviewPreviewStatus.error
          ? 'Preview failed — fix files or retry'
        : overviewPreviewPending && overviewPreviewStatus.loading
          ? 'Loading preview…'
          : overviewPreviewPending && overviewPreviewStatus.ready && !overviewPreviewSatisfied
            ? 'Review preview to continue'
          : overviewIsJson
            ? 'Proceed to JSON Mapping'
            : 'Proceed to Mapping'
      : 'Proceed to Overview';

  return (
    <div className={styles.wizardPage}>
      <header className={styles.wizardHeaderShell}>
        <div className={styles.wizardHeaderLogoGroup}>
          <h2 className={styles.wizardTitle}>File-to-File Validation Tool</h2>
        </div>
      </header>

      <div className={styles.wizardStepTabBanner}>
        <div className={styles.wizardStepRow}>
          <div className={`${styles.stepTabItem} ${styles.stepTabStatic} ${currentStep === 1 ? styles.stepTabActive : styles.stepTabInactive}`}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 1 ? styles.stepNumberActive : styles.stepNumberInactive}`}>1</span>
            <span className={styles.stepTabLabel}>File Selection</span>
          </div>
          <div className={`${styles.stepTabItem} ${styles.stepTabStatic} ${currentStep === 2 ? styles.stepTabActive : styles.stepTabInactive}`}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 2 ? styles.stepNumberActive : styles.stepNumberInactive}`}>2</span>
            <span className={styles.stepTabLabel}>File Overview</span>
          </div>
          <div className={`${styles.stepTabItem} ${styles.stepTabStatic} ${currentStep === 3 ? styles.stepTabActive : styles.stepTabInactive}`}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 3 ? styles.stepNumberActive : styles.stepNumberInactive}`}>3</span>
            <span className={styles.stepTabLabel}>
              {overviewIsJson || isJson ? 'JSON Mapping' : isArchiveMetadataOnly ? 'Archive Validation' : 'File Mapping'}
            </span>
          </div>
        </div>
      </div>

      <main className={styles.wizardWorkspaceArea}>
        {renderStepContent()}
      </main>

      <footer className={`${styles.wizardActionFooter} ${styles.wizardActionFooterSpread}`}>
        <div>
          {currentStep > 1 && (
            <button
              type="button"
              onClick={handleBack}
              disabled={isActuallyLoading}
              className={`${styles.secondaryBtn} ${isActuallyLoading ? styles.secondaryBtnDisabled : ''}`}
            >
              Back
            </button>
          )}
        </div>
        <div className={styles.footerBtnGroup}>
          <button
            type="button"
            disabled={!canSaveDraft || savingDraft}
            onClick={() => void handleSaveDraft()}
            title="Save mapping configuration without running validation"
            className={`${styles.secondaryBtn} ${!canSaveDraft || savingDraft ? styles.secondaryBtnMuted : ''}`}
          >
            {savingDraft ? 'Saving…' : 'Save Draft'}
          </button>
          <button
            type="button"
            onClick={() => void handleProceed()}
            disabled={isNextButtonDisabled}
            className={isNextButtonDisabled ? `${styles.primaryBtn} ${styles.primaryBtnDisabled}` : styles.primaryBtn}
          >
            {isActuallyLoading ? 'Processing...' : proceedLabel}
            {!isActuallyLoading && <ArrowRightOutlined className={styles.proceedIcon} />}
          </button>
        </div>
      </footer>
    </div>
  );
};

export default ValidationWizardView;

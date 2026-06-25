import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { notification } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { reportActions } from '../report/Report.reducer';
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

import { FileSelectionStep } from './steps/FileSelectionStep';
import { MappingOverviewStep } from './steps/MappingOverviewStep';
import { ConfigureMappingStep } from './steps/ConfigureMappingStep';
import { Api } from '../../shared/api/Api';
import { isFixedWidthFormat } from './fixedWidthFormat';
import { resolveWizardJsonMode } from './jsonFormat';

import styles from './Validation.module.scss';

const cloudObjectKey = (cloud: any): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

export const ValidationWizardView: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { step: currentStep, runId } = parseValidationRoute(location.pathname);

  const isStep1Valid = useAppSelector((state) => state.validation.isStep1Valid);
  const { isFetching } = useAppSelector((state) => state.validation.validationDataState);
  const validationForm = useAppSelector((state) => state.validation.validationForm);
  const overviewCache = useAppSelector((state) => state.validation.overviewProfileCache);
  const wizardRunId = useAppSelector((state) => state.validation.wizardRunId);

  const [savingDraft, setSavingDraft] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const loadedRunIdRef = useRef<string | null>(null);
  const sessionSaveReadyRef = useRef(false);

  // Align loaded-run tracking with store bootstrap (see redux/store.ts).
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

  const isStep2Loading = currentStep === 2 && (
    loadingRun
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

  const isFixedWidth = isFixedWidthFormat(validationForm.detectedFileFormat);
  const isJson = resolveWizardJsonMode({
    detectedFileFormat: validationForm.detectedFileFormat,
    sourceFileName: validationForm.sourceFileName,
    targetFileName: validationForm.targetFileName,
    sourceProfile: overviewCache?.source,
    targetProfile: overviewCache?.target,
  });
  const isStep3Loading = currentStep === 3 && (
    loadingRun
    || (isFixedWidth
      ? validationForm.fixedWidthColumns.length === 0
      : isJson
        ? false
        : !validationForm.columnMappings || validationForm.columnMappings.length === 0)
  );

  const isActuallyLoading = isFetching || advancing || isStep2Loading || isStep3Loading;
  const isNextButtonDisabled = isActuallyLoading
    || (currentStep === 1 && !isStep1Valid)
    || (currentStep === 2 && overviewBlocksMapping);

  const handleProceed = async () => {
    if (currentStep === 1) {
      if (!isStep1Valid || !validationForm.sourceCloud || !validationForm.targetCloud) return;
      setAdvancing(true);
      try {
        const { data } = await Api.saveValidationDraft({
          source_path: `gs://${validationForm.sourceCloud.bucket}/${validationForm.sourceCloud.object_name}`,
          target_path: `gs://${validationForm.targetCloud.bucket}/${validationForm.targetCloud.object_name}`,
          uid_column: validationForm.uidColumn,
          delimiter: validationForm.delimiter || 'auto',
          column_mappings: validationForm.columnMappings,
        });
        loadedRunIdRef.current = data.run_id;
        dispatch(validationActions.setWizardRunId(data.run_id));
        navigate(validationOverviewPath(data.run_id));
      } catch (e) {
        notification.error({
          message: 'Could not start file overview',
          description: e instanceof Error ? e.message : 'Failed to create validation run',
        });
      } finally {
        setAdvancing(false);
      }
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
      navigate(validationMappingPath(runId));
      return;
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

  const handleSaveDraft = async () => {
    if (!canSaveDraft || !validationForm.sourceCloud || !validationForm.targetCloud) return;
    setSavingDraft(true);
    try {
      const { data } = await Api.saveValidationDraft({
        source_path: `gs://${validationForm.sourceCloud.bucket}/${validationForm.sourceCloud.object_name}`,
        target_path: `gs://${validationForm.targetCloud.bucket}/${validationForm.targetCloud.object_name}`,
        uid_column: validationForm.uidColumn,
        delimiter: validationForm.delimiter || 'auto',
        column_mappings: validationForm.columnMappings,
      });
      notification.success({
        message: 'Draft saved',
        description: 'Find it under Reports → Saved.',
      });
      loadedRunIdRef.current = data.run_id;
      dispatch(validationActions.setWizardRunId(data.run_id));
      if (currentStep === 2) {
        navigate(validationOverviewPath(data.run_id), { replace: true });
      } else if (currentStep === 3) {
        navigate(validationMappingPath(data.run_id), { replace: true });
      }
      dispatch(reportActions.fetchReportsRequest());
    } catch (e) {
      notification.error({
        message: 'Could not save draft',
        description: e instanceof Error ? e.message : 'Save failed',
      });
    } finally {
      setSavingDraft(false);
    }
  };

  const renderStepContent = () => {
    if (loadingRun && runId) {
      return (
        <div style={{ padding: '48px', textAlign: 'center', color: '#727786' }}>
          Loading validation run…
        </div>
      );
    }

    switch (currentStep) {
      case 1: return <FileSelectionStep />;
      case 2: return <MappingOverviewStep />;
      case 3: return <ConfigureMappingStep />;
      default: return <FileSelectionStep />;
    }
  };

  const proceedLabel = currentStep === 3
    ? 'Run Validation'
    : currentStep === 2
      ? overviewBlocksMapping
        ? 'Cannot proceed — empty file'
        : overviewIsJson
          ? 'Proceed to JSON Mapping'
          : 'Proceed to Mapping'
      : 'Proceed to Overview';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '24px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
      <header className={styles.wizardHeaderShell}>
        <div className={styles.wizardHeaderLogoGroup}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, letterSpacing: '-0.015em' }}>
            File-to-File Validation Tool
          </h2>
        </div>
      </header>

      <div className={styles.wizardStepTabBanner}>
        <div className={styles.wizardStepRow}>
          <div className={`${styles.stepTabItem} ${currentStep === 1 ? styles.stepTabActive : styles.stepTabInactive}`} style={{ cursor: 'default' }}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 1 ? styles.stepNumberActive : styles.stepNumberInactive}`}>1</span>
            <span style={{ fontSize: '14px', fontWeight: 600 }}>File Selection</span>
          </div>
          <div className={`${styles.stepTabItem} ${currentStep === 2 ? styles.stepTabActive : styles.stepTabInactive}`} style={{ cursor: 'default' }}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 2 ? styles.stepNumberActive : styles.stepNumberInactive}`}>2</span>
            <span style={{ fontSize: '14px', fontWeight: 600 }}>File Overview</span>
          </div>
          <div className={`${styles.stepTabItem} ${currentStep === 3 ? styles.stepTabActive : styles.stepTabInactive}`} style={{ cursor: 'default' }}>
            <span className={`${styles.stepNumberBadge} ${currentStep === 3 ? styles.stepNumberActive : styles.stepNumberInactive}`}>3</span>
            <span style={{ fontSize: '14px', fontWeight: 600 }}>
              {overviewIsJson || isJson ? 'JSON Mapping' : 'File Mapping'}
            </span>
          </div>
        </div>
      </div>

      <main className={styles.wizardWorkspaceArea}>
        {renderStepContent()}
      </main>

      <footer className={styles.wizardActionFooter} style={{ justifyContent: 'space-between' }}>
        <div>
          {currentStep > 1 && (
            <button
              onClick={handleBack}
              disabled={isActuallyLoading}
              style={{ padding: '0 24px', height: '40px', borderRadius: '8px', border: '1px solid #d9d9d9', background: '#ffffff', color: '#414755', fontSize: '14px', fontWeight: 600, cursor: isActuallyLoading ? 'not-allowed' : 'pointer', opacity: isActuallyLoading ? 0.6 : 1 }}
            >
              Back
            </button>
          )}
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <button
            type="button"
            disabled={!canSaveDraft || savingDraft}
            onClick={() => void handleSaveDraft()}
            title="Save mapping configuration without running validation"
            style={{ padding: '0 24px', height: '40px', borderRadius: '8px', border: '1px solid #d9d9d9', background: '#ffffff', color: '#414755', fontSize: '14px', fontWeight: 600, cursor: canSaveDraft && !savingDraft ? 'pointer' : 'not-allowed', opacity: canSaveDraft ? 1 : 0.6 }}
          >
            {savingDraft ? 'Saving…' : 'Save Draft'}
          </button>
          <button
            onClick={() => void handleProceed()}
            disabled={isNextButtonDisabled}
            style={{
              padding: '0 32px', height: '40px', borderRadius: '8px', border: 'none',
              background: isNextButtonDisabled ? '#e5e2e1' : '#234B5F',
              color: isNextButtonDisabled ? '#727786' : '#ffffff',
              fontSize: '14px', fontWeight: 700, cursor: isNextButtonDisabled ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s',
            }}
          >
            {isActuallyLoading ? 'Processing...' : proceedLabel}
            {!isActuallyLoading && <ArrowRightOutlined style={{ fontSize: '16px' }} />}
          </button>
        </div>
      </footer>
    </div>
  );
};

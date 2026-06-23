import React, { useEffect } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { notification } from 'antd';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { reportActions } from '../report/Report.reducer';
import { saveValidationWizardSession } from './validationWizardStorage';

import { FileSelectionStep } from './steps/FileSelectionStep';
import { MappingOverviewStep } from './steps/MappingOverviewStep';
import { ConfigureMappingStep } from './steps/ConfigureMappingStep';
import { Api } from '../../shared/api/Api';

import styles from './Validation.module.scss';

const cloudObjectKey = (cloud: any): string =>
  cloud ? `${cloud.connection_id ?? ''}:${cloud.bucket ?? ''}:${cloud.object_name}` : '';

export const ValidationWizardView: React.FC = () => {
  const dispatch = useAppDispatch();
  const currentStep = useAppSelector((state) => state.validation.currentStep);
  const isStep1Valid = useAppSelector((state) => state.validation.isStep1Valid);
  const { isFetching } = useAppSelector((state) => state.validation.validationDataState);
  const validationForm = useAppSelector((state) => state.validation.validationForm);
  const overviewCache = useAppSelector((state) => state.validation.overviewProfileCache);
  const [savingDraft, setSavingDraft] = React.useState(false);

  useEffect(() => {
    saveValidationWizardSession({
      currentStep,
      isStep1Valid,
      validationForm,
      overviewProfileCache: overviewCache,
    });
  }, [currentStep, isStep1Valid, validationForm, overviewCache]);

  const isStep2Loading = currentStep === 2 && (
    overviewCache?.sourceKey !== cloudObjectKey(validationForm.sourceCloud) ||
    overviewCache?.targetKey !== cloudObjectKey(validationForm.targetCloud)
  );

  const isStep3Loading = currentStep === 3 && (
    !validationForm.columnMappings || validationForm.columnMappings.length === 0
  );

  const isActuallyLoading = isFetching || isStep2Loading || isStep3Loading;
  const isNextButtonDisabled = isActuallyLoading || (currentStep === 1 && !isStep1Valid);

  const handleProceed = () => {
    if (currentStep === 1 && !isStep1Valid) return;
    if (currentStep < 3) {
      dispatch(validationActions.setWizardStep(currentStep + 1));
    } else {
      dispatch(validationActions.submitValidationRequest());
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      dispatch(validationActions.setWizardStep(currentStep - 1));
    }
  };

  const canSaveDraft = Boolean(
    validationForm.sourceCloud?.object_name && validationForm.targetCloud?.object_name,
  );

  const handleSaveDraft = async () => {
    if (!canSaveDraft || !validationForm.sourceCloud || !validationForm.targetCloud) return;
    setSavingDraft(true);
    try {
      await Api.saveValidationDraft({
        source_path: `gs://${validationForm.sourceCloud.bucket}/${validationForm.sourceCloud.object_name}`,
        target_path: `gs://${validationForm.targetCloud.bucket}/${validationForm.targetCloud.object_name}`,
        uid_column: validationForm.uidColumn,
        delimiter: validationForm.delimiter || 'auto',
        column_mappings: validationForm.columnMappings,
      });
      notification.success({ message: 'Draft saved', description: 'Find it under Reports → Saved.' });
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
    switch (currentStep) {
      case 1: return <FileSelectionStep />;
      case 2: return <MappingOverviewStep />;
      case 3: return <ConfigureMappingStep />;
      default: return <FileSelectionStep />;
    }
  };

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
            <span style={{ fontSize: '14px', fontWeight: 600 }}>File Mapping</span>
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
            onClick={handleProceed}
            disabled={isNextButtonDisabled}
            style={{
              padding: '0 32px', height: '40px', borderRadius: '8px', border: 'none',
              background: isNextButtonDisabled ? '#e5e2e1' : '#234B5F',
              color: isNextButtonDisabled ? '#727786' : '#ffffff',
              fontSize: '14px', fontWeight: 700, cursor: isNextButtonDisabled ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s',
            }}
          >
            {isActuallyLoading ? 'Processing...' : (currentStep === 3 ? 'Run Validation' : 'Proceed to Mapping')}
            {!isActuallyLoading && <ArrowRightOutlined style={{ fontSize: '16px' }} />}
          </button>
        </div>
      </footer>
    </div>
  );
};

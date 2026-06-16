import React, { useEffect, useRef, useState } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { notification } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { reportActions } from '../report/Report.reducer';

import { FileSelectionStep } from './steps/FileSelectionStep';
import { MappingOverviewStep } from './steps/MappingOverviewStep';
import { ConfigureMappingStep } from './steps/ConfigureMappingStep';
import { ReportService } from '../report/Report.service';
import { gcsUri } from '../report/reportPairId';
import { Api } from '../../shared/api/Api';

// ⚡ Import the newly created CSS module
import styles from './Validation.module.scss';

export const ValidationWizardView: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  
  const currentStep = useAppSelector((state) => state.validation.currentStep);
  const isStep1Valid = useAppSelector((state) => state.validation.isStep1Valid);
  const { isFetching, data } = useAppSelector((state) => state.validation.validationDataState);
  const validationForm = useAppSelector((state) => state.validation.validationForm);
  const pendingReportJobId = useAppSelector((state) => state.validation.pendingReportJobId);
  const wasFetchingRef = useRef(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // Opening the wizard tab after a finished run should start fresh, not reopen the report.
  useEffect(() => {
    if (data?.status === 'Complete' || data?.status === 'Failed') {
      dispatch(validationActions.clearValidationRun());
    }
    // Only when the wizard view is mounted (user navigated to /validations).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pendingReportJobId) {
      navigate(`/validation/report/${pendingReportJobId}`);
      dispatch(validationActions.clearPendingReportJob());
    }
  }, [pendingReportJobId, navigate, dispatch]);

  // Redirect to reports history for this file pair after a fast run finishes in-wizard.
  useEffect(() => {
    if (
      wasFetchingRef.current
      && !isFetching
      && data?.status === 'Complete'
      && validationForm.sourceCloud
      && validationForm.targetCloud
    ) {
      const src = gcsUri(validationForm.sourceCloud);
      const tgt = gcsUri(validationForm.targetCloud);
      void ReportService.getMappingIdForPaths(src, tgt).then((mappingId) => {
        navigate(`/reports/${mappingId}/history`);
      });
    }
    wasFetchingRef.current = isFetching;
  }, [isFetching, data, navigate, validationForm.sourceCloud, validationForm.targetCloud]);

  const isNextButtonDisabled = isFetching || (currentStep === 1 && !isStep1Valid);

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
        source_path: gcsUri(validationForm.sourceCloud),
        target_path: gcsUri(validationForm.targetCloud),
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
      
      {/* ⚡ Swapped to styles.wizardHeaderShell */}
      <header className={styles.wizardHeaderShell}>
        <div className={styles.wizardHeaderLogoGroup}>
          <div style={{ width: '24px', height: '24px', color: 'var(--primary, #1677ff)' }}>
            <svg fill="none" viewBox="0 0 48 48" xmlns="http://w3.org">
              <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z" fill="currentColor" />
            </svg>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, letterSpacing: '-0.015em' }}>
            File-to-File Validation Tool
          </h2>
        </div>
      </header>

      {/* ⚡ Swapped tab banner classes to use dynamic module styles */}
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

      {/* ⚡ Swapped to styles.wizardWorkspaceArea */}
      <main className={styles.wizardWorkspaceArea}>
        {renderStepContent()}
      </main>

      {/* ⚡ Swapped to styles.wizardActionFooter */}
      <footer className={styles.wizardActionFooter} style={{ justifyContent: 'space-between' }}>
        <div>
          {currentStep > 1 && (
            <button 
              onClick={handleBack}
              disabled={isFetching}
              style={{ padding: '0 24px', height: '40px', borderRadius: '8px', border: '1px solid #d9d9d9', background: '#ffffff', color: '#414755', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
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
              background: isNextButtonDisabled ? '#e5e2e1' : '#1677ff', 
              color: isNextButtonDisabled ? '#727786' : '#ffffff', 
              fontSize: '14px', fontWeight: 700, cursor: isNextButtonDisabled ? 'not-allowed' : 'pointer', 
              display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s'
            }}
          >
            {isFetching ? 'Processing...' : (currentStep === 3 ? 'Run Validation' : 'Proceed to Mapping')}
            {!isFetching && <ArrowRightOutlined style={{ fontSize: '16px' }} />}
          </button>
        </div>
      </footer>
    </div>
  );
};

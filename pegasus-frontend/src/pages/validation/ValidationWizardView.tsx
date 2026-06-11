import React, { useEffect } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { validationActions } from './Validation.reducer';
import { FileSelectionStep } from './steps/FileSelectionStep';
import { MappingOverviewStep } from './steps/MappingOverviewStep';
import { ConfigureMappingStep } from './steps/ConfigureMappingStep';

export const ValidationWizardView: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  
  const currentStep = useAppSelector((state) => state.validation.currentStep);
  const isStep1Valid = useAppSelector((state) => state.validation.isStep1Valid);
  const { isFetching, data } = useAppSelector((state) => state.validation.validationDataState);
  const validationForm = useAppSelector((state) => state.validation.validationForm);

  useEffect(() => {
    if (data?.status === 'Complete' && data.jobId) {
      navigate(`/validation/report/${data.jobId}`);
    }
  }, [data, navigate]);

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

  const renderStepContent = () => {
    switch (currentStep) {
      case 1: return <FileSelectionStep />;
      case 2: return <MappingOverviewStep />;
      case 3: return <ConfigureMappingStep />;
      default: return <FileSelectionStep />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <header className="wizardHeaderShell">
        <div className="wizardHeaderLogoGroup">
          <div style={{ width: '24px', height: '24px', color: 'var(--primary)' }}>
            <svg fill="none" viewBox="0 0 48 48" xmlns="http://w3.org">
              <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z" fill="currentColor" />
            </svg>
          </div>
          <h2 style={{ fontSize: 'var(--h3)', fontWeight: 700, margin: 0, letterSpacing: '-0.015em' }}>
            File-to-File Validation Tool
          </h2>
        </div>
      </header>

      {/* ⚡ UPDATED TAB NAMES */}
      <div className="wizardStepTabBanner">
        <div className="wizardStepRow">
          <div className={`stepTabItem ${currentStep === 1 ? 'stepTabActive' : 'stepTabInactive'}`} style={{ cursor: 'default' }}>
            <span className={`stepNumberBadge ${currentStep === 1 ? 'stepNumberActive' : 'stepNumberInactive'}`}>1</span>
            <span style={{ fontSize: 'var(--label-md)', fontWeight: 600 }}>File Selection</span>
          </div>
          <div className={`stepTabItem ${currentStep === 2 ? 'stepTabActive' : 'stepTabInactive'}`} style={{ cursor: 'default' }}>
            <span className={`stepNumberBadge ${currentStep === 2 ? 'stepNumberActive' : 'stepNumberInactive'}`}>2</span>
            <span style={{ fontSize: 'var(--label-md)', fontWeight: 600 }}>File Overview</span>
          </div>
          <div className={`stepTabItem ${currentStep === 3 ? 'stepTabActive' : 'stepTabInactive'}`} style={{ cursor: 'default' }}>
            <span className={`stepNumberBadge ${currentStep === 3 ? 'stepNumberActive' : 'stepNumberInactive'}`}>3</span>
            <span style={{ fontSize: 'var(--label-md)', fontWeight: 600 }}>File Mapping</span>
          </div>
        </div>
      </div>

      <main className="wizardWorkspaceArea">
        {renderStepContent()}
      </main>

      <footer className="wizardActionFooter" style={{ justifyContent: 'space-between' }}>
        <div>
          {currentStep > 1 && (
            <button 
              onClick={handleBack}
              disabled={isFetching}
              style={{ padding: '0 var(--lg)', height: '40px', borderRadius: '8px', border: '1px solid var(--outline-variant)', background: 'var(--surface-container-lowest)', color: 'var(--on-surface-variant)', fontSize: 'var(--body-md)', fontWeight: 600, cursor: 'pointer' }}
            >
              Back
            </button>
          )}
        </div>
        
        <div style={{ display: 'flex', gap: 'var(--md)' }}>
          <button
            type="button"
            disabled={!canSaveDraft}
            title="Draft save requires local paths; use GCS selection and Run Validation"
            style={{ padding: '0 var(--lg)', height: '40px', borderRadius: '8px', border: '1px solid var(--outline-variant)', background: 'var(--surface-container-lowest)', color: 'var(--on-surface-variant)', fontSize: 'var(--body-md)', fontWeight: 600, cursor: 'not-allowed', opacity: 0.6 }}
          >
            Save Draft
          </button>
          <button 
            onClick={handleProceed}
            disabled={isNextButtonDisabled}
            style={{ 
              padding: '0 var(--xl)', height: '40px', borderRadius: '8px', border: 'none', 
              background: isNextButtonDisabled ? 'var(--surface-variant)' : 'var(--primary)', 
              color: isNextButtonDisabled ? 'var(--on-surface-variant)' : 'var(--on-primary)', 
              fontSize: 'var(--body-md)', fontWeight: 700, cursor: isNextButtonDisabled ? 'not-allowed' : 'pointer', 
              display: 'flex', alignItems: 'center', gap: 'var(--base)', transition: 'all 0.2s'
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
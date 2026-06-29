import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Checkbox, Col, Divider, Flex, InputNumber, Row, Select, Spin, Typography } from 'antd'
import { CheckboxChangeEvent } from 'antd/es/checkbox'
import { InfoCircleFilled } from '@ant-design/icons'

import { useAppDispatch, useAppSelector } from '~/redux/store'

import { ValidationSettings } from './Setting.interface'
import { settingActions } from './Setting.reducer'
import styles from './Setting.module.scss'

const { Title, Paragraph, Text } = Typography

const DEFAULT_SETTINGS: ValidationSettings = {
	cores: 8,
	autoTuning: true,
	samplesPerColumnError: 10,
}

const SAMPLES_OPTIONS = [
	{ value: 10, label: '10' },
	{ value: 20, label: '20' },
	{ value: 50, label: '50' },
]

const Setting = () => {
	const dispatch = useAppDispatch()
	const { data: settingsData, isFetching: isFetchingSettings } = useAppSelector(
		(state) => state.setting.fetchSettingsState
	)
	const { isFetching: isSaving } = useAppSelector((state) => state.setting.saveSettingsState)

	const [formData, setFormData] = useState<ValidationSettings>(DEFAULT_SETTINGS)

	useEffect(() => {
		dispatch(settingActions.fetchSettingsRequest())
	}, [dispatch])

	useEffect(() => {
		if (settingsData) {
			setFormData(settingsData)
		}
	}, [settingsData])

	const handleCoresChange = useCallback((value: number | null) => {
		setFormData((prev) => ({
			...prev,
			cores: value || 1,
		}))
	}, [])

	const handleAutoTuneChange = useCallback((e: CheckboxChangeEvent) => {
		setFormData((prev) => ({
			...prev,
			autoTuning: e.target.checked,
		}))
	}, [])

	const handleSamplesChange = useCallback((value: number) => {
		setFormData((prev) => ({
			...prev,
			samplesPerColumnError: value,
		}))
	}, [])

	const handleResetDefault = useCallback(() => {
		setFormData(DEFAULT_SETTINGS)
	}, [])

	const handleSaveConfiguration = useCallback(() => {
		dispatch(settingActions.saveSettingsRequest(formData))
	}, [formData, dispatch])

	const renderAsideInformation = () => (
		<aside className={styles.infoAside} data-testid="section-engine-info">
			<div className={styles.engineInfoCard}>
				<Flex align="center" gap="small" className="mb-2">
					<InfoCircleFilled className={styles.infoTitle} />
					<Text className={`fw-bold text-uppercase ${styles.infoTitle}`}>Engine Information</Text>
				</Flex>
				<Paragraph className="m-0">
					Optimizing these settings can reduce validation time by up to 40% for datasets exceeding 10GB.
				</Paragraph>
			</div>

			<div className={styles.envCard}>
				<Title level={4} className="mb-4 mt-0 font-value-sm">
					Current Environment
				</Title>
				<ul className={styles.envList}>
					<li>
						<span>Node Cluster:</span>
						<span className={styles.envValue}>us-east-4-main</span>
					</li>
					<li>
						<span>Memory Limit:</span>
						<span className={styles.envValueDark}>128 GB RAM</span>
					</li>
					<li>
						<span>Storage Engine:</span>
						<span className={styles.envValueDark}>S3-Optimized</span>
					</li>
				</ul>
			</div>
		</aside>
	)

	return (
		<div className={styles.mainWrapper}>
			<main className={styles.mainContainer}>
				<div className={styles.headerSection}>
					<Title level={2} className="m-0 font-headline-md">
						Pegasus Settings
					</Title>
					<Paragraph className="mt-1 font-body-sm">
						Configure the engine parameters for high-performance validation workflows.
					</Paragraph>
				</div>

				<Spin spinning={isFetchingSettings} data-testid="spinner-settings-loading">
					<Row gutter={[24, 24]}>
						<Col xs={24} lg={16}>
							<Card className={styles.settingsCard} bordered={false}>
								<Flex vertical gap="large">
									{/* Core Allocation */}
									<div>
										<label htmlFor="input-cores" className={styles.formLabel}>
											Number of cores being used
										</label>
										<InputNumber
											id="input-cores"
											className={`w-100 ${styles.fieldMaxWidth}`}
											min={1}
											max={64}
											value={formData.cores}
											onChange={handleCoresChange}
											data-testid="input-cores"
										/>
										<Paragraph className={styles.helperText}>
											Recommended: 8 cores. Maximum supported by current instance: 32 cores.
										</Paragraph>
									</div>

									<Divider className={styles.divider} />

									{/* Auto-tuning */}
									<Flex align="flex-start" gap="small">
										<Checkbox
											id="checkbox-autotune"
											checked={formData.autoTuning}
											onChange={handleAutoTuneChange}
											data-testid="checkbox-autotune"
											className="mt-1"
										/>
										<div>
											<label htmlFor="checkbox-autotune" className={`cursor-pointer select-none ${styles.formLabel}`}>
												Auto-tuning
											</label>
											<Paragraph className={`m-0 ${styles.helperText}`}>
												Enable dynamic resource adjustment based on file size and complexity to optimize performance.
											</Paragraph>
										</div>
									</Flex>

									<Divider className={styles.divider} />

									{/* Samples Per Column */}
									<div>
										<label htmlFor="select-samples" className={styles.formLabel}>
											Samples for per column error
										</label>
										<Select
											id="select-samples"
											className={`w-100 ${styles.fieldMaxWidth}`}
											options={SAMPLES_OPTIONS}
											value={formData.samplesPerColumnError}
											onChange={handleSamplesChange}
											data-testid="select-samples"
										/>
										<Paragraph className={styles.helperText}>
											Define the depth of sampling when an inconsistency is detected in a specific column.
										</Paragraph>
									</div>

									{/* Action Buttons */}
									<Flex justify="flex-end" gap="small" className="pt-4">
										<Button
											className={styles.resetButton}
											disabled={isSaving}
											onClick={handleResetDefault}
											data-testid="button-reset"
										>
											Reset to Default
										</Button>
										<Button
											className={styles.actionButton}
											loading={isSaving}
											onClick={handleSaveConfiguration}
											data-testid="button-save"
										>
											Save Configuration
										</Button>
									</Flex>
								</Flex>
							</Card>
						</Col>

						<Col xs={24} lg={8}>
							{renderAsideInformation()}
						</Col>
					</Row>
				</Spin>
			</main>
		</div>
	)
}

export default Setting
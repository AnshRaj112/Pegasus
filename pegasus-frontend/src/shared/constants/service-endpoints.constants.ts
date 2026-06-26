/** @see shared/api/Api.ts for endpoint paths */
export const PELICAN_BASE_PATH = '/api/v1';

// Add this object to satisfy the architecture requirements
export const SERVICE_ENDPOINT = {
    FILE_VALIDATION_SETTINGS: '/validation/settings', // Replace with your actual backend path if different
    TESTS_ACTIVE: '/tests/active',
    TESTS_COMPLETED: '/tests/completed',
    TESTS_SAVED: '/tests/saved',
}

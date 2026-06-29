import React from 'react';

const InvalidAppPathPage: React.FC = () => (
  <div className="p-4 text-break">
    <h1 className="h4 mb-2">Invalid URL</h1>
    <p className="mb-0">
      This app only supports hash routes such as{' '}
      <code>{`${window.location.origin}/#/login`}</code>.
      {' '}Remove any path before the <code>#</code> and try again.
    </p>
  </div>
);

export default InvalidAppPathPage;

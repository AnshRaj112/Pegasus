import React, { useEffect, useState } from 'react';

import InvalidAppPathPage from '~/router/InvalidAppPathPage';
import { hasInvalidAppPathname } from '~/router/router.utils';

const HashPathGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [invalidPath, setInvalidPath] = useState(hasInvalidAppPathname);

  useEffect(() => {
    const check = () => setInvalidPath(hasInvalidAppPathname());
    window.addEventListener('popstate', check);
    window.addEventListener('hashchange', check);
    return () => {
      window.removeEventListener('popstate', check);
      window.removeEventListener('hashchange', check);
    };
  }, []);

  if (invalidPath) {
    return <InvalidAppPathPage />;
  }

  return <>{children}</>;
};

export default HashPathGuard;

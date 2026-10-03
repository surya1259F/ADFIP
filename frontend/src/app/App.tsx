import React, { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { Providers } from './providers';
import { router } from './routes';
import { useAuthStore } from '../stores/authStore';

const AppInit: React.FC = () => {
  const restore = useAuthStore((s) => s.restore);
  useEffect(() => { restore(); }, [restore]);
  return <RouterProvider router={router} />;
};

export const App: React.FC = () => (
  <Providers>
    <AppInit />
  </Providers>
);

export default App;

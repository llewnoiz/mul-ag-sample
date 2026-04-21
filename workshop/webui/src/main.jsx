import React from 'react';
import ReactDOM from 'react-dom/client';
import { Amplify } from 'aws-amplify';

import './styles/app.css';
import App from './components/app.jsx';
import { AmplifyConfig } from './components/amplify.js';
import { ThemeProvider } from './components/theme-context.jsx';

Amplify.configure(AmplifyConfig);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);

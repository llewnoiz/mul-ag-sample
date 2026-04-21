// imports
import React from 'react';

// utilities
import { detectEnvironment } from '../logic/utilities.js';

// detect environment
const environment = detectEnvironment(window.location.host);

// export contexts
export const CustomerContext = React.createContext(null);
export const EnvironmentContext = React.createContext(environment);
export const UserContext = React.createContext(null);

import { useContext, useState, useRef, useEffect } from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { Amplify } from 'aws-amplify';
import { fetchUserAttributes } from 'aws-amplify/auth';
import { withAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

import { Header } from './header.jsx';
import { Dashboard } from './dashboard.jsx';
import { Billing } from './billing.jsx';
import { Usage } from './usage.jsx';
import { Account } from './account.jsx';
import { apiGetCustomers, apiSetCustomer } from '../logic/apis.js';
import { CustomerContext, EnvironmentContext, UserContext } from './contexts.js';
import { AmplifyConfig } from './amplify.js';

Amplify.configure(AmplifyConfig);

const env = EnvironmentContext._currentValue;

export const App = () => {
  const isMounted = useRef(true);
  const environment = useContext(EnvironmentContext);
  const [customer, setCustomer] = useState(null);
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState((environment !== "local") ? "active" : "loading");

  if (environment === "local") { console.warn("Running in local environment, some APIs won't work!"); }

  const getCustomer = async () => {
    setStatus("loading");
    const attributes = await fetchUserAttributes();
    setUser(attributes);
    const result = await apiGetCustomers({ customer_username: attributes?.sub });
    if (result.length === 0 && isMounted.current) {
      await claimDummyCustomer(attributes?.sub, attributes?.email);
    } else if (result === false && isMounted.current) {
      setStatus("error");
    } else if (isMounted.current) {
      setCustomer(result[0]);
      setStatus("active");
    }
  };

  const claimDummyCustomer = async (customer_username, customer_email) => {
    const result = await apiSetCustomer({
      customer_username, customer_email,
      first_name: "Jane", last_name: "Smith"
    });
    if (result && result.length > 0) {
      setCustomer(result[0]);
      setStatus("active");
    } else {
      setStatus("error");
    }
  };

  useEffect(() => { return () => { isMounted.current = false; }; }, []);
  useEffect(() => { if (isMounted.current) getCustomer(); }, []); // eslint-disable-line

  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex items-center gap-3 text-muted-foreground">
          <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">Looking up customer information, please wait...</span>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex items-center gap-3 text-destructive">
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <span className="text-sm">A system error occurred, please refresh the browser page.</span>
        </div>
      </div>
    );
  }

  return (
    <EnvironmentContext.Provider value={environment}>
      <UserContext.Provider value={user}>
        <CustomerContext.Provider value={customer}>
          <div className="min-h-screen bg-secondary">
            <Header />
            <Router>
              <Routes>
                <Route path="/" exact element={<Dashboard />} />
                <Route path="/billing" exact element={<Billing />} />
                <Route path="/usage" exact element={<Usage />} />
                <Route path="/account" exact element={<Account />} />
              </Routes>
            </Router>
          </div>
        </CustomerContext.Provider>
      </UserContext.Provider>
    </EnvironmentContext.Provider>
  );
};

export default withAuthenticator(App);

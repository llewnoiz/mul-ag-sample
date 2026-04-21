import { useContext } from 'react';
import { CustomerContext } from './contexts.js';

const Field = ({ label, children }) => (
  <div>
    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
    <div className="text-sm text-foreground">{children}</div>
  </div>
);

export const Account = () => {
  const customer = useContext(CustomerContext);

  return (
    <div className="px-6 py-4 space-y-4">
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <a href="#/" className="hover:text-foreground transition-colors no-underline text-muted-foreground">Dashboard</a>
        <span>/</span>
        <span className="text-foreground">User Profile</span>
      </nav>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">User Profile</h1>

      {/* Customer Information */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-card-foreground mb-4">Customer information</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-4">
            <Field label="First name">{customer.first_name}</Field>
            <Field label="Last name">{customer.last_name}</Field>
          </div>
          <div className="space-y-4">
            <Field label="Billing Address">
              {customer.billing_address}<br />
              {customer.billing_city}, {customer.billing_state} {customer.billing_zipcode}
            </Field>
            <Field label="Phone">{customer.phone}</Field>
            <Field label="Email">{customer.customer_email}</Field>
          </div>
          <div className="space-y-4">
            <Field label="Customer ID">{customer.customer_uuid}</Field>
            <Field label="Username">{customer.customer_email}</Field>
            <Field label="Password">***********</Field>
          </div>
        </div>
      </div>

      {/* Billing Information */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-card-foreground mb-4">Billing information</h2>
        <Field label="Meter ID">{customer.device_id}</Field>
      </div>

      {/* Payment Information */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-card-foreground mb-4">Payment information</h2>
        <div className="space-y-4">
          <Field label="Autopay">
            <span className="inline-flex items-center gap-2">
              <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-500">✓ Enabled</span>
              <a href="#/account" className="text-blue-500 hover:underline underline-offset-4 text-sm">Manage Autopay</a>
            </span>
          </Field>
          <Field label="Payment method">My Visa Card ending in 1234</Field>
        </div>
      </div>
    </div>
  );
};

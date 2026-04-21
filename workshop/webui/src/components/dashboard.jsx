import { useState, useContext, useRef, useEffect } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { apiGetMetrics, apiGetBilling, apiGetInvoice } from '../logic/apis.js';
import { CustomerContext } from './contexts.js';

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export const Dashboard = () => {
  const isMounted = useRef(true);
  const customer = useContext(CustomerContext);
  const [status, setStatus] = useState("initial");
  const [usage, setUsage] = useState(null);
  const [showInvoice, setShowInvoice] = useState(false);
  const [invoice, setInvoice] = useState(null);

  const getCustomerState = async (customer) => {
    setStatus("loading");
    const result1 = await apiGetMetrics({ device_id: customer.device_id, name: "usage", order: "DESC" });
    const result2 = await apiGetMetrics({ device_id: customer.device_id, name: "sold", order: "DESC" });
    const result3 = await apiGetBilling({ customer_id: customer.customer_id });

    if ((result1 === false || result2 === false || result3 === false) && isMounted.current) {
      setStatus("error");
    } else if (isMounted.current) {
      const totalUsage = result1.reduce((a, b) => a + parseFloat(b.value), 0);
      const totalSold = result2.reduce((a, b) => a + parseFloat(b.value), 0);
      const usageByRate = result1.map((e) => ({ name: e.dimension, value: parseFloat(e.value) / 1000 }));
      const invoices = result3.map((e) => { e.invoice_amount = parseFloat(e.invoice_amount); return e; });
      setUsage({ totalConsumed: totalUsage / 1000, totalSold: totalSold / 1000, consumedByRate: usageByRate, latestBill: invoices[0] || null });
      setStatus("finished");
    }
  };

  useEffect(() => { return () => { isMounted.current = false; }; }, []);
  useEffect(() => { if (isMounted.current && customer) getCustomerState(customer); }, [customer]); // eslint-disable-line

  return (
    <div className="px-6 py-4 space-y-4">
      {/* Breadcrumb */}
      <nav className="text-sm text-muted-foreground">
        <a href="#/" className="hover:text-foreground transition-colors no-underline text-muted-foreground">Dashboard</a>
      </nav>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Account Overview</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Usage Card */}
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-card-foreground">Usage this month by rate plan</h2>
              <p className="text-sm text-muted-foreground">Energy consumption breakdown</p>
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="flex items-center justify-center">
                {status === "loading" ? (
                  <div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">Loading...</div>
                ) : usage && usage.consumedByRate.length > 0 ? (
                  <ResponsiveContainer width={180} height={180}>
                    <PieChart>
                      <Pie data={usage.consumedByRate} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" stroke="hsl(var(--card))">
                        {usage.consumedByRate.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '6px', color: 'hsl(var(--foreground))' }}
                        formatter={(value) => [`${value.toFixed(2)} kWh`, 'Usage']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[180px] flex items-center justify-center text-sm text-muted-foreground">No usage data</div>
                )}
              </div>
              <div className="flex flex-col justify-center space-y-6">
                <div>
                  <div className="text-4xl font-bold tracking-tight text-foreground">{usage ? usage.totalConsumed.toFixed(2) : '0'}</div>
                  <div className="text-sm text-muted-foreground mt-1">kWh consumed</div>
                </div>
                <div>
                  <div className="text-4xl font-bold tracking-tight text-foreground">{usage ? usage.totalSold.toFixed(2) : '0'}</div>
                  <div className="text-sm text-muted-foreground mt-1">kWh solar sold to grid</div>
                </div>
              </div>
            </div>
            {/* Legend */}
            {usage && usage.consumedByRate.length > 0 && (
              <div className="flex gap-4 mt-4 pt-4 border-t border-border flex-wrap">
                {usage.consumedByRate.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-foreground">
                    <span className="h-3 w-3 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                    {item.name} — {item.value.toFixed(1)} kWh
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Planning link */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-card-foreground mb-2">Planning to buy a new appliance?</h2>
            <a href="#/" className="text-blue-500 hover:underline underline-offset-4 text-sm">Estimate impact on your bill</a>
            <p className="text-xs text-muted-foreground mt-1">Estimate the impact your new investment will have on your electricity usage, and monthly bill.</p>
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Latest Bill Card */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-card-foreground mb-4">Your latest bill</h2>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <div className="text-4xl font-bold tracking-tight text-foreground">
                    ${usage?.latestBill ? usage.latestBill.invoice_amount.toFixed(2) : 'N/A'}
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">statement amount</div>
                </div>
                <div>
                  <div className="text-4xl font-bold tracking-tight text-foreground">
                    {usage?.latestBill ? usage.latestBill.due_date : 'N/A'}
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">due date</div>
                </div>
              </div>
              <div className="space-y-4">
                <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-500">
                  ✓ Autopay enabled
                </span>
                <p className="text-sm text-muted-foreground">
                  Your payment method will be charged on {usage?.latestBill ? usage.latestBill.due_date : 'N/A'}.{' '}
                  <a href="#/account" className="text-blue-500 hover:underline underline-offset-4">Manage Autopay</a>
                </p>
                <div className="flex gap-2 pt-2">
                  <button
                    disabled={!usage?.latestBill || status === "loading"}
                    onClick={async () => {
                      if (usage?.latestBill) {
                        const inv = await apiGetInvoice({ invoice_no: usage.latestBill.invoice_no });
                        if (inv) { setInvoice(inv); setShowInvoice(true); }
                      }
                    }}
                    className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-4 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                  >
                    View current bill
                  </button>
                  <button
                    onClick={() => window.location.href = '/#/billing'}
                    className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-4 border border-border bg-card hover:bg-secondary transition-colors text-foreground cursor-pointer"
                  >
                    Billing history
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Help link */}
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-lg font-semibold text-card-foreground mb-2">Need help paying your bill?</h2>
            <a href="#/" className="text-blue-500 hover:underline underline-offset-4 text-sm">Discover options and support programs</a>
            <p className="text-xs text-muted-foreground mt-1">The payment support portal offers a variety of payment options and programs you might qualify for to help keep the lights on.</p>
          </div>
        </div>
      </div>

      {/* Invoice Detail */}
      {showInvoice && invoice && (
        <div className="rounded-lg border border-border bg-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-card-foreground">Invoice Details</h2>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2 text-sm">
              <p><span className="text-muted-foreground">Invoice Number:</span> {invoice.invoice_no}</p>
              <p><span className="text-muted-foreground">Customer:</span> {invoice.full_name}</p>
              <p><span className="text-muted-foreground">Address:</span> {invoice.billing_address}, {invoice.billing_city}, {invoice.billing_state} {invoice.billing_zipcode}</p>
            </div>
            <div className="space-y-2 text-sm">
              <p><span className="text-muted-foreground">Bill Date:</span> {invoice.bill_date}</p>
              <p><span className="text-muted-foreground">Due Date:</span> {invoice.due_date}</p>
            </div>
          </div>
          <div className="text-sm space-y-1 pt-2 border-t border-border">
            <p><span className="text-muted-foreground">Invoice Amount:</span> {invoice.currency_symbol}{parseFloat(invoice.invoice_amount).toFixed(2)}</p>
            {parseFloat(invoice.discount_amount || 0) > 0 && <p><span className="text-muted-foreground">Discount:</span> -{invoice.currency_symbol}{parseFloat(invoice.discount_amount).toFixed(2)} ({invoice.discount_program})</p>}
            {parseFloat(invoice.penalty_amount || 0) > 0 && <p><span className="text-muted-foreground">Penalty:</span> +{invoice.currency_symbol}{parseFloat(invoice.penalty_amount).toFixed(2)} ({invoice.penalty_reason})</p>}
            <p className="font-medium"><span className="text-muted-foreground">Total Due:</span> {invoice.currency_symbol}{(parseFloat(invoice.invoice_amount) - parseFloat(invoice.discount_amount || 0) + parseFloat(invoice.penalty_amount || 0)).toFixed(2)}</p>
          </div>
          <button onClick={() => setShowInvoice(false)} className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-4 border border-border bg-card hover:bg-secondary transition-colors text-foreground cursor-pointer">
            Hide bill
          </button>
        </div>
      )}
    </div>
  );
};

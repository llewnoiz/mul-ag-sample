import { useState, useContext, useRef, useEffect } from 'react';
import { apiGetPayments, apiGetBilling, apiGetInvoice } from '../logic/apis.js';
import { CustomerContext } from './contexts.js';

export const Billing = () => {
  const isMounted = useRef(true);
  const customer = useContext(CustomerContext);
  const [status, setStatus] = useState("initial");
  const [billing, setBilling] = useState(null);
  const [showInvoice, setShowInvoice] = useState(false);
  const [invoice, setInvoice] = useState(null);

  const getBillingState = async (customer) => {
    setStatus("loading");
    const result1 = await apiGetBilling({ customer_id: customer.customer_id });
    const result2 = await apiGetPayments({ customer_id: customer.customer_id });

    if ((result1 === false || result2 === false) && isMounted.current) {
      setStatus("error");
    } else if (isMounted.current) {
      const temp = result1.map((e) => {
        let t = { invoice_no: e.invoice_no, bill_date: e.bill_date, invoice_amount: parseFloat(e.invoice_amount), currency_symbol: e.currency_symbol, append_after: e.append_after, is_paid: false };
        const f = result2.filter(p => p.invoice_no === e.invoice_no);
        if (f && f.length > 0) { t.is_paid = true; t.payment_date = f[0].payment_date; t.payment_amount = parseFloat(f[0].payment_amount); }
        return t;
      });

      let transactions = [];
      temp.forEach((t) => {
        if (t.is_paid) transactions.push({ invoice_no: t.invoice_no, date: t.payment_date, credit: t.payment_amount, note: "Payment, thank you!", currency_symbol: t.currency_symbol, append_after: t.append_after });
        transactions.push({ invoice_no: t.invoice_no, date: t.bill_date, debit: t.invoice_amount, note: "Monthly bill issued.", currency_symbol: t.currency_symbol, append_after: t.append_after });
      });

      const invoices = result1.map((e) => { e.invoice_amount = parseFloat(e.invoice_amount); return e; });
      const payments = result2.map((e) => { e.payment_amount = parseFloat(e.payment_amount); return e; });
      setBilling({ transactions, latestBill: invoices[0] || null, latestPayment: payments[0] || null });
      setStatus("finished");
    }
  };

  useEffect(() => { return () => { isMounted.current = false; }; }, []);
  useEffect(() => { if (isMounted.current && customer) getBillingState(customer); }, [customer]); // eslint-disable-line

  const fmtAmount = (e) => {
    const val = (e.credit ? e.credit : e.debit || 0).toFixed(2);
    const sym = e.currency_symbol || '$';
    const prefix = e.credit ? '-' : '';
    return e.append_after ? `${prefix}${val}${sym}` : `${prefix}${sym}${val}`;
  };

  return (
    <div className="px-6 py-4 space-y-4">
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <a href="#/" className="hover:text-foreground transition-colors no-underline text-muted-foreground">Dashboard</a>
        <span>/</span>
        <span className="text-foreground">Billing and payments</span>
      </nav>
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">Billing and payments</h1>

      {/* Latest Bill */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold text-card-foreground mb-4">Your latest bill</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="space-y-4">
            <div>
              <div className="text-4xl font-bold tracking-tight text-foreground">
                {billing?.latestBill && !billing.latestBill.append_after ? billing.latestBill.currency_symbol : ''}
                {billing?.latestBill ? billing.latestBill.invoice_amount.toFixed(2) : 'N/A'}
                {billing?.latestBill?.append_after ? billing.latestBill.currency_symbol : ''}
              </div>
              <div className="text-sm text-muted-foreground mt-1">statement amount</div>
            </div>
            <div>
              <div className="text-4xl font-bold tracking-tight text-foreground">{billing?.latestBill ? billing.latestBill.due_date : 'N/A'}</div>
              <div className="text-sm text-muted-foreground mt-1">due date</div>
            </div>
          </div>
          <div className="md:col-span-3 space-y-4">
            <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-500">✓ Autopay enabled</span>
            <p className="text-sm text-muted-foreground">
              Your payment method will be charged on {billing?.latestBill ? billing.latestBill.due_date : 'N/A'}.{' '}
              <a href="#/account" className="text-blue-500 hover:underline underline-offset-4">Manage Autopay</a>
            </p>
            <p className="text-sm text-muted-foreground">
              Your last bill was charged on {billing?.latestPayment ? billing.latestPayment.payment_date : 'N/A'}, in the amount of{' '}
              {billing?.latestPayment && !billing.latestPayment.append_after ? billing.latestPayment.currency_symbol : ''}
              {billing?.latestPayment ? billing.latestPayment.payment_amount.toFixed(2) : 'N/A'}
              {billing?.latestPayment?.append_after ? billing.latestBill?.currency_symbol : ''}{' '}
              for invoice {billing?.latestPayment ? billing.latestPayment.invoice_no : 'N/A'}.
            </p>
            <div className="flex gap-2">
              <button
                disabled={!billing?.latestBill || status === "loading"}
                onClick={async () => {
                  if (billing?.latestBill) {
                    const inv = await apiGetInvoice({ invoice_no: billing.latestBill.invoice_no });
                    if (inv) { setInvoice(inv); setShowInvoice(true); }
                  }
                }}
                className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-4 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
              >
                View current bill
              </button>
              {showInvoice && (
                <button onClick={() => setShowInvoice(false)} className="inline-flex items-center justify-center rounded-md text-sm font-medium h-9 px-4 border border-border bg-card hover:bg-secondary transition-colors text-foreground cursor-pointer">
                  Hide bill
                </button>
              )}
            </div>
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
        </div>
      )}

      {/* Transaction Table */}
      <div className="rounded-lg border border-border bg-card">
        <div className="p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-card-foreground">Transaction history</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-3 font-medium text-muted-foreground">Transaction date</th>
                <th className="text-left p-3 font-medium text-muted-foreground">Invoice Number</th>
                <th className="text-left p-3 font-medium text-muted-foreground">Amount</th>
                <th className="text-left p-3 font-medium text-muted-foreground">Description</th>
              </tr>
            </thead>
            <tbody>
              {status === "loading" ? (
                <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">Loading transactions...</td></tr>
              ) : billing?.transactions?.length > 0 ? (
                billing.transactions.map((t, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-secondary/30 transition-colors">
                    <td className="p-3 text-foreground">{t.date || '-'}</td>
                    <td className="p-3 text-foreground">{t.invoice_no || '-'}</td>
                    <td className="p-3 text-foreground">{fmtAmount(t)}</td>
                    <td className="p-3 text-foreground">{t.note || '-'}</td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No transactions</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

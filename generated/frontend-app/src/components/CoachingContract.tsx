import { useEffect, useState } from 'react';
import { jsPDF } from 'jspdf';
import { createContract, deleteContract, listContracts } from '../api';
import type { ContractData, ContractItem } from '../types';
import { SignaturePad } from './SignaturePad';

interface CoachingContractProps {
  currentUsername: string;
}

interface TermsSection {
  heading: string;
  body: string;
}

// Transcribed from the Executive Coaching Contract template supplied by the user.
const TERMS: readonly TermsSection[] = [
  {
    heading: 'Service Intentions',
    body: 'The Coach agrees to provide Executive Coaching services to facilitate the achievement of specific and agreed goals through a series of regular sessions over an agreed timeframe',
  },
  {
    heading: 'Responsibility of Coach',
    body: 'The Coach is responsible for providing the process of Coaching. They will facilitate and provide structure to the coaching programme.',
  },
  {
    heading: 'Responsibility of the Coachee',
    body: 'The Coachee is responsible for the content of the Coaching programme. The Coachee accepts all responsibility and accountability to the success of the programme, and will not hold the Coach liable for any perceived lack of satisfactory outcomes.',
  },
  {
    heading: 'Disclaimer',
    body: 'It is acknowledged that nothing said by Coach can be construed as advice or instruction and that Coach cannot be held be responsible for Coachee\u2019s decisions or actions.',
  },
  {
    heading: 'Confidentiality',
    body: 'All conversations and information will remain totally confidential between the Coach and Coachee throughout and after the Coaching process.',
  },
  {
    heading: 'Punctuality',
    body: 'Lack of punctuality will result in reduced session time, with the session finishing at the originally agreed completion time',
  },
  {
    heading: 'Cancellation Policy',
    body: 'Cancellations instigated by the Coachee within 48 hours of the scheduled session time will result in a 100% cancellation fee.',
  },
  {
    heading: 'Procedure on Termination',
    body: 'Either party reserves the right to terminate the programme. Should the Coachee choose to terminate, any balance outstanding for Coaching sessions undertaken will be payable immediately.',
  },
  {
    heading: 'ICF disclosure',
    body: 'It is agreed that the coach may provide details of this coaching agreement. This would be for the purpose of identifying the number of coaching hours delivered by a coach for professional accreditation purposes',
  },
] as const;

const CLOSING_STATEMENT =
  'Our signatures on this agreement indicate full understanding and agreement of the content of this contract.';

function emptyContract(): ContractData {
  return {
    agreementDate: '',
    coach: { name: '', address: '', phone: '', email: '' },
    coachee: { name: '', address: '', phone: '', email: '', dateOfBirth: '' },
    periodSessions: '',
    sessionCycle: '',
    commencementDate: '',
    totalFee: '',
    paymentArrangement: 'advance',
    coachSignatureName: '',
    coachSignature: '',
    coachSignedAt: '',
    coacheeSignatureName: '',
    coacheeSignature: '',
    coacheeSignedAt: '',
  };
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function CoachingContract({ currentUsername }: CoachingContractProps): JSX.Element {
  const [items, setItems] = useState<ContractItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ContractData>(emptyContract);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [viewing, setViewing] = useState<ContractItem | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listContracts()
      .then((data) => {
        if (!cancelled) {
          setItems(data);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setError('Could not load contracts.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function openForm(): void {
    const fresh = emptyContract();
    fresh.coach.name = currentUsername;
    fresh.coachSignatureName = currentUsername;
    setForm(fresh);
    setFormError(null);
    setFormOpen(true);
  }

  function updateForm(patch: Partial<ContractData>): void {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  function updateCoach(patch: Partial<ContractData['coach']>): void {
    setForm((prev) => ({ ...prev, coach: { ...prev.coach, ...patch } }));
  }

  function updateCoachee(patch: Partial<ContractData['coachee']>): void {
    setForm((prev) => ({ ...prev, coachee: { ...prev.coachee, ...patch } }));
  }

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setFormError(null);
    if (!form.coach.name.trim() && !form.coachee.name.trim()) {
      setFormError('Please enter at least the coach or coachee name before saving.');
      return;
    }
    const now = new Date().toISOString();
    const data: ContractData = {
      ...form,
      coachSignedAt: form.coachSignature ? form.coachSignedAt || now : '',
      coacheeSignedAt: form.coacheeSignature ? form.coacheeSignedAt || now : '',
    };
    setSaving(true);
    try {
      const title = form.coachee.name.trim()
        ? `Executive Coaching Contract \u2013 ${form.coachee.name.trim()}`
        : 'Executive Coaching Contract';
      const created = await createContract({ title, data });
      setItems((prev) => [created, ...prev]);
      setFormOpen(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not save contract.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(item: ContractItem): Promise<void> {
    if (!window.confirm('Delete this saved contract? This cannot be undone.')) return;
    try {
      await deleteContract(item.id);
      setItems((prev) => prev.filter((c) => c.id !== item.id));
      if (viewing?.id === item.id) setViewing(null);
    } catch {
      setError('Could not delete contract.');
    }
  }

  return (
    <section className='card' aria-labelledby='profile-contracts-heading'>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 id='profile-contracts-heading' style={{ margin: 0 }}>Coaching contracts</h2>
        <button type='button' className='primary' style={{ marginTop: 0 }} onClick={openForm}>
          New Contract
        </button>
      </div>

      {loading && <p className='muted'>Loading contracts...</p>}
      {error && <p className='muted' role='alert'>{error}</p>}

      {!loading && !error && items.length === 0 && (
        <p className='muted'>No contracts saved yet.</p>
      )}

      {items.length > 0 && (
        <ul className='questionnaire-list'>
          {items.map((item) => (
            <li key={item.id}>
              <div className='contract-list-row'>
                <button type='button' className='questionnaire-list-item' onClick={() => setViewing(item)}>
                  <span className='questionnaire-list-name'>{item.title || 'Executive Coaching Contract'}</span>
                  <span className='muted'>{formatDate(item.createdAt)}</span>
                </button>
                <div className='contract-list-actions'>
                  <button type='button' onClick={() => downloadContractPdf(item)}>Download PDF</button>
                  <button type='button' onClick={() => { void handleDelete(item); }}>Delete</button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {formOpen && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card contract-modal-card'>
            <button
              type='button'
              aria-label='Close contract form'
              onClick={() => setFormOpen(false)}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <h3>Executive Coaching Contract <span className='muted'>(Non-sponsored)</span></h3>
            <form onSubmit={(e) => { void handleSubmit(e); }}>
              <p className='muted'>This Executive Coaching contract refers to the following parties.</p>

              <label htmlFor='contract-date'>Agreement date</label>
              <input
                id='contract-date'
                type='date'
                value={form.agreementDate}
                onChange={(e) => updateForm({ agreementDate: e.target.value })}
              />

              <fieldset className='contract-fieldset'>
                <legend>Coach</legend>
                <label htmlFor='coach-name'>Name</label>
                <input id='coach-name' type='text' value={form.coach.name}
                  onChange={(e) => updateCoach({ name: e.target.value })} />
                <label htmlFor='coach-address'>Address</label>
                <input id='coach-address' type='text' value={form.coach.address}
                  onChange={(e) => updateCoach({ address: e.target.value })} />
                <label htmlFor='coach-phone'>Contact phone number</label>
                <input id='coach-phone' type='tel' value={form.coach.phone}
                  onChange={(e) => updateCoach({ phone: e.target.value })} />
                <label htmlFor='coach-email'>Email address</label>
                <input id='coach-email' type='email' value={form.coach.email}
                  onChange={(e) => updateCoach({ email: e.target.value })} />
              </fieldset>

              <fieldset className='contract-fieldset'>
                <legend>Coachee</legend>
                <label htmlFor='coachee-name'>Name</label>
                <input id='coachee-name' type='text' value={form.coachee.name}
                  onChange={(e) => updateCoachee({ name: e.target.value })} />
                <label htmlFor='coachee-address'>Address</label>
                <input id='coachee-address' type='text' value={form.coachee.address}
                  onChange={(e) => updateCoachee({ address: e.target.value })} />
                <label htmlFor='coachee-phone'>Contact phone number</label>
                <input id='coachee-phone' type='tel' value={form.coachee.phone}
                  onChange={(e) => updateCoachee({ phone: e.target.value })} />
                <label htmlFor='coachee-email'>Email address</label>
                <input id='coachee-email' type='email' value={form.coachee.email}
                  onChange={(e) => updateCoachee({ email: e.target.value })} />
                <label htmlFor='coachee-dob'>Date of birth</label>
                <input id='coachee-dob' type='date' value={form.coachee.dateOfBirth}
                  onChange={(e) => updateCoachee({ dateOfBirth: e.target.value })} />
              </fieldset>

              <fieldset className='contract-fieldset'>
                <legend>Coaching series</legend>
                <label htmlFor='contract-period'>Period of the coaching (series of ___ sessions)</label>
                <input id='contract-period' type='text' value={form.periodSessions}
                  onChange={(e) => updateForm({ periodSessions: e.target.value })} />
                <label htmlFor='contract-cycle'>Session cycle (weekly, fortnightly, monthly etc)</label>
                <input id='contract-cycle' type='text' value={form.sessionCycle}
                  onChange={(e) => updateForm({ sessionCycle: e.target.value })} />
                <label htmlFor='contract-commence'>Commencement date for coaching</label>
                <input id='contract-commence' type='date' value={form.commencementDate}
                  onChange={(e) => updateForm({ commencementDate: e.target.value })} />
                <label htmlFor='contract-fee'>Total fee for period of coaching series</label>
                <input id='contract-fee' type='text' value={form.totalFee}
                  onChange={(e) => updateForm({ totalFee: e.target.value })} />
                <label htmlFor='contract-payment'>Payment arrangement</label>
                <select id='contract-payment' value={form.paymentArrangement}
                  onChange={(e) => updateForm({ paymentArrangement: e.target.value as ContractData['paymentArrangement'] })}>
                  <option value='advance'>Series payment in advance</option>
                  <option value='instalments'>Instalments in advance</option>
                </select>
              </fieldset>

              <details className='contract-terms-preview'>
                <summary>Terms &amp; conditions</summary>
                {TERMS.map((section) => (
                  <div key={section.heading} className='contract-term'>
                    <strong>{section.heading}</strong>
                    <p className='muted'>{section.body}</p>
                  </div>
                ))}
                <p className='muted'>{CLOSING_STATEMENT}</p>
              </details>

              <fieldset className='contract-fieldset'>
                <legend>Signatures</legend>
                <label htmlFor='coach-sign-name'>Coach&rsquo;s name</label>
                <input id='coach-sign-name' type='text' value={form.coachSignatureName}
                  onChange={(e) => updateForm({ coachSignatureName: e.target.value })} />
                <SignaturePad
                  label="Coach's signature"
                  value={form.coachSignature}
                  onChange={(dataUrl) => updateForm({ coachSignature: dataUrl, coachSignedAt: dataUrl ? new Date().toISOString() : '' })}
                />
                <label htmlFor='coachee-sign-name'>Coachee&rsquo;s name</label>
                <input id='coachee-sign-name' type='text' value={form.coacheeSignatureName}
                  onChange={(e) => updateForm({ coacheeSignatureName: e.target.value })} />
                <SignaturePad
                  label="Coachee's signature"
                  value={form.coacheeSignature}
                  onChange={(dataUrl) => updateForm({ coacheeSignature: dataUrl, coacheeSignedAt: dataUrl ? new Date().toISOString() : '' })}
                />
              </fieldset>

              {formError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{formError}</p>}

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button type='submit' className='primary' style={{ marginTop: 0 }} disabled={saving}>
                  {saving ? 'Saving...' : 'Save contract'}
                </button>
                <button type='button' onClick={() => setFormOpen(false)} disabled={saving}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {viewing && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card contract-modal-card'>
            <button
              type='button'
              aria-label='Close contract'
              onClick={() => setViewing(null)}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <ContractView contract={viewing} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button type='button' className='primary' style={{ marginTop: 0 }} onClick={() => downloadContractPdf(viewing)}>
                Download PDF
              </button>
              <button type='button' onClick={() => setViewing(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className='contract-view-row'>
      <dt>{label}</dt>
      <dd>{value ? value : <span className='muted'>&mdash;</span>}</dd>
    </div>
  );
}

function ContractView({ contract }: { contract: ContractItem }): JSX.Element {
  const d = contract.data;
  return (
    <div>
      <h3>Executive Coaching Contract <span className='muted'>(Non-sponsored)</span></h3>
      <p className='muted'>Saved {formatDate(contract.createdAt)}{d.agreementDate ? ` \u00b7 Dated ${d.agreementDate}` : ''}</p>

      <h4>Coach</h4>
      <dl className='contract-view'>
        <Row label='Name' value={d.coach.name} />
        <Row label='Address' value={d.coach.address} />
        <Row label='Contact phone' value={d.coach.phone} />
        <Row label='Email' value={d.coach.email} />
      </dl>

      <h4>Coachee</h4>
      <dl className='contract-view'>
        <Row label='Name' value={d.coachee.name} />
        <Row label='Address' value={d.coachee.address} />
        <Row label='Contact phone' value={d.coachee.phone} />
        <Row label='Email' value={d.coachee.email} />
        <Row label='Date of birth' value={d.coachee.dateOfBirth} />
      </dl>

      <h4>Coaching series</h4>
      <dl className='contract-view'>
        <Row label='Period (sessions)' value={d.periodSessions} />
        <Row label='Session cycle' value={d.sessionCycle} />
        <Row label='Commencement date' value={d.commencementDate} />
        <Row label='Total fee' value={d.totalFee} />
        <Row label='Payment arrangement' value={d.paymentArrangement === 'instalments' ? 'Instalments in advance' : 'Series payment in advance'} />
      </dl>

      <h4>Signatures</h4>
      <div className='contract-view-signatures'>
        <div>
          <span className='muted'>{d.coachSignatureName || 'Coach'}</span>
          {d.coachSignature
            ? <img src={d.coachSignature} alt='Coach signature' className='contract-view-sig' />
            : <p className='muted'>Not signed</p>}
          {d.coachSignedAt && <span className='muted'>Signed {formatDate(d.coachSignedAt)}</span>}
        </div>
        <div>
          <span className='muted'>{d.coacheeSignatureName || 'Coachee'}</span>
          {d.coacheeSignature
            ? <img src={d.coacheeSignature} alt='Coachee signature' className='contract-view-sig' />
            : <p className='muted'>Not signed</p>}
          {d.coacheeSignedAt && <span className='muted'>Signed {formatDate(d.coacheeSignedAt)}</span>}
        </div>
      </div>
    </div>
  );
}

/** Build and trigger download of a PDF that mirrors the contract layout. */
function downloadContractPdf(contract: ContractItem): void {
  const d = contract.data;
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const margin = 48;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  function ensureSpace(needed: number): void {
    if (y + needed > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  }

  function heading(text: string, size = 13): void {
    ensureSpace(size + 10);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(size);
    doc.text(text, margin, y);
    y += size + 6;
  }

  function paragraph(text: string, size = 10): void {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(text, contentWidth) as string[];
    lines.forEach((line) => {
      ensureSpace(size + 4);
      doc.text(line, margin, y);
      y += size + 4;
    });
  }

  function field(label: string, value: string): void {
    ensureSpace(16);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(`${label}:`, margin, y);
    const labelWidth = doc.getTextWidth(`${label}: `);
    doc.setFont('helvetica', 'normal');
    const lines = doc.splitTextToSize(value || '\u2014', contentWidth - labelWidth) as string[];
    doc.text(lines[0] ?? '', margin + labelWidth, y);
    y += 14;
    for (let i = 1; i < lines.length; i += 1) {
      ensureSpace(14);
      doc.text(lines[i], margin + labelWidth, y);
      y += 14;
    }
  }

  heading('Executive Coaching Contract (Non-sponsored)', 15);
  paragraph('This Executive Coaching contract refers to the following parties.');
  if (d.agreementDate) paragraph(`This agreement is dated ${d.agreementDate}.`);
  y += 6;

  heading('Coach', 12);
  field('Name', d.coach.name);
  field('Address', d.coach.address);
  field('Contact Phone Numbers', d.coach.phone);
  field('Email Address', d.coach.email);
  y += 6;

  heading('Coachee', 12);
  field('Name', d.coachee.name);
  field('Address', d.coachee.address);
  field('Contact Phone Numbers', d.coachee.phone);
  field('Email Address', d.coachee.email);
  field('Date of Birth', d.coachee.dateOfBirth);
  y += 6;

  paragraph('All parties as stated agree to be bound by the Terms and Conditions herewith, for the Period of Coaching Sessions specified as follows:');
  field('Period of the Coaching (Series of sessions)', d.periodSessions);
  field('Session Cycle (weekly, fortnightly, monthly etc)', d.sessionCycle);
  field('Commencement Date for Coaching', d.commencementDate);
  field('Total Fee for Period of Coaching Series', d.totalFee);
  field('Payment Arrangement', d.paymentArrangement === 'instalments' ? 'Instalments in advance' : 'Series Payment in advance');
  y += 10;

  TERMS.forEach((section) => {
    heading(section.heading, 11);
    paragraph(section.body);
    y += 4;
  });

  y += 6;
  paragraph(CLOSING_STATEMENT);
  y += 10;

  ensureSpace(120);
  const colWidth = (contentWidth - 20) / 2;
  const sigTop = y;
  const signatureBlock = (x: number, name: string, image: string, role: string, signedAt: string): void => {
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.text(`${role}'s Name:`, x, sigTop);
    doc.setFont('helvetica', 'normal');
    doc.text(name || '\u2014', x + 90, sigTop);
    if (image) {
      try {
        doc.addImage(image, 'PNG', x, sigTop + 12, 160, 46);
      } catch {
        /* ignore malformed image data */
      }
    }
    doc.line(x, sigTop + 62, x + colWidth, sigTop + 62);
    doc.setFontSize(9);
    doc.setTextColor(120);
    doc.text(`${role}'s Signature${signedAt ? ` \u00b7 ${formatDate(signedAt)}` : ''}`, x, sigTop + 74);
    doc.setTextColor(0);
  };
  signatureBlock(margin, d.coachSignatureName, d.coachSignature, 'Coach', d.coachSignedAt);
  signatureBlock(margin + colWidth + 20, d.coacheeSignatureName, d.coacheeSignature, 'Coachee', d.coacheeSignedAt);

  const safeName = (d.coachee.name || 'contract').replace(/[^a-z0-9]+/gi, '-').toLowerCase();
  doc.save(`executive-coaching-contract-${safeName}.pdf`);
}

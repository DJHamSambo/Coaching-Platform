import { useEffect, useMemo, useState } from 'react';
import { jsPDF } from 'jspdf';
import { createContract, deleteContract, listAdminCoachees, listContracts, updateContract } from '../api';
import type { AdminCoachee, ContractData, ContractItem, CurrentUser } from '../types';
import { SignaturePad } from './SignaturePad';

interface CoachingContractProps {
  currentUser: CurrentUser;
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

function statusLabel(item: ContractItem, currentUsername: string): string {
  if (item.status === 'executed') return 'Fully executed';
  if (item.coacheeUsername === currentUsername) return 'Awaiting your signature';
  return 'Awaiting coachee\u2019s signature';
}

export function CoachingContract({ currentUser }: CoachingContractProps): JSX.Element {
  const isCoachee = currentUser.role === 'coachee';
  const [items, setItems] = useState<ContractItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [coachees, setCoachees] = useState<AdminCoachee[]>([]);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ContractData>(emptyContract);
  const [selectedCoacheeId, setSelectedCoacheeId] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [viewing, setViewing] = useState<ContractItem | null>(null);

  const [reviewing, setReviewing] = useState<ContractItem | null>(null);
  const [reviewAddress, setReviewAddress] = useState('');
  const [reviewPhone, setReviewPhone] = useState('');
  const [reviewEmail, setReviewEmail] = useState('');
  const [reviewDob, setReviewDob] = useState('');
  const [reviewAccepted, setReviewAccepted] = useState(false);
  const [reviewSignatureName, setReviewSignatureName] = useState('');
  const [reviewSignature, setReviewSignature] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

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

  useEffect(() => {
    if (isCoachee) return;
    let cancelled = false;
    listAdminCoachees()
      .then((data) => {
        if (!cancelled) setCoachees(data.filter((c) => Boolean(c.user)));
      })
      .catch(() => {
        /* silently ignore; the coachee dropdown will just be empty */
      });
    return () => {
      cancelled = true;
    };
  }, [isCoachee]);

  const availableCoachees = useMemo(() => coachees, [coachees]);

  function openForm(): void {
    const fresh = emptyContract();
    fresh.coach.name = currentUser.username;
    fresh.coach.phone = currentUser.phone;
    fresh.coach.email = currentUser.email;
    fresh.coachSignatureName = currentUser.username;
    setForm(fresh);
    setSelectedCoacheeId('');
    setFormError(null);
    setFormOpen(true);
  }

  function updateForm(patch: Partial<ContractData>): void {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  function updateCoach(patch: Partial<ContractData['coach']>): void {
    setForm((prev) => ({ ...prev, coach: { ...prev.coach, ...patch } }));
  }

  function handleCoacheeSelect(id: string): void {
    setSelectedCoacheeId(id);
    const chosen = coachees.find((c) => c.id === id);
    setForm((prev) => ({
      ...prev,
      coachee: {
        ...prev.coachee,
        name: chosen?.name ?? '',
        phone: chosen?.userPhone ?? '',
        email: chosen?.userEmail || chosen?.email || '',
      },
    }));
  }

  async function handleSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setFormError(null);
    if (!form.coach.name.trim()) {
      setFormError('Please enter your name before saving.');
      return;
    }
    if (!selectedCoacheeId) {
      setFormError('Please select a coachee for this contract.');
      return;
    }
    if (!form.coachSignature) {
      setFormError('Please sign the contract before saving.');
      return;
    }
    const now = new Date().toISOString();
    const data: ContractData = {
      ...form,
      coachSignedAt: form.coachSignature ? form.coachSignedAt || now : '',
    };
    setSaving(true);
    try {
      const title = form.coachee.name.trim()
        ? `Executive Coaching Contract \u2013 ${form.coachee.name.trim()}`
        : 'Executive Coaching Contract';
      const created = await createContract({ title, data, coacheeId: selectedCoacheeId });
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

  function openReview(item: ContractItem): void {
    setReviewing(item);
    setReviewAddress(item.data.coachee.address ?? '');
    setReviewPhone(item.data.coachee.phone || currentUser.phone);
    setReviewEmail(item.data.coachee.email || currentUser.email);
    setReviewDob(item.data.coachee.dateOfBirth ?? '');
    setReviewAccepted(item.coacheeAcceptedTerms);
    setReviewSignatureName(item.data.coacheeSignatureName || currentUser.username);
    setReviewSignature(item.data.coacheeSignature ?? '');
    setReviewError(null);
  }

  async function handleReviewSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!reviewing) return;
    setReviewError(null);
    if (!reviewAccepted) {
      setReviewError('Please accept the terms and conditions before signing.');
      return;
    }
    if (!reviewSignature) {
      setReviewError('Please sign the contract before submitting.');
      return;
    }
    const updatedData: ContractData = {
      ...reviewing.data,
      coachee: {
        ...reviewing.data.coachee,
        address: reviewAddress,
        phone: reviewPhone,
        email: reviewEmail,
        dateOfBirth: reviewDob,
      },
      coacheeSignatureName: reviewSignatureName,
      coacheeSignature: reviewSignature,
      coacheeSignedAt: new Date().toISOString(),
    };
    setReviewSaving(true);
    try {
      const updated = await updateContract(reviewing.id, { data: updatedData, coacheeAcceptedTerms: true });
      setItems((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setReviewing(null);
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : 'Could not submit your signature.');
    } finally {
      setReviewSaving(false);
    }
  }

  return (
    <section className='card' aria-labelledby='profile-contracts-heading'>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h2 id='profile-contracts-heading' style={{ margin: 0 }}>Coaching contracts</h2>
        {!isCoachee && (
          <button type='button' className='primary' style={{ marginTop: 0 }} onClick={openForm}>
            New Contract
          </button>
        )}
      </div>

      {loading && <p className='muted'>Loading contracts...</p>}
      {error && <p className='muted' role='alert'>{error}</p>}

      {!loading && !error && items.length === 0 && (
        <p className='muted'>No contracts saved yet.</p>
      )}

      {items.length > 0 && (
        <ul className='questionnaire-list'>
          {items.map((item) => {
            const awaitingMe = isCoachee && item.status === 'awaiting_coachee' && item.coacheeUsername === currentUser.username;
            return (
              <li key={item.id}>
                <div className='contract-list-row'>
                  <button type='button' className='questionnaire-list-item' onClick={() => setViewing(item)}>
                    <span className='questionnaire-list-name'>{item.title || 'Executive Coaching Contract'}</span>
                    <span className='muted'>{formatDate(item.createdAt)} {'\u00b7'} {statusLabel(item, currentUser.username)}</span>
                  </button>
                  <div className='contract-list-actions'>
                    {awaitingMe && (
                      <button type='button' className='primary' onClick={() => openReview(item)}>Review &amp; sign</button>
                    )}
                    <button type='button' onClick={() => downloadContractPdf(item)}>Download PDF</button>
                    {!isCoachee && (
                      <button type='button' onClick={() => { void handleDelete(item); }}>Delete</button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
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
              <p className='muted'>This Executive Coaching contract refers to the following parties. Once you sign and save, your coachee will be notified to review, accept the terms, and co-sign.</p>

              <label htmlFor='contract-date'>Agreement date</label>
              <input
                id='contract-date'
                type='date'
                value={form.agreementDate}
                onChange={(e) => updateForm({ agreementDate: e.target.value })}
              />

              <fieldset className='contract-fieldset'>
                <legend>Coach (you)</legend>
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
                <label htmlFor='contract-coachee'>Select coachee</label>
                <select
                  id='contract-coachee'
                  value={selectedCoacheeId}
                  onChange={(e) => handleCoacheeSelect(e.target.value)}
                >
                  <option value=''>Choose a coachee&hellip;</option>
                  {availableCoachees.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                {availableCoachees.length === 0 && (
                  <p className='muted'>No coachees with a linked login are available yet. Add a coachee and link their account first.</p>
                )}
                {selectedCoacheeId && (
                  <p className='muted'>
                    {form.coachee.email || 'No email on file'}{form.coachee.phone ? ` \u00b7 ${form.coachee.phone}` : ''} &mdash; they will fill in their address and date of birth when they review and sign.
                  </p>
                )}
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
                <legend>Your signature</legend>
                <label htmlFor='coach-sign-name'>Your name</label>
                <input id='coach-sign-name' type='text' value={form.coachSignatureName}
                  onChange={(e) => updateForm({ coachSignatureName: e.target.value })} />
                <SignaturePad
                  label="Your signature"
                  value={form.coachSignature}
                  onChange={(dataUrl) => updateForm({ coachSignature: dataUrl, coachSignedAt: dataUrl ? new Date().toISOString() : '' })}
                />
              </fieldset>

              {formError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{formError}</p>}

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button type='submit' className='primary' style={{ marginTop: 0 }} disabled={saving}>
                  {saving ? 'Saving...' : 'Sign & send to coachee'}
                </button>
                <button type='button' onClick={() => setFormOpen(false)} disabled={saving}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {reviewing && (
        <div className='admin-panel-modal-overlay'>
          <div className='admin-panel-modal-card contract-modal-card'>
            <button
              type='button'
              aria-label='Close review form'
              onClick={() => setReviewing(null)}
              className='admin-panel-modal-close'
            >
              x
            </button>
            <h3>Review &amp; sign your coaching contract</h3>
            <p className='muted'>
              {reviewing.coachUsername ?? 'Your coach'} has sent you this coaching contract. Please review the details below, fill in your information, accept the terms and conditions, and co-sign to fully execute the contract.
            </p>

            <ContractView contract={reviewing} />

            <form onSubmit={(e) => { void handleReviewSubmit(e); }}>
              <fieldset className='contract-fieldset'>
                <legend>Your details</legend>
                <label htmlFor='review-address'>Address</label>
                <input id='review-address' type='text' value={reviewAddress}
                  onChange={(e) => setReviewAddress(e.target.value)} />
                <label htmlFor='review-phone'>Contact phone number</label>
                <input id='review-phone' type='tel' value={reviewPhone}
                  onChange={(e) => setReviewPhone(e.target.value)} />
                <label htmlFor='review-email'>Email address</label>
                <input id='review-email' type='email' value={reviewEmail}
                  onChange={(e) => setReviewEmail(e.target.value)} />
                <label htmlFor='review-dob'>Date of birth</label>
                <input id='review-dob' type='date' value={reviewDob}
                  onChange={(e) => setReviewDob(e.target.value)} />
              </fieldset>

              <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, margin: '12px 0' }}>
                <input
                  type='checkbox'
                  checked={reviewAccepted}
                  onChange={(e) => setReviewAccepted(e.target.checked)}
                />
                <span>I have read and accept the terms and conditions of this coaching contract.</span>
              </label>

              <fieldset className='contract-fieldset'>
                <legend>Your signature</legend>
                <label htmlFor='coachee-sign-name'>Your name</label>
                <input id='coachee-sign-name' type='text' value={reviewSignatureName}
                  onChange={(e) => setReviewSignatureName(e.target.value)} />
                <SignaturePad
                  label="Your signature"
                  value={reviewSignature}
                  onChange={(dataUrl) => setReviewSignature(dataUrl)}
                />
              </fieldset>

              {reviewError && <p className='muted' role='alert' style={{ color: '#e5484d' }}>{reviewError}</p>}

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button type='submit' className='primary' style={{ marginTop: 0 }} disabled={reviewSaving}>
                  {reviewSaving ? 'Submitting...' : 'Accept & co-sign'}
                </button>
                <button type='button' onClick={() => setReviewing(null)} disabled={reviewSaving}>
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
      <p className='muted'>
        Saved {formatDate(contract.createdAt)}{d.agreementDate ? ` \u00b7 Dated ${d.agreementDate}` : ''}
        {' \u00b7 '}{contract.status === 'executed' ? 'Fully executed' : 'Awaiting coachee\u2019s signature'}
      </p>

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

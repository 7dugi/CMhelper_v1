import React, { useState, useEffect } from 'react';
import { Plus, Edit2, X, ChevronRight, ChevronDown, Save } from 'lucide-react';
import * as api from '../../api';

export const OPPORTUNITY_STATUS_LABELS = {
  NEW: "신규 상담",
  QUOTING: "견적 진행",
  NEGOTIATING: "협의 중",
  WON: "계약 확정",
  LOST: "계약 실패",
  ON_HOLD: "보류",
};

export const PRODUCT_TYPE_LABELS = {
  RENT: "장기렌트",
  LEASE: "리스",
  INSTALLMENT: "할부",
  CASH: "일시불",
};

const formatMoney = (val) => {
  if (val === null || val === undefined || val === '') return '';
  return Number(val).toLocaleString() + '원';
};

const formatRate = (val) => {
  if (val === null || val === undefined || val === '') return '';
  return Number(val).toFixed(2) + '%';
};

const parseMoney = (val) => {
  if (val === null || val === undefined || val === '') return null;
  const num = parseInt(val.toString().replace(/[^0-9]/g, ''), 10);
  return isNaN(num) ? null : num;
};

// --- Quote Form ---
function QuoteForm({ initial, opportunityId, onSave, onClose, user }) {
  const [form, setForm] = useState(() => ({
    product_type: initial?.product_type || 'RENT',
    vehicle_name: initial?.vehicle_name || '',
    vehicle_price: initial?.vehicle_price || null,
    discount_amount: initial?.discount_amount || null,
    deposit_amount: initial?.deposit_amount || null,
    down_payment: initial?.down_payment || null,
    monthly_payment: initial?.monthly_payment || null,
    residual_value: initial?.residual_value || null,
    term_months: initial?.term_months || null,
    interest_rate: initial?.interest_rate || null,
    residual_rate: initial?.residual_rate || null,
    annual_mileage: initial?.annual_mileage || null,
    capital_company: initial?.capital_company || '',
    notes: initial?.notes || '',
    assigned_user_id: initial?.assigned_user_id || user.id,
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const data = { ...form };
      if (user.role !== 'OWNER') {
        delete data.assigned_user_id;
      }
      if (!initial) {
        data.opportunity_id = opportunityId;
        await api.createQuote(data);
      } else {
        await api.updateQuote(initial.id, data);
      }
      onSave();
    } catch (err) {
      if (err.message.includes('403')) setError('해당 견적에 접근할 권한이 없습니다.');
      else if (err.message.includes('422')) setError('입력한 정보를 확인해 주세요.');
      else setError('견적을 저장하지 못했습니다.');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="quote-form">
      <div className="modal-body">
        {error && <div className="alert alert-err" style={{ marginBottom: '1rem' }}>{error}</div>}
        <div className="form-grid-2">
          <div className="form-row">
            <label className="form-label">상품 유형</label>
            <select className="form-select" value={form.product_type} onChange={e => set('product_type', e.target.value)}>
              {Object.entries(PRODUCT_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="form-row">
            <label className="form-label">차량명</label>
            <input className="form-input" value={form.vehicle_name} onChange={e => set('vehicle_name', e.target.value)} required />
          </div>
          <div className="form-row">
            <label className="form-label">월 납입금 (선택)</label>
            <input className="form-input" value={form.monthly_payment ? form.monthly_payment.toLocaleString() : ''} onChange={e => set('monthly_payment', parseMoney(e.target.value))} />
          </div>
        </div>
        <div className="form-row" style={{ marginTop: '1rem' }}>
          <label className="form-label">견적 메모</label>
          <textarea className="form-input" style={{ minHeight: '120px' }} value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="예: 롯데렌터카 48개월 / 보증금 20%&#10;월 685,000원&#10;현대캐피탈보다 약 2만원 저렴&#10;고객 카톡 발송 완료" />
        </div>
      </div>
      <div className="modal-ft">
        <button type="button" className="btn btn-secondary" onClick={onClose}>취소</button>
        <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? '저장 중...' : '견적 저장'}</button>
      </div>
    </form>
  );
}

// --- Quote List ---
function QuoteList({ opportunityId, user, quotes, loadQuotes }) {
  const [modalMode, setModalMode] = useState(null); // 'create' | 'edit'
  const [selectedQuote, setSelectedQuote] = useState(null);

  const handleSave = () => {
    setModalMode(null);
    setSelectedQuote(null);
    loadQuotes();
  };

  return (
    <div style={{ marginTop: '1rem', padding: '1rem', background: 'var(--bg-input)', borderRadius: '8px', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h4 style={{ margin: 0, fontSize: '0.9rem' }}>견적</h4>
        <button className="btn btn-secondary btn-sm" onClick={() => setModalMode('create')} style={{ padding: '0.2rem 0.6rem' }}>
          <Plus size={12}/> 견적 추가
        </button>
      </div>

      {quotes.length === 0 ? (
        <p style={{ color:'var(--text-3)', fontSize:'.82rem', textAlign:'center', padding:'1rem 0' }}>등록된 견적이 없습니다.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {quotes.map((q, i) => (
            <div key={q.id} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', background: 'var(--bg-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginBottom: '0.2rem' }}>견적 #{i+1}</div>
                  <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-1)' }}>{q.vehicle_name}</div>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); setSelectedQuote(q); setModalMode('edit'); }}>
                  <Edit2 size={14} style={{ marginRight: '4px' }}/> 수정
                </button>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-2)', display: 'flex', gap: '1rem', marginBottom: q.notes ? '0.75rem' : '0' }}>
                <div><span style={{ color: 'var(--text-3)' }}>상품:</span> {PRODUCT_TYPE_LABELS[q.product_type]}</div>
                <div><span style={{ color: 'var(--text-3)' }}>월 납입금:</span> {formatMoney(q.monthly_payment) || '-'}</div>
              </div>
              {q.notes && (
                <div style={{ fontSize: '0.85rem', whiteSpace: 'pre-wrap', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '6px', color: 'var(--text-2)' }}>
                  {q.notes}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {modalMode && (
        <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={() => { setModalMode(null); setSelectedQuote(null); }}>
          <div className="modal" style={{ maxWidth: '600px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-hd">
              <h2>{modalMode === 'create' ? '새 견적 추가' : '견적 수정'}</h2>
              <button className="btn btn-ghost btn-icon" onClick={() => { setModalMode(null); setSelectedQuote(null); }}><X size={16}/></button>
            </div>
            <QuoteForm 
              initial={modalMode === 'edit' ? selectedQuote : null} 
              opportunityId={opportunityId}
              onSave={handleSave} 
              onClose={() => { setModalMode(null); setSelectedQuote(null); }} 
              user={user} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

// --- Opportunity Detail ---
function OpportunityDetail({ opportunity, onUpdate, onBack, user, adminUsers }) {
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingStatus, setSavingStatus] = useState(false);
  
  const loadQuotes = async () => {
    try {
      setLoading(true);
      const res = await api.getOpportunityQuotes(opportunity.id);
      setQuotes(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuotes();
  }, [opportunity.id]);

  const handleStatusChange = async (e) => {
    const newStatus = e.target.value;
    setSavingStatus(true);
    try {
      const updated = await api.updateOpportunity(opportunity.id, { status: newStatus });
      onUpdate(updated);
    } catch (err) {
      if (err.message.includes('403')) alert('해당 상담에 접근할 권한이 없습니다.');
      else alert('상태를 업데이트하지 못했습니다.');
    } finally {
      setSavingStatus(false);
    }
  };

  const handleAssigneeChange = async (e) => {
    if (user.role !== 'OWNER') return;
    const newAssignee = parseInt(e.target.value, 10);
    try {
      const updated = await api.updateOpportunity(opportunity.id, { assigned_user_id: newAssignee });
      onUpdate(updated);
    } catch (err) {
      alert('담당자를 변경할 권한이 없습니다.');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem', cursor: 'pointer', color: 'var(--primary)' }} onClick={onBack}>
        <ChevronRight size={16} style={{ transform: 'rotate(180deg)', marginRight: 4 }} /> 상담 목록으로 돌아가기
      </div>
      
      <div style={{ padding: '1rem', border: '1px solid var(--border)', borderRadius: '8px', background: 'var(--bg)' }}>
        <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem' }}>{opportunity.title}</h3>
        
        <div className="form-grid-2">
          <div className="form-row">
            <label className="form-label" style={{ fontSize: '0.8rem' }}>상담 상태</label>
            <select className="form-select" value={opportunity.status} onChange={handleStatusChange} disabled={savingStatus}>
              {Object.entries(OPPORTUNITY_STATUS_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          
          <div className="form-row">
            <label className="form-label" style={{ fontSize: '0.8rem' }}>담당자</label>
            {user.role === 'OWNER' ? (
              <select className="form-select" value={opportunity.assigned_user_id || ''} onChange={handleAssigneeChange}>
                <option value="">담당자 없음</option>
                {adminUsers.map(u => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>
            ) : (
              <input className="form-input" readOnly value={opportunity.assigned_user_name || '담당자 없음'} />
            )}
          </div>
        </div>

        {opportunity.notes && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-input)', borderRadius: '4px', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
            {opportunity.notes}
          </div>
        )}
      </div>

      {loading ? (
        <p style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-3)' }}>불러오는 중...</p>
      ) : (
        <QuoteList opportunityId={opportunity.id} user={user} quotes={quotes} loadQuotes={loadQuotes} />
      )}
    </div>
  );
}

// --- Opportunity Form ---
function OpportunityForm({ initial, customerId, onSave, onClose, user, adminUsers }) {
  const [form, setForm] = useState(() => ({
    title: initial?.title || '',
    status: initial?.status || 'NEW',
    notes: initial?.notes || '',
    assigned_user_id: initial?.assigned_user_id || user.id,
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const data = { ...form };
      if (user.role !== 'OWNER') {
        delete data.assigned_user_id;
      }
      if (!initial) {
        data.customer_id = customerId;
        delete data.status; // status is handled by backend default 'NEW' on creation
        await api.createOpportunity(data);
      } else {
        await api.updateOpportunity(initial.id, data);
      }
      onSave();
    } catch (err) {
      if (err.message.includes('403')) setError('해당 상담에 접근할 권한이 없습니다.');
      else if (err.message.includes('422')) setError('입력한 정보를 확인해 주세요.');
      else setError('상담을 저장하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="opportunity-form">
      <div className="modal-body">
        {error && <div className="alert alert-err" style={{ marginBottom: '1rem' }}>{error}</div>}
        
        <div className="form-row" style={{ marginBottom: '1rem' }}>
          <label className="form-label">상담 제목</label>
          <input className="form-input" value={form.title} onChange={e => set('title', e.target.value)} required placeholder="예: GV80 차량 교체 상담" />
        </div>
        
        <div className="form-grid-2" style={{ marginBottom: '1rem' }}>
          <div className="form-row">
            <label className="form-label">상담 상태</label>
            <select className="form-select" value={form.status} onChange={e => set('status', e.target.value)}>
              {Object.entries(OPPORTUNITY_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          
          <div className="form-row">
            <label className="form-label">담당자</label>
            {user.role === 'OWNER' ? (
              <select className="form-select" value={form.assigned_user_id || ''} onChange={e => set('assigned_user_id', parseInt(e.target.value, 10))}>
                <option value="">담당자 없음</option>
                {adminUsers.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            ) : (
              <input className="form-input" readOnly value={user.name} />
            )}
          </div>
        </div>

        <div className="form-row">
          <label className="form-label">메모</label>
          <textarea className="form-input" style={{ minHeight: '80px' }} value={form.notes} onChange={e => set('notes', e.target.value)} />
        </div>
      </div>
      <div className="modal-ft">
        <button type="button" className="btn btn-secondary" onClick={onClose}>취소</button>
        <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? '저장 중...' : '상담 저장'}</button>
      </div>
    </form>
  );
}

// --- Main Exported Component ---
export default function OpportunitySection({ customerId, user, adminUsers }) {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalMode, setModalMode] = useState(null); // 'create'
  const [activeViewOpp, setActiveViewOpp] = useState(null); // for detail view

  const load = async () => {
    try {
      setLoading(true);
      const data = await api.getCustomerOpportunities(customerId);
      setOpportunities(data || []);
      // If we are viewing a specific opportunity, update it
      if (activeViewOpp) {
        const updated = data.find(o => o.id === activeViewOpp.id);
        if (updated) setActiveViewOpp(updated);
        else setActiveViewOpp(null);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (customerId) load();
  }, [customerId]);

  if (activeViewOpp) {
    return (
      <div style={{ marginBottom: '1.5rem' }}>
        <OpportunityDetail 
          opportunity={activeViewOpp} 
          onUpdate={(updated) => load()}
          onBack={() => setActiveViewOpp(null)}
          user={user}
          adminUsers={adminUsers}
        />
      </div>
    );
  }

  return (
    <div style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom:'1rem' }}>
        <h3 style={{ fontSize:'.9rem', fontWeight:600, margin: 0 }}>📊 상담</h3>
        <button className="btn btn-secondary btn-sm" onClick={() => setModalMode('create')} style={{ padding: '0.2rem 0.6rem' }}>
          <Plus size={12}/> 새 상담
        </button>
      </div>

      {loading ? (
        <p style={{ color:'var(--text-3)', fontSize:'.82rem', textAlign:'center', padding:'1rem 0' }}>불러오는 중...</p>
      ) : opportunities.length === 0 ? (
        <p style={{ color:'var(--text-3)', fontSize:'.82rem', textAlign:'center', padding:'1rem 0' }}>등록된 상담이 없습니다.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {opportunities.map(opp => (
            <div key={opp.id} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', background: 'var(--bg-input)', cursor: 'pointer' }} onClick={() => setActiveViewOpp(opp)}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>{opp.title}</span>
                <span className="badge badge-sys">{OPPORTUNITY_STATUS_LABELS[opp.status]}</span>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-2)', display: 'flex', gap: '1rem' }}>
                <div><strong>담당자:</strong> {opp.assigned_user_name || '-'}</div>
                <div><strong>등록일:</strong> {opp.created_at ? new Date(opp.created_at).toLocaleDateString() : '-'}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalMode === 'create' && (
        <div className="modal-overlay" style={{ zIndex: 9999 }} onClick={() => setModalMode(null)}>
          <div className="modal" style={{ maxWidth: '500px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-hd">
              <h2>새 상담</h2>
              <button className="btn btn-ghost btn-icon" onClick={() => setModalMode(null)}><X size={16}/></button>
            </div>
            <OpportunityForm 
              initial={null} 
              customerId={customerId}
              onSave={() => { setModalMode(null); load(); }} 
              onClose={() => setModalMode(null)}
              user={user}
              adminUsers={adminUsers}
            />
          </div>
        </div>
      )}
    </div>
  );
}

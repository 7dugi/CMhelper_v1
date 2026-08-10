import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Users, FileSpreadsheet, Settings, Database,
  Plus, Search, X, Send, Trash2, Eye, EyeOff,
  ChevronRight, UploadCloud, CheckCircle, AlertCircle,
  Shield, RefreshCw, ServerCrash, ChevronUp, ChevronDown,
  Star, Clock, Edit2, Calendar, MessageSquare, LogOut
} from 'lucide-react';
import './index.css';
import * as api from './api';
import MessageSender from './MessageSender';
import AuthScreen from './auth/AuthScreen';
import UserManagement from './UserManagement';

/* ─── constants ─────────────────────────────────────────────────────── */
const SYSTEM_KEYS = new Set([
  'name','contact','region','company','contract_car','contract_date','contract_months',
  'expiry_date','capital','product_type','supplies_work','insurance_active',
  'dealer_info','is_prospect','is_contracted','anniversary','memo','sent_quotes',
]);

/* ─── helpers ────────────────────────────────────────────────────────── */

const renderProspectBadge = (v) => {
  if (!v || v <= 0) return <span className="badge badge-no">일반</span>;
  const level = Number(v);
  const colors = {
    1: '#fcd34d',
    2: '#fbbf24',
    3: '#f59e0b',
    4: '#ea580c',
    5: '#dc2626'
  };
  const color = colors[level] || 'var(--warn)';
  return (
    <span className="badge" style={{ backgroundColor: `${color}20`, color: color, border: `1px solid ${color}40`, display: 'inline-flex', alignItems: 'center' }}>
      <div style={{display:'flex', gap:'1px', marginRight:'4px'}}>
        {[...Array(level)].map((_, i) => <Star key={i} size={10} fill={color} stroke={color} />)}
      </div>
      {level}단계
    </span>
  );
};

const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d);
  return `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')} ${String(dt.getHours()).padStart(2,'0')}:${String(dt.getMinutes()).padStart(2,'0')}`;
};

function computeExpiry(dateStr, months) {
  if (!dateStr || !months) return null;
  const d = new Date(dateStr);
  if (isNaN(d)) return null;
  d.setMonth(d.getMonth() + parseInt(months, 10));
  return d.toISOString().split('T')[0];
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  const exp = new Date(dateStr);
  return Math.ceil((exp - now) / 86400000);
}

function getVal(customer, field) {
  if (SYSTEM_KEYS.has(field.name)) return customer[field.name] ?? null;
  return customer.extra?.[field.name] ?? null;
}

/* ─── ExpiryBadge ────────────────────────────────────────────────────── */
function ExpiryBadge({ dateStr }) {
  if (!dateStr) return <span style={{ color:'var(--text-3)' }}>—</span>;
  const days = daysUntil(dateStr);
  if (days === null) return <span style={{ color:'var(--text-2)' }}>{dateStr}</span>;
  if (days < 0)    return <span className="badge badge-expired">만기 {dateStr}</span>;
  if (days <= 30)  return <span className="badge badge-exp-1m">D-{days} · {dateStr}</span>;
  if (days <= 90)  return <span className="badge badge-exp-3m">D-{days} · {dateStr}</span>;
  if (days <= 180) return <span className="badge badge-exp-6m">D-{days} · {dateStr}</span>;
  return <span style={{ color:'var(--text-2)', fontSize:'.82rem' }}>{dateStr}</span>;
}

/* ─── CustomerForm ───────────────────────────────────────────────────── */
function CustomerForm({ formType, fields, initial, onSave, onClose }) {
  const visibleFields = useMemo(() => {
    return fields.filter(fd => fd.target_type === 'common' || fd.target_type === formType);
  }, [fields, formType]);

  const [form, setForm] = useState(() => {
    const f = {};
    visibleFields.forEach(fd => {
      const v = initial ? getVal(initial, fd) : null;
      if (fd.field_type === 'boolean') f[fd.name] = v ?? false;
      else if (fd.field_type === 'image_gallery') f[fd.name] = v ?? [];
      else if (fd.field_type === 'number') f[fd.name] = v ?? '';
      else f[fd.name] = v ?? '';
    });
    if (!initial) {
      
      if (formType === 'contracted') f.is_contracted = true;
    }
    return f;
  });
  const [saving, setSaving] = useState(false);
  const [initialConsultation, setInitialConsultation] = useState('');

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  // Live expiry preview
  const previewExpiry = computeExpiry(form['contract_date'], form['contract_months']);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const sysData = {}, extra = {};
      visibleFields.forEach(fd => {
        if (fd.name === 'expiry_date') return; // computed by backend
        let v = form[fd.name];
        if (v === '' || v === undefined) v = null;
        if (fd.field_type === 'number' && v !== null) v = Number(v);
        if (fd.name === 'contract_months' && v !== null) v = parseInt(v, 10) || null;
        if (SYSTEM_KEYS.has(fd.name)) sysData[fd.name] = v;
        else extra[fd.name] = v;
      });
      if (!initial && formType === 'prospect' && initialConsultation.trim()) {
        sysData.initial_consultation = initialConsultation.trim();
      }
      await onSave({ ...sysData, extra });
    } catch (err) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="modal-body">
        {visibleFields.map(fd => {
          // ── Computed field: expiry_date ──────────────────────────────
          if (fd.name === 'expiry_date') {
            return (
              <div className="form-row" key={fd.id}>
                <label className="form-label" style={{ display:'flex', alignItems:'center', gap:6 }}>
                  <Calendar size={13}/> {fd.label} <span style={{ color:'var(--text-3)', fontWeight:400 }}>(자동 계산)</span>
                </label>
                <div className={`computed-field ${previewExpiry ? '' : 'empty'}`}>
                  {previewExpiry || '계약일과 개월수를 입력하면 자동 계산됩니다'}
                </div>
              </div>
            );
          }

          // ── Skip is_contracted to render it alongside is_prospect ───
          if (fd.name === 'is_contracted') return null;

          // ── Boolean toggle ───────────────────────────────────────────
          if (fd.field_type === 'boolean') {
            if (fd.name === 'is_prospect') {
              const val = Number(form[fd.name] || 0);
              return (
                <div className="form-row" key={fd.id}>
                  <label style={{display:'block', marginBottom:'8px', fontWeight:600}}>가망고객 중요도 (1~5단계)</label>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    {[1,2,3,4,5].map(lvl => (
                      <button
                        key={lvl}
                        type="button"
                        onClick={(e) => {
                           e.preventDefault();
                           set(fd.name, val === lvl ? 0 : lvl);
                        }}
                        style={{
                          background: val >= lvl ? 'var(--warn-bg)' : 'transparent',
                          border: val >= lvl ? '1px solid var(--warn)' : '1px solid var(--border)',
                          color: val >= lvl ? 'var(--warn)' : 'var(--text-3)',
                          padding: '0.4rem 0.8rem',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.85rem'
                        }}
                      >
                        <Star size={14} fill={val >= lvl ? 'var(--warn)' : 'none'} /> {lvl}단계
                      </button>
                    ))}
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginTop: '6px' }}>* 버튼을 한 번 더 누르면 선택이 취소(일반고객)됩니다.</p>
                </div>
              );
            }

            return (
              <div className="form-row" key={fd.id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', background:'var(--bg-input)', padding:'0.7rem 0.95rem', borderRadius:'var(--radius-md)', border:'1px solid var(--border)' }}>
                <label className="form-label" style={{ marginBottom:0 }}>{fd.label}</label>
                <label className="toggle">
                  <input type="checkbox" checked={!!form[fd.name]}
                    onChange={e => set(fd.name, e.target.checked)} />
                  <span className="track" />
                </label>
              </div>
            );
          }

          // ── Select (dropdown) ────────────────────────────────────────
          if (fd.field_type === 'select') {
            return (
              <div className="form-row" key={fd.id}>
                <label className="form-label">{fd.label}</label>
                <select className="form-select" value={form[fd.name] || ''}
                  onChange={e => set(fd.name, e.target.value)}>
                  <option value="">— 선택 —</option>
                  {fd.options?.map(o => (
                    <option key={o} value={o}>
                      {fd.name === 'contract_months' ? `${o}개월` : o}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          // ── Textarea ─────────────────────────────────────────────────
          if (fd.field_type === 'textarea') {
            return (
              <div className="form-row" key={fd.id}>
                <label className="form-label">{fd.label}</label>
                <textarea className="form-textarea" rows={3}
                  placeholder={fd.label}
                  value={form[fd.name] || ''}
                  onChange={e => set(fd.name, e.target.value)} />
              </div>
            );
          }
          // ── Image Gallery (Sent Quotes) ──
          if (fd.field_type === 'image_gallery') {
            const urls = form[fd.name] || [];
            return (
              <div className="form-row" key={fd.id}>
                <label className="form-label">{fd.label}</label>
                <div style={{ display:'flex', flexWrap:'wrap', gap:'1rem', marginBottom:'0.5rem' }}>
                  {urls.map((url, idx) => (
                    <div key={idx} style={{ position:'relative' }}>
                      <img src={`${api.BASE_URL}${url}`} alt="첨부" style={{ width:80, height:80, objectFit:'cover', borderRadius:6, border:'1px solid var(--border)' }} />
                      <button type="button" className="btn btn-danger btn-icon" style={{ position:'absolute', top:-5, right:-5, width:20, height:20, padding:0, minHeight:20 }} onClick={() => set(fd.name, urls.filter((_, i) => i !== idx))}><X size={12}/></button>
                    </div>
                  ))}
                  <label style={{ width:80, height:80, border:'1px dashed var(--border)', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', color:'var(--text-3)' }}>
                    <Plus size={24} />
                    <input type="file" accept="image/*" multiple style={{ display:'none' }} onChange={async (e) => {
                      const files = Array.from(e.target.files);
                      if (!files.length) return;
                      const newUrls = [...urls];
                      for (const file of files) {
                        const formData = new FormData();
                        formData.append('file', file);
                        try {
                          const res = await fetch(`${api.BASE_URL}/api/upload`, { method: 'POST', body: formData });
                          const data = await res.json();
                          newUrls.push(data.url);
                        } catch (err) {
                          alert('이미지 업로드에 실패했습니다.');
                        }
                      }
                      set(fd.name, newUrls);
                    }} />
                  </label>
                </div>
              </div>
            );
          }



          // ── Image Upload ─────────────────────────────────────────────
          if (fd.field_type === 'image') {
            return (
              <div className="form-row" key={fd.id}>
                <label className="form-label">{fd.label}</label>
                {form[fd.name] ? (
                  <div style={{ display:'flex', alignItems:'center', gap:'1rem' }}>
                    <img src={`${api.BASE_URL}${form[fd.name]}`} alt="첨부" style={{ width:80, height:80, objectFit:'cover', borderRadius:6, border:'1px solid var(--border)' }} />
                    <button type="button" className="btn btn-ghost" style={{ padding:'0.4rem 0.8rem', fontSize:'.85rem' }} onClick={() => set(fd.name, null)}>삭제</button>
                  </div>
                ) : (
                  <input type="file" accept="image/*" className="form-input" style={{ padding:'.4rem' }} onChange={async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;
                    const formData = new FormData();
                    formData.append('file', file);
                    try {
                      const res = await fetch(`${api.BASE_URL}/api/upload`, {
                        method: 'POST', body: formData
                      });
                      const data = await res.json();
                      set(fd.name, data.url);
                    } catch (err) {
                      alert('이미지 업로드에 실패했습니다.');
                    }
                  }} />
                )}
              </div>
            );
          }

          // ── Default: text / number / date ────────────────────────────
          return (
            <div className="form-row" key={fd.id}>
              <label className="form-label">
                {fd.label}
                {fd.name === 'name' && <span style={{ color:'var(--danger)', marginLeft:2 }}>*</span>}
              </label>
              <input className="form-input"
                type={fd.field_type === 'number' ? 'number' : fd.field_type === 'date' ? 'date' : 'text'}
                placeholder={fd.field_type === 'date' ? '' : fd.label}
                value={form[fd.name] ?? ''}
                onClick={e => { if (fd.field_type === 'date' && e.target.showPicker) e.target.showPicker(); }}
                onChange={e => set(fd.name, e.target.value)}
                required={fd.name === 'name'} />
            </div>
          );
        })}
      </div>

      {!initial && formType === 'prospect' && (
        <div className="modal-body" style={{ marginTop: 0, paddingTop: 0 }}>
          <div className="form-row">
            <label className="form-label">초기 상담 내역 (옵션)</label>
            <textarea className="form-textarea" rows={4} placeholder="첫 상담 내용을 입력하세요 (날짜별 내역에 기록됩니다)"
              value={initialConsultation} onChange={e => setInitialConsultation(e.target.value)} />
          </div>
        </div>
      )}

      <div className="modal-ft">
        <button type="button" className="btn btn-ghost" onClick={onClose}>취소</button>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? '저장 중…' : '✓ 저장하기'}
        </button>
      </div>
    </form>
  );
}

/* ─── Dashboard ──────────────────────────────────────────────────────── */
function Dashboard({ activeFields }) {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch]       = useState('');
  const [filter, setFilter]       = useState('all');
  const [loading, setLoading]     = useState(false);
  const [selected, setSelected]   = useState(null);
  const [modalMode, setModalMode] = useState(null);
  const [noteText, setNoteText]   = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'id', dir: 'desc' });

  const load = useCallback(async () => {
    setLoading(true);
    try { setCustomers(await api.getCustomers('')); }
    catch { /* backend not ready */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Sync drawer with latest data
  useEffect(() => {
    if (selected) {
      const updated = customers.find(c => c.id === selected.id);
      if (updated) setSelected(updated);
    }
  }, [customers]);

  // ── Stats ──────────────────────────────────────────────────────────
  const now = new Date(); now.setHours(0,0,0,0);
  const add = (d, m) => { const x = new Date(d); x.setMonth(x.getMonth()+m); return x; };

  const stats = useMemo(() => {
    const prospects   = customers.filter(c => c.is_prospect).length;
    const contracted  = customers.filter(c => !c.is_prospect).length;
    const expiry1m    = customers.filter(c => {
      if (!c.expiry_date) return false;
      const e = new Date(c.expiry_date);
      return e >= now && e <= add(now,1);
    }).length;
    const expiry3m    = customers.filter(c => {
      if (!c.expiry_date) return false;
      const e = new Date(c.expiry_date);
      return e >= now && e <= add(now,3);
    }).length;
    return { total: customers.length, prospects, contracted, expiry1m, expiry3m };
  }, [customers]);

  // ── Filtering ─────────────────────────────────────────────────────
  const displayCustomers = useMemo(() => {
    let list = customers;

    // Text search (client-side)
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c =>
        c.name?.toLowerCase().includes(q) ||
        c.company?.toLowerCase().includes(q) ||
        c.contract_car?.toLowerCase().includes(q) ||
        c.capital?.toLowerCase().includes(q) ||
        c.dealer_info?.toLowerCase().includes(q) ||
        c.memo?.toLowerCase().includes(q)
      );
    }

    // Tab filter
    if (filter === 'contracted') {
      list = list.filter(c => c.is_contracted || (!c.is_prospect));
    } else if (filter === 'prospect') {
      list = list.filter(c => c.is_prospect);
    } else if (filter === 'expiry_1m') {
      const limit = add(now,1);
      list = list.filter(c => {
        if (!c.expiry_date) return false;
        const e = new Date(c.expiry_date);
        return e >= now && e <= limit;
      });
    } else if (filter === 'expiry_3m') {
      const limit = add(now,3);
      list = list.filter(c => {
        if (!c.expiry_date) return false;
        const e = new Date(c.expiry_date);
        return e >= now && e <= limit;
      });
    } else if (filter === 'expiry_6m') {
      const limit = add(now,6);
      list = list.filter(c => {
        if (!c.expiry_date) return false;
        const e = new Date(c.expiry_date);
        return e >= now && e <= limit;
      });
    }

    // Sort
    list.sort((a, b) => {
      let va = getVal(a, { name: sortConfig.key });
      let vb = getVal(b, { name: sortConfig.key });
      if (va == null) va = '';
      if (vb == null) vb = '';
      if (va < vb) return sortConfig.dir === 'asc' ? -1 : 1;
      if (va > vb) return sortConfig.dir === 'asc' ? 1 : -1;
      return 0;
    });

    return list;
  }, [customers, search, filter, sortConfig]);

  const handleSort = (key) => {
    setSortConfig(prev => {
      if (prev.key === key) return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' };
      return { key, dir: 'asc' };
    });
  };

  const openCreate = () => setModalMode('create');
  const openEdit   = (c, e) => { e.stopPropagation(); setModalMode('edit'); setSelected(c); };

  const handleSave = async (data) => {
    if (modalMode && modalMode.startsWith('create')) {
      await api.createCustomer(data);
    } else if (modalMode === 'convert_to_contracted') {
      data.is_prospect = 0;
      data.is_contracted = true;
      await api.updateCustomer(selected.id, data);
    } else {
      await api.updateCustomer(selected.id, data);
    }
    setModalMode(null);
    load();
  };

  const handleDelete = async (c, e) => {
    e.stopPropagation();
    if (!confirm(`'${c.name}' 고객을 삭제하시겠습니까?`)) return;
    await api.deleteCustomer(c.id);
    if (selected?.id === c.id) setSelected(null);
    load();
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim() || !selected) return;
    await api.addConsultation(selected.id, noteText.trim());
    setNoteText('');
    load();
  };

  const handleDelNote = async (id) => {
    if (!confirm('이 상담 기록을 삭제할까요?')) return;
    await api.deleteConsultation(id);
    load();
  };

  const FILTERS = [
    { id:'all',        label:'전체',           cls:''           },
    { id:'contracted', label:'기고객',         cls:'ft-contracted', icon:<CheckCircle size={12}/> },
    { id:'prospect',   label:'상담고객',       cls:'ft-prospect', icon:<Star size={12}/> },
    { id:'expiry_1m',  label:'만기 1개월 이내', cls:'ft-expiry-red', icon:<Clock size={12}/> },
    { id:'expiry_3m',  label:'만기 3개월 이내', cls:'ft-expiry-ora', icon:<Clock size={12}/> },
    { id:'expiry_6m',  label:'만기 6개월 이내', cls:'ft-expiry-yel', icon:<Clock size={12}/> },
  ];

  return (
    <div>
      {/* Stat cards */}
      <div className="stat-grid">
        <div className="stat-card">
          <span className="stat-label">전체 고객</span>
          <span className="stat-value">{stats.total}</span>
          <span className="stat-sub">등록된 고객 수</span>
        </div>
        <div className="stat-card" style={{ borderColor: stats.contracted ? 'rgba(52,211,153,.3)':'' }}>
          <span className="stat-label" style={{ color:'#6ee7b7' }}>✓ 기고객</span>
          <span className="stat-value">{stats.contracted}</span>
          <span className="stat-sub">현재 계약 고객</span>
        </div>
        <div className="stat-card" style={{ borderColor: stats.prospects ? 'rgba(245,158,11,.3)':'' }}>
          <span className="stat-label" style={{ color:'#fcd34d' }}>★ 상담고객</span>
          <span className="stat-value">{stats.prospects}</span>
          <span className="stat-sub">잠재 계약 대상</span>
        </div>
        <div className="stat-card" style={{ borderColor: stats.expiry1m ? 'rgba(244,63,94,.35)':'' }}>
          <span className="stat-label" style={{ color:'#fca5a5' }}>🔴 만기 1개월</span>
          <span className="stat-value">{stats.expiry1m}</span>
          <span className="stat-sub">긴급 연락 필요</span>
        </div>
        <div className="stat-card" style={{ borderColor: stats.expiry3m ? 'rgba(251,146,60,.3)':'' }}>
          <span className="stat-label" style={{ color:'#fdba74' }}>🟠 만기 3개월</span>
          <span className="stat-value">{stats.expiry3m}</span>
          <span className="stat-sub">선제 관리 대상</span>
        </div>
      </div>

      {/* Page header */}
      <div className="page-hd">
        <div>
          <h1>고객 데이터베이스</h1>
          <p>고객 정보를 등록하고 실시간 상담 내역을 기록합니다.</p>
        </div>
        <div style={{ display:'flex', gap:'0.5rem' }}>
          <button className="btn btn-primary" onClick={() => setModalMode('create_contracted')}><Plus size={16}/> 기고객 등록</button>
          <button className="btn btn-secondary" onClick={() => setModalMode('create_prospect')}><Plus size={16}/> 상담고객 등록</button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="filter-tabs">
        {FILTERS.map(f => (
          <button key={f.id}
            className={`filter-tab ${filter === f.id ? (f.cls || 'ft-active') : ''}`}
            onClick={() => setFilter(f.id)}>
            {f.icon}{f.label}
            {f.id === 'all' && <span style={{ marginLeft:4, fontWeight:400, color:'var(--text-3)' }}>{customers.length}</span>}
            {f.id === 'contracted' && <span style={{ marginLeft:4, fontWeight:400 }}>{stats.contracted}</span>}
            {f.id === 'prospect'  && <span style={{ marginLeft:4, fontWeight:400 }}>{stats.prospects}</span>}
            {f.id === 'expiry_1m' && <span style={{ marginLeft:4, fontWeight:400 }}>{stats.expiry1m}</span>}
            {f.id === 'expiry_3m' && <span style={{ marginLeft:4, fontWeight:400 }}>{stats.expiry3m}</span>}
          </button>
        ))}
      </div>

      {/* Search & refresh */}
      <div className="ctrl-bar">
        <div className="search-wrap">
          <Search />
          <input className="search-input"
            placeholder="이름, 업체명, 차종, 캐피탈, 딜러 등으로 검색…"
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={14}/> 새로고침</button>
        {search && (
          <button className="btn btn-ghost btn-sm" onClick={() => setSearch('')}><X size={13}/> 검색 초기화</button>
        )}
      </div>

      {/* Table */}
      <div className="card" style={{ padding:0, overflow:'hidden' }}>
        {displayCustomers.length === 0 && !loading ? (
          <div className="empty">
            <Users />
            <h3>
              {filter !== 'all'
                ? `해당 조건의 고객이 없습니다.`
                : search ? '검색 결과가 없습니다.'
                : '등록된 고객이 없습니다.'}
            </h3>
            {filter === 'all' && !search && (
              <div style={{ display:'flex', gap:'0.5rem', justifyContent:'center' }}>
                <button className="btn btn-primary" onClick={() => setModalMode('create_contracted')}><Plus size={14}/> 첫 기고객 등록</button>
                <button className="btn btn-secondary" onClick={() => setModalMode('create_prospect')}><Plus size={14}/> 첫 상담고객 등록</button>
              </div>
            )}
          </div>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  {activeFields.map(f => {
                    const sortable = ['name', 'company', 'contract_date', 'expiry_date'].includes(f.name);
                    return (
                      <th key={f.id} 
                          onClick={() => sortable && handleSort(f.name)}
                          style={{ cursor: sortable ? 'pointer' : 'default', userSelect: 'none' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          {f.label}
                          {sortable && (
                            <span style={{ color: sortConfig.key === f.name ? 'var(--primary)' : 'var(--border)', fontSize: '10px', display: 'flex', flexDirection: 'column', lineHeight: '8px' }}>
                              <ChevronUp size={12} color={sortConfig.key === f.name && sortConfig.dir === 'asc' ? 'var(--primary)' : 'var(--text-3)'} style={{ marginBottom: '-4px' }} />
                              <ChevronDown size={12} color={sortConfig.key === f.name && sortConfig.dir === 'desc' ? 'var(--primary)' : 'var(--text-3)'} />
                            </span>
                          )}
                        </div>
                      </th>
                    );
                  })}
                  <th style={{ textAlign:'center' }}>관리</th>
                </tr>
              </thead>
              <tbody>
                {displayCustomers.map(c => (
                  <tr key={c.id} onClick={() => { setSelected(c); setModalMode(null); }}>
                    {activeFields.map(f => {
                      const v = getVal(c, f);
                      // Special renders
                      if (f.name === 'expiry_date') return <td key={f.id}><ExpiryBadge dateStr={v} /></td>;
                      if (f.name === 'is_prospect') return (
                        <td key={f.id}>
                          {renderProspectBadge(v)}
                        </td>
                      );
                      if (f.name === 'is_contracted') return (
                        <td key={f.id}>
                          {v ? <span className="badge badge-ok"><CheckCircle size={10}/> 기계약</span>
                             : <span className="badge badge-no">미계약</span>}
                        </td>
                      );
                      if (f.field_type === 'boolean') return (
                        <td key={f.id}>
                          <span className={v ? 'badge badge-ok' : 'badge badge-no'}>
                            {f.name === 'insurance_active' ? (v ? '가입' : '미가입') : (v ? 'Y' : 'N')}
                          </span>
                        </td>
                      );
                      if (f.name === 'contract_months' && v) return <td key={f.id}>{v}개월</td>;
                      return <td key={f.id} title={v ?? ''}>{v != null ? String(v) : '—'}</td>;
                    })}
                    <td onClick={e => e.stopPropagation()} style={{ textAlign:'center' }}>
                      <div style={{ display:'flex', gap:'.4rem', justifyContent:'center' }}>
                        <button className="btn btn-ghost btn-sm" onClick={e => openEdit(c, e)}>수정</button>
                        <button className="btn btn-danger btn-sm" onClick={e => handleDelete(c, e)}><Trash2 size={12}/></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Customer Detail Drawer */}
      {selected && modalMode === null && (
        <>
          <div className="drawer-overlay" onClick={() => setSelected(null)} />
          <aside className="drawer">
            <div className="drawer-hd">
              <div>
                <h2 style={{ display:'flex', alignItems:'center', gap:8 }}>
                  {selected.name}
                  {selected.is_prospect > 0 && renderProspectBadge(selected.is_prospect)}
                </h2>
                <p style={{ fontSize:'.78rem', color:'var(--text-3)', marginTop:2 }}>고객 #{selected.id}</p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {!selected.is_contracted && (
                    <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); setModalMode('convert_to_contracted'); }} style={{ padding: '0.25rem 0.75rem', height: '32px' }}>
                      <CheckCircle size={14} style={{ marginRight: 4 }}/> 기고객 전환
                    </button>
                  )}
                  <button className="btn btn-secondary btn-sm" onClick={(e) => openEdit(selected, e)} style={{ padding: '0.25rem 0.75rem', height: '32px' }}><Edit2 size={14}/> 수정</button>
                  <button className="btn btn-danger btn-sm" onClick={(e) => handleDelete(selected, e)} style={{ padding: '0.25rem 0.75rem', height: '32px', background: 'var(--danger)', color: 'white', border: 'none' }}><Trash2 size={14}/> 삭제</button>
                <button className="btn btn-ghost btn-icon" onClick={() => setSelected(null)}><X size={18}/></button>
              </div>
            </div>
            <div className="drawer-body">
              <div className="info-grid">
                  {activeFields.filter(f => f.target_type === 'common' || f.target_type === (!selected.is_contracted ? 'prospect' : 'contracted')).map(f => {
                    const v = getVal(selected, f);
                    return (
                      <div className="info-row" key={f.id}>
                        <span className="lbl">{f.label}</span>
                        <span className="val">
                          {f.name === 'expiry_date' ? <ExpiryBadge dateStr={v} />
                           : f.field_type === 'image' ? (v ? <a href={`${api.BASE_URL}${v}`} target="_blank" rel="noreferrer"><img src={`${api.BASE_URL}${v}`} alt="첨부" style={{ maxHeight: 150, borderRadius: 8, border:'1px solid var(--border)', marginTop: 4, display: 'block' }} /></a> : <span style={{color:'var(--text-3)'}}>미첨부</span>)
                           : f.field_type === 'image_gallery' ? (
                               v && v.length > 0 ? (
                                 <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: 4 }}>
                                   {v.map((url, i) => (
                                     <a key={i} href={`${api.BASE_URL}${url}`} target="_blank" rel="noreferrer">
                                       <img src={`${api.BASE_URL}${url}`} alt="견적" style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 6, border: '1px solid var(--border)' }} />
                                     </a>
                                   ))}
                                 </div>
                               ) : <span style={{color:'var(--text-3)'}}>미첨부</span>
                           )
                           : f.name === 'is_prospect' ? renderProspectBadge(v)
                           : f.name === 'is_contracted' ? (v ? <span className="badge badge-ok"><CheckCircle size={10}/> 기계약고객</span> : <span className="badge badge-no">미계약고객</span>)
                           : f.field_type === 'boolean' ? <span className={v ? 'badge badge-ok' : 'badge badge-no'}>{f.name === 'insurance_active' ? (v ? '가입' : '미가입') : (v ? 'Y' : 'N')}</span>
                           : f.name === 'contract_months' && v ? `${v}개월`
                           : v != null ? String(v) : '—'}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <h3 style={{ fontSize:'.9rem', fontWeight:600, marginBottom:'1rem' }}>📋 상담 일지</h3>
              <form className="consult-form" onSubmit={handleAddNote}>
                <input className="form-input" placeholder="새 상담 내용 입력 후 전송…"
                  value={noteText} onChange={e => setNoteText(e.target.value)} required />
                <button type="submit" className="btn btn-primary btn-icon"><Send size={16}/></button>
              </form>

              {(selected.consultations || []).length === 0
                ? <p style={{ color:'var(--text-3)', fontSize:'.82rem', textAlign:'center', padding:'2rem 0' }}>등록된 상담 기록이 없습니다.</p>
                : (
                  <div className="timeline">
                    {[...(selected.consultations||[])].sort((a,b)=>b.id-a.id).map(log => (
                      <div className="tl-item" key={log.id}>
                        <p className="tl-date">{fmtDate(log.created_at)}</p>
                        <div className="tl-note">
                          <span>{log.notes}</span>
                          <button style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', flexShrink:0 }}
                            onClick={() => handleDelNote(log.id)}><Trash2 size={12}/></button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </aside>
        </>
      )}

      {/* Create / Edit modal */}
      {modalMode && (
        <div className="overlay" onClick={() => setModalMode(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-hd">
              <h2>
                  {modalMode === 'create_contracted' ? '기고객 등록' :
                   modalMode === 'create_prospect' ? '상담고객 등록' :
                   modalMode === 'convert_to_contracted' ? '기고객으로 전환' : '고객 정보 수정'}
                </h2>
              <button className="btn btn-ghost btn-icon" onClick={() => setModalMode(null)}><X size={16}/></button>
            </div>
            <CustomerForm
              formType={
                  modalMode === 'create_contracted' ? 'contracted' :
                  modalMode === 'create_prospect' ? 'prospect' :
                  modalMode === 'convert_to_contracted' ? 'contracted' :
                  (!selected?.is_contracted ? 'prospect' : 'contracted')
                }
              fields={activeFields}
              initial={(modalMode === 'edit' || modalMode === 'convert_to_contracted') ? selected : null}
              onSave={handleSave}
              onClose={() => setModalMode(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── ExcelImport ────────────────────────────────────────────────────── */
function ExcelImport({ activeFields }) {
  const [step, setStep]       = useState(1);
  const [file, setFile]       = useState(null);
  const [headers, setHeaders] = useState([]);
  const [preview, setPreview] = useState([]);
  const [mapping, setMapping] = useState({});
  const [result, setResult]   = useState(null);
  const [drag, setDrag]       = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const fileRef = useRef();

  const processFile = async (f) => {
    setError(''); setLoading(true);
    try {
      const data = await api.parseExcel(f);
      setFile(f);
      setHeaders(data.headers);
      setPreview(data.preview);
      const m = {};
      activeFields.forEach(fd => {
        const match = data.headers.find(h =>
          h.toLowerCase() === fd.label.toLowerCase() ||
          h.toLowerCase() === fd.name.toLowerCase()
        );
        m[fd.name] = match || '';
      });
      setMapping(m);
      setStep(2);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) processFile(f);
  };

  const handleRun = async () => {
    setError(''); setLoading(true);
    try {
      const mappingList = Object.entries(mapping)
        .filter(([,v]) => v)
        .map(([db_field, excel_col]) => ({ db_field, excel_col }));
      const res = await api.importExcel(file, mappingList);
      setResult(res);
      setStep(3);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const reset = () => { setStep(1); setFile(null); setResult(null); setError(''); };

  return (
    <div>
      <div className="page-hd">
        <div>
          <h1>엑셀 일괄 업로드</h1>
          <p>기존 고객 엑셀 파일을 업로드하고 스마트 컬럼 매핑으로 한 번에 등록합니다.</p>
        </div>
        {step > 1 && <button className="btn btn-ghost" onClick={reset}><RefreshCw size={14}/> 다시 시작</button>}
      </div>

      {error && <div className="alert alert-err"><AlertCircle size={16}/>{error}</div>}

      {step === 1 && (
        <div className="card">
          <div
            className={`upload-zone ${drag ? 'drag' : ''}`}
            onDragEnter={e => { e.preventDefault(); setDrag(true); }}
            onDragOver={e => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current.click()}
          >
            <UploadCloud size={52} style={{ color: loading ? 'var(--primary)' : 'var(--text-3)' }} />
            <h3>{loading ? '파일 분석 중…' : '엑셀 또는 CSV 파일을 드래그 앤 드롭'}</h3>
            <p>또는 클릭하여 파일 탐색기에서 선택하세요 (.xlsx .xls .csv)</p>
            <button className="btn btn-ghost btn-sm" style={{ pointerEvents:'none' }}>파일 선택</button>
            <input ref={fileRef} type="file" style={{ display:'none' }}
              accept=".xlsx,.xls,.csv"
              onChange={e => { if(e.target.files[0]) processFile(e.target.files[0]); }} />
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1.5rem', gap:'1rem', flexWrap:'wrap' }}>
            <div>
              <h2 style={{ fontFamily:'var(--font-display)', fontSize:'1.1rem', fontWeight:700 }}>스마트 컬럼 매핑</h2>
              <p style={{ color:'var(--text-2)', fontSize:'.83rem', marginTop:2 }}>엑셀 열과 DB 항목을 연결해 주세요.</p>
            </div>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? '가져오는 중…' : '등록 실행'} <ChevronRight size={16}/>
            </button>
          </div>
          {activeFields.filter(f => f.name !== 'expiry_date').map(fd => (
            <div className="mapper-row" key={fd.id}>
              <div className="mapper-label">
                {fd.label}
                {fd.name === 'name' && <span style={{ color:'var(--danger)' }}>*</span>}
              </div>
              <div className="mapper-arrow"><ChevronRight size={18}/></div>
              <select className="form-select"
                value={mapping[fd.name] || ''}
                onChange={e => setMapping(p => ({ ...p, [fd.name]: e.target.value }))}
                style={{ borderColor: mapping[fd.name] ? 'var(--success)' : '' }}>
                <option value="">— 매핑 안 함 —</option>
                {headers.map(h => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>
          ))}
          {preview.length > 0 && (
            <div style={{ marginTop:'2rem' }}>
              <p style={{ fontSize:'.8rem', color:'var(--text-2)', marginBottom:'.75rem' }}>📋 미리보기 (상위 5행)</p>
              <div className="tbl-wrap">
                <table>
                  <thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead>
                  <tbody>{preview.map((r,i) => <tr key={i}>{headers.map(h => <td key={h}>{String(r[h] ?? '')}</td>)}</tr>)}</tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {step === 3 && result && (
        <div className="card">
          <div className="result-card">
            <div className="result-icon"><CheckCircle size={36}/></div>
            <h2 style={{ fontFamily:'var(--font-display)', fontSize:'1.5rem' }}>업로드 완료!</h2>
            <p style={{ color:'var(--text-2)' }}>
              <strong style={{ color:'#fff', fontSize:'1.2rem' }}>{result.success}명</strong>의 고객이 성공적으로 등록되었습니다.
            </p>
            {result.skipped > 0 && <p style={{ color:'var(--text-3)', fontSize:'.85rem' }}>건너뜀: {result.skipped}건</p>}
            {result.errors?.length > 0 && (
              <div style={{ maxWidth:480, textAlign:'left', background:'rgba(244,63,94,.07)', border:'1px solid rgba(244,63,94,.2)', borderRadius:'var(--radius-md)', padding:'1rem', fontSize:'.8rem', color:'#fda4af' }}>
                {result.errors.map((e,i) => <p key={i} style={{ marginBottom:2 }}>{e}</p>)}
              </div>
            )}
            <button className="btn btn-primary" onClick={reset}><RefreshCw size={14}/> 새 파일 업로드</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── FieldSettings ──────────────────────────────────────────────────── */
function FieldSettings({ fields, onRefresh }) {
  const [settingsTab, setSettingsTab] = useState('contracted');
  const [adding, setAdding]         = useState(false);
  const [form, setForm]             = useState({ name:'', label:'', field_type:'text', options:'' });
  
  const activeTabFields = fields.filter(f => f.target_type === settingsTab || f.target_type === 'common');

  const [editingLabel, setEditingLabel] = useState(null); // { id, label }
  const [error, setError]           = useState('');
  const [success, setSuccess]       = useState('');

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleAdd = async (e) => {
    e.preventDefault(); setError(''); setSuccess('');
    try {
      const body = {
        name: form.name.trim().toLowerCase(),
        label: form.label.trim(),
        field_type: form.field_type,
        options: form.field_type === 'select'
          ? form.options.split(',').map(s=>s.trim()).filter(Boolean)
          : null,
        sort_order: Math.max(0, ...activeTabFields.map(f=>f.sort_order)) + 1,
        target_type: settingsTab,
      };
      await api.createField(body);
      setSuccess(`'${body.label}' 항목이 추가되었습니다.`);
      setForm({ name:'', label:'', field_type:'text', options:'' });
      setAdding(false);
      onRefresh();
    } catch(e) { setError(e.message); }
  };

  const toggle = async (f) => {
    await api.updateField(f.id, { is_active: !f.is_active });
    onRefresh();
  };

  const moveOrder = async (idx, dir) => {
    const target = activeTabFields[idx + (dir === 'up' ? -1 : 1)];
    if (!target) return;
    const a = activeTabFields[idx], b = target;
    await Promise.all([
      api.updateField(a.id, { sort_order: b.sort_order }),
      api.updateField(b.id, { sort_order: a.sort_order }),
    ]);
    onRefresh();
  };

  const saveLabel = async () => {
    if (!editingLabel || !editingLabel.label.trim()) return;
    try {
      await api.updateField(editingLabel.id, { label: editingLabel.label.trim() });
      setEditingLabel(null);
      onRefresh();
    } catch(e) { alert(e.message); }
  };

  const handleDelete = async (f) => {
    if (!confirm(`'${f.label}' 항목을 삭제하면 모든 고객의 해당 데이터가 사라집니다.\n계속하시겠습니까?`)) return;
    try { await api.deleteField(f.id); onRefresh(); }
    catch(e) { alert(e.message); }
  };

  return (
    <div>
      <div className="page-hd">
        <div>
          <h1>데이터베이스 항목 설정</h1>
          <p>고객 관리에 사용할 항목을 추가·삭제하고 순서·이름·표시 여부를 설정합니다.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setAdding(!adding)}>
          <Plus size={16}/> {adding ? '닫기' : '항목 추가'}
        </button>
      </div>
      
      <div style={{ display:'flex', borderBottom:'1px solid var(--border)', marginBottom:'1.5rem', gap:'1rem' }}>
        <button 
          style={{ padding:'0.5rem 1rem', background:'none', border:'none', borderBottom: settingsTab === 'contracted' ? '2px solid var(--primary)' : '2px solid transparent', color: settingsTab === 'contracted' ? 'var(--text)' : 'var(--text-2)', cursor:'pointer', fontWeight: settingsTab === 'contracted' ? 600 : 400 }}
          onClick={() => { setSettingsTab('contracted'); setAdding(false); }}>기계약고객 항목</button>
        <button 
          style={{ padding:'0.5rem 1rem', background:'none', border:'none', borderBottom: settingsTab === 'prospect' ? '2px solid var(--primary)' : '2px solid transparent', color: settingsTab === 'prospect' ? 'var(--text)' : 'var(--text-2)', cursor:'pointer', fontWeight: settingsTab === 'prospect' ? 600 : 400 }}
          onClick={() => { setSettingsTab('prospect'); setAdding(false); }}>상담고객 항목</button>
      </div>

      {adding && (
        <div className="card" style={{ animation:'scaleIn .2s ease' }}>
          <h3 style={{ fontFamily:'var(--font-display)', fontSize:'1rem', fontWeight:700, marginBottom:'1.25rem' }}>새 항목 추가</h3>
          {error   && <div className="alert alert-err"><AlertCircle size={14}/>{error}</div>}
          {success && <div className="alert alert-ok"><CheckCircle size={14}/>{success}</div>}
          <form onSubmit={handleAdd}>
            <div className="form-grid-2">
              <div className="form-row">
                <label className="form-label">한글 라벨 <span style={{ color:'var(--danger)' }}>*</span></label>
                <input className="form-input" placeholder="예: 희망 출고일" value={form.label} onChange={e=>set('label',e.target.value)} required />
              </div>
              <div className="form-row">
                <label className="form-label">영문 키 (영소문자·숫자·_ 만) <span style={{ color:'var(--danger)' }}>*</span></label>
                <input className="form-input" placeholder="예: delivery_date" value={form.name} onChange={e=>set('name',e.target.value)} required />
              </div>
            </div>
            <div className="form-grid-2">
              <div className="form-row">
                <label className="form-label">데이터 타입</label>
                <select className="form-select" value={form.field_type} onChange={e=>set('field_type',e.target.value)}>
                  <option value="text">단문 텍스트</option>
                  <option value="number">숫자</option>
                  <option value="select">드롭다운 선택</option>
                  <option value="boolean">여부 토글</option>
                  <option value="date">날짜</option>
                  <option value="textarea">장문 메모</option>
                </select>
              </div>
              {form.field_type === 'select' && (
                <div className="form-row" style={{ animation:'fadeIn .2s ease' }}>
                  <label className="form-label">선택 옵션 (쉼표 구분)</label>
                  <input className="form-input" placeholder="예: 현대, 기아, 르노" value={form.options} onChange={e=>set('options',e.target.value)} />
                </div>
              )}
            </div>
            <div style={{ display:'flex', gap:'.75rem', marginTop:'.5rem' }}>
              <button type="submit" className="btn btn-primary">추가하기</button>
              <button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>취소</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <h3 style={{ fontFamily:'var(--font-display)', fontSize:'1rem', fontWeight:700, marginBottom:'1rem' }}>
          현재 항목 목록 ({activeTabFields.length}개)
        </h3>
        {activeTabFields.map((f, idx) => (
          <div key={f.id} className={`field-card ${f.is_active ? '' : 'dim'}`}>

            {/* Order buttons */}
            <div style={{ display:'flex', flexDirection:'column', gap:1, flexShrink:0 }}>
              <button className="btn btn-icon" style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:'1px' }}
                onClick={() => moveOrder(idx, 'up')} disabled={idx===0}><ChevronUp size={13}/></button>
              <button className="btn btn-icon" style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-3)', padding:'1px' }}
                onClick={() => moveOrder(idx, 'down')} disabled={idx===activeTabFields.length-1}><ChevronDown size={13}/></button>
            </div>

            {/* Meta */}
            <div className="field-meta">
              <div>
                {/* Label — inline edit mode */}
                {editingLabel?.id === f.id ? (
                  <div className="label-edit">
                    <input className="form-input" autoFocus
                      value={editingLabel.label}
                      onChange={e => setEditingLabel(p => ({ ...p, label: e.target.value }))}
                      onKeyDown={e => { if(e.key==='Enter') saveLabel(); if(e.key==='Escape') setEditingLabel(null); }}
                    />
                    <button className="btn btn-primary btn-sm" onClick={saveLabel}>저장</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditingLabel(null)}>취소</button>
                  </div>
                ) : (
                  <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap' }}>
                    <span className="field-label">{f.label}</span>
                    <span className="field-name">{f.name}</span>
                    <span className="field-type-tag">{f.field_type.toUpperCase()}</span>
                    {f.is_system && <span className="badge badge-sys"><Shield size={9}/> 기본</span>}
                  </div>
                )}
                {f.options?.length > 0 && (
                  <p style={{ fontSize:'.72rem', color:'var(--text-3)', marginTop:2 }}>{f.options.join(' / ')}</p>
                )}
              </div>
            </div>

            {/* Actions */}
            {editingLabel?.id !== f.id && (
              <div className="field-actions">
                <button className="btn btn-ghost btn-sm" title="이름 변경"
                  onClick={() => setEditingLabel({ id: f.id, label: f.label })}>
                  <Edit2 size={12}/> 이름
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => toggle(f)}>
                  {f.is_active ? <><EyeOff size={12}/> 숨기기</> : <><Eye size={12}/> 표시</>}
                </button>
                {!f.is_system && (
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(f)}><Trash2 size={12}/></button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── App (root) ─────────────────────────────────────────────────────── */
export default function App() {
  const [tab, setTab]       = useState('dashboard');
  const [fields, setFields] = useState([]);
  const [active, setActive] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [connErr, setConnErr]   = useState('');

  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    setAuthLoading(true);
    try {
      if (sessionStorage.getItem('cmhelper_token')) {
        const u = await api.getAuthMe();
        setUser(u);
      } else {
        setUser(null);
      }
    } catch (err) {
      sessionStorage.removeItem('cmhelper_token');
      setUser(null);
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const loadFields = useCallback(async () => {
    setLoading(true); setConnErr('');
    try {
      const all = await api.getFields(false);
      setFields(all);
      setActive(all.filter(f => f.is_active));
    } catch {
      setConnErr('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (user) {
      loadFields();
    }
  }, [user, loadFields]);

  const LoadingScreen = ({ text }) => (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100vh', gap:'1rem' }}>
      <div style={{ width:48, height:48, background:'linear-gradient(135deg,#6366f1,#8b5cf6)', borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--font-display)', fontWeight:800, fontSize:'1.1rem', color:'#fff', boxShadow:'0 4px 20px rgba(99,102,241,.4)' }}>CM</div>
      <p style={{ color:'var(--text-2)', fontSize:'.9rem' }}>{text}</p>
    </div>
  );

  if (authLoading) return <LoadingScreen text="사용자 확인 중…" />;
  
  if (!user) return <AuthScreen onLoginSuccess={checkAuth} />;

  if (loading) return <LoadingScreen text="서버에 연결하는 중…" />;

  if (connErr) return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', height:'100vh', gap:'1.25rem', padding:'2rem', textAlign:'center' }}>
      <div style={{ background:'rgba(244,63,94,.12)', color:'var(--danger)', padding:'1.25rem', borderRadius:'50%' }}><ServerCrash size={48}/></div>
      <h2 style={{ fontFamily:'var(--font-display)', fontWeight:700 }}>서버 연결 실패</h2>
      <p style={{ color:'var(--text-2)', maxWidth:400, lineHeight:1.6 }}>{connErr}</p>
      <button className="btn btn-primary" onClick={loadFields}><RefreshCw size={14}/> 다시 연결</button>
    </div>
  );

  const TABS = [
    { id:'dashboard', label:'고객 대시보드', icon:<Users size={18}/> },
    { id:'excel',     label:'엑셀 업로드',   icon:<FileSpreadsheet size={18}/> },
    { id:'message',   label:'메시지 발송',   icon:<MessageSquare size={18}/> },
  ];
  if (user?.role === 'OWNER') {
    TABS.push({ id:'settings',  label:'항목 설정',      icon:<Settings size={18}/> });
    TABS.push({ id:'users',     label:'사용자 관리',    icon:<Shield size={18}/> });
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">CM</div>
          <span className="brand-name">CMhelper</span>
          <span className="brand-ver">v1</span>
        </div>
        <nav className="nav">
          {TABS.map(t => (
            <div key={t.id} className={`nav-item ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
              <span className="nav-icon">{t.icon}</span>
              <span className="nav-text">{t.label}</span>
            </div>
          ))}
        </nav>
        <div className="sidebar-foot" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.8rem 1rem', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div className="foot-avatar"><Database size={16} style={{ color:'var(--success)' }}/></div>
            <div className="foot-info">
              <strong>{user.name}</strong>
              <span>{user.role === 'OWNER' ? '최고 관리자' : (user.role === 'ADMIN' ? '관리자' : '일반 사용자')}</span>
            </div>
          </div>
          <button 
            className="btn btn-ghost btn-icon" 
            title="로그아웃" 
            onClick={() => { sessionStorage.removeItem('cmhelper_token'); setUser(null); }}
            style={{ color: 'var(--text-3)' }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="main">
        {tab === 'dashboard' && <Dashboard activeFields={active} />}
        {tab === 'excel'     && <ExcelImport activeFields={active} />}
        {tab === 'message'   && <MessageSender />}
        {tab === 'settings'  && user?.role === 'OWNER' && <FieldSettings fields={fields} onRefresh={loadFields} />}
        {tab === 'users'     && user?.role === 'OWNER' && <UserManagement />}
      </main>
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { Search, Send, UserCheck, RefreshCw, AlertCircle, CheckSquare, Square } from 'lucide-react';
import * as api from './api';

export default function MessageSender() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all'); // 'all', 'contracted', 'prospect', 'expiring_1m'
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [message, setMessage] = useState('{{이름}} 고객님 안녕하세요!\n');
  const [sendResult, setSendResult] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getCustomers('');
      setCustomers(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Derived state for filtering
  const filtered = customers.filter(c => {
    if (filter === 'contracted' && !c.is_contracted) return false;
    if (filter === 'prospect' && !c.is_prospect) return false;
    if (filter === 'expiring_1m') {
      if (!c.expiry_date) return false;
      const days = (new Date(c.expiry_date) - new Date()) / (1000 * 60 * 60 * 24);
      if (days < 0 || days > 30) return false;
    }
    if (search) {
      const q = search.toLowerCase();
      if (!c.name?.toLowerCase().includes(q) &&
          !c.contact?.toLowerCase().includes(q) &&
          !c.contract_car?.toLowerCase().includes(q)) {
        return false;
      }
    }
    return true;
  });

  const toggleAll = () => {
    if (selectedIds.size === filtered.length && filtered.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map(c => c.id)));
    }
  };

  const toggleOne = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleSend = () => {
    if (selectedIds.size === 0) {
      alert("발송할 고객을 1명 이상 선택해주세요.");
      return;
    }
    if (!message.trim()) {
      alert("메시지 내용을 입력해주세요.");
      return;
    }
    
    // Simulate API call for queuing the messages
    console.log("Queueing messages for:", Array.from(selectedIds));
    console.log("Message template:", message);
    
    setSendResult(`${selectedIds.size}명의 고객에게 발송 대기열에 등록되었습니다!\n(현재 UI 테스트 모드입니다. 실제 발송 에이전트는 추후 연동됩니다.)`);
    
    setTimeout(() => {
      setSendResult('');
      setSelectedIds(new Set());
      setMessage('{{이름}} 고객님 안녕하세요!\n');
    }, 5000);
  };

  return (
    <div>
      <div className="page-hd">
        <div>
          <h1>메시지 발송 (PC 카톡 연동)</h1>
          <p>고객 목록에서 대상을 선택하고 맞춤형 메시지를 작성하여 발송 큐에 등록합니다.</p>
        </div>
      </div>

      {sendResult && (
        <div className="alert alert-success" style={{ marginBottom: 20 }}>
          <UserCheck size={16} /> {sendResult}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        {/* Left: Customer Selection */}
        <div className="card" style={{ flex: 1, minWidth: 0 }}>
          <div className="card-hd">
            <h3 className="card-tit">발송 대상 선택</h3>
            <span style={{ fontSize: '0.9rem', color: 'var(--primary)' }}>
              선택됨: {selectedIds.size}명
            </span>
          </div>

          <div className="filters" style={{ padding: '0 20px 10px' }}>
            <div className="search-bar">
              <Search size={16} />
              <input 
                placeholder="이름, 연락처, 차종 검색..." 
                value={search} onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className="filter-chips">
              <button className={`chip ${filter==='all'?'active':''}`} onClick={()=>setFilter('all')}>전체</button>
              <button className={`chip ${filter==='contracted'?'active':''}`} onClick={()=>setFilter('contracted')}>기고객</button>
              <button className={`chip ${filter==='prospect'?'active':''}`} onClick={()=>setFilter('prospect')}>상담고객</button>
              <button className={`chip ${filter==='expiring_1m'?'active':''}`} onClick={()=>setFilter('expiring_1m')}>만기 1개월 이내</button>
            </div>
          </div>

          <div className="table-wrap" style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {loading ? (
              <div className="empty-state">로딩 중...</div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">조건에 맞는 고객이 없습니다.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 40, textAlign: 'center', cursor: 'pointer' }} onClick={toggleAll}>
                      {selectedIds.size > 0 && selectedIds.size === filtered.length ? <CheckSquare size={16}/> : <Square size={16}/>}
                    </th>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>차종</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(c => {
                    const isSel = selectedIds.has(c.id);
                    return (
                      <tr key={c.id} className={isSel ? 'selected' : ''} onClick={() => toggleOne(c.id)} style={{ cursor: 'pointer' }}>
                        <td style={{ textAlign: 'center' }}>
                          {isSel ? <CheckSquare size={16} color="var(--primary)"/> : <Square size={16} color="var(--border)"/>}
                        </td>
                        <td style={{ fontWeight: 500 }}>{c.name}</td>
                        <td>{c.contact}</td>
                        <td>{c.contract_car || '-'}</td>
                        <td>
                          {c.is_contracted && <span className="chip" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>기고객</span>}
                          {c.is_prospect && <span className="chip" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>상담</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right: Message Compose */}
        <div className="card" style={{ width: 400, flexShrink: 0 }}>
          <div className="card-hd">
            <h3 className="card-tit">메시지 작성</h3>
          </div>
          <div style={{ padding: 20 }}>
            <div className="alert alert-info" style={{ marginBottom: 15, padding: '10px 15px', fontSize: '0.85rem' }}>
              <AlertCircle size={14} style={{ marginRight: 6 }}/>
              <code>{`{{이름}}`}</code>, <code>{`{{차종}}`}</code> 등의 변수를 사용하면 고객별 맞춤 텍스트로 자동 치환됩니다.
            </div>
            
            <textarea
              className="form-control"
              style={{ height: 250, resize: 'none', marginBottom: 20, fontFamily: 'inherit' }}
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="전송할 메시지 내용을 입력하세요."
            />

            <button 
              className="btn btn-primary" 
              style={{ width: '100%', justifyContent: 'center', height: 44, fontSize: '1rem' }}
              onClick={handleSend}
              disabled={selectedIds.size === 0}
            >
              <Send size={18} style={{ marginRight: 8 }}/>
              {selectedIds.size > 0 ? `${selectedIds.size}명에게 발송하기` : '발송 대상을 선택하세요'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

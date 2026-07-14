import { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Send, UserCheck, AlertCircle, CheckSquare, Square, Image as ImageIcon, X } from 'lucide-react';
import * as api from './api';

export default function MessageSender() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all'); // 'all', 'contracted', 'prospect', 'expiring_1m', 'expiring_3m', 'custom'
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [message, setMessage] = useState('{{이름}} 고객님 안녕하세요!\n');
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState('');
  const [sendResult, setSendResult] = useState('');
  const fileInputRef = useRef(null);

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
    if (filter === 'contracted' && !Number(c.is_contracted)) return false;
    if (filter === 'prospect' && !Number(c.is_prospect)) return false;
    
    if (filter === 'expiring_1m' || filter === 'expiring_3m' || filter === 'custom') {
      if (!c.expiry_date) return false;
      const expiry = new Date(c.expiry_date);
      const today = new Date();
      
      if (filter === 'expiring_1m') {
        const days = (expiry - today) / (1000 * 60 * 60 * 24);
        if (days < 0 || days > 30) return false;
      } else if (filter === 'expiring_3m') {
        const days = (expiry - today) / (1000 * 60 * 60 * 24);
        if (days < 0 || days > 90) return false;
      } else if (filter === 'custom') {
        if (customStart) {
          if (expiry < new Date(customStart)) return false;
        }
        if (customEnd) {
          const endObj = new Date(customEnd);
          endObj.setHours(23, 59, 59, 999);
          if (expiry > endObj) return false;
        }
      }
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

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (ev) => setImagePreview(ev.target.result);
      reader.readAsDataURL(file);
    }
  };

  const removeImage = () => {
    setImageFile(null);
    setImagePreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSend = async () => {
    if (selectedIds.size === 0) {
      alert("발송할 고객을 1명 이상 선택해주세요.");
      return;
    }
    if (!message.trim()) {
      alert("메시지 내용을 입력해주세요.");
      return;
    }
    
    setLoading(true);
    try {
      let imageUrl = null;
      if (imageFile) {
        const res = await api.uploadFile(imageFile);
        imageUrl = res.url;
      }

      const tasks = Array.from(selectedIds).map(id => {
        const c = customers.find(x => x.id === id);
        let msg = message.replace(/{{이름}}/g, c.name || '');
        msg = msg.replace(/{{차종}}/g, c.contract_car || '');
        msg = msg.replace(/{{연락처}}/g, c.contact || '');
        return {
          customer_id: id,
          message_text: msg,
          image_url: imageUrl
        };
      });

      await api.queueMessages(tasks);
      
      setSendResult(`${selectedIds.size}명의 고객에게 발송 대기열 등록이 완료되었습니다! PC 에이전트가 순차적으로 발송합니다.`);
      
      setTimeout(() => {
        setSendResult('');
        setSelectedIds(new Set());
        setMessage('{{이름}} 고객님 안녕하세요!\n');
        removeImage();
      }, 5000);
    } catch (e) {
      alert("발송 큐 등록 실패: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-hd">
        <div>
          <h1>메시지 발송 (PC 카톡 연동)</h1>
          <p>고객 목록에서 대상을 선택하고 맞춤형 메시지와 이미지를 작성하여 발송 큐에 등록합니다.</p>
        </div>
      </div>

      {sendResult && (
        <div className="alert alert-success" style={{ marginBottom: 20 }}>
          <UserCheck size={16} style={{ marginRight: 8, verticalAlign: 'middle' }}/> 
          <span style={{ verticalAlign: 'middle' }}>{sendResult}</span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
        {/* Left: Customer Selection */}
        <div className="card" style={{ flex: '1 1 55%', minWidth: 0 }}>
          <div className="card-hd">
            <h3 className="card-tit">발송 대상 선택</h3>
            <span style={{ fontSize: '0.9rem', color: 'var(--primary)', fontWeight: 500 }}>
              선택됨: {selectedIds.size}명
            </span>
          </div>

          <div className="filters" style={{ padding: '0 20px 15px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="search-bar" style={{ display: 'flex', alignItems: 'center', gap: 10, position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: 12, color: 'var(--text-3)' }} />
              <input 
                className="form-control"
                style={{ paddingLeft: 38, width: '100%', maxWidth: 400, height: 40, fontSize: '0.95rem' }}
                placeholder="이름, 연락처, 차종 검색..." 
                value={search} onChange={e => setSearch(e.target.value)}
              />
            </div>
            
            <div className="filter-chips" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <button className={`chip ${filter==='all'?'active':''}`} onClick={()=>setFilter('all')}>전체</button>
              <button className={`chip ${filter==='contracted'?'active':''}`} onClick={()=>setFilter('contracted')}>기고객</button>
              <button className={`chip ${filter==='prospect'?'active':''}`} onClick={()=>setFilter('prospect')}>상담고객</button>
              <button className={`chip ${filter==='expiring_1m'?'active':''}`} onClick={()=>setFilter('expiring_1m')}>만기 1개월 이내</button>
              <button className={`chip ${filter==='expiring_3m'?'active':''}`} onClick={()=>setFilter('expiring_3m')}>만기 3개월 이내</button>
              <button className={`chip ${filter==='custom'?'active':''}`} onClick={()=>setFilter('custom')}>기간 직접 설정</button>
            </div>

            {filter === 'custom' && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 4, padding: '10px 15px', background: 'var(--bg-card)', borderRadius: 6, border: '1px solid var(--border)' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-2)' }}>만기일 검색:</span>
                <input 
                  type="date" 
                  className="form-control" 
                  style={{ width: 140, height: 36 }}
                  value={customStart}
                  onChange={e => setCustomStart(e.target.value)}
                />
                <span style={{ color: 'var(--text-3)' }}>~</span>
                <input 
                  type="date" 
                  className="form-control" 
                  style={{ width: 140, height: 36 }}
                  value={customEnd}
                  onChange={e => setCustomEnd(e.target.value)}
                />
              </div>
            )}
          </div>

          <div className="table-wrap" style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {loading ? (
              <div className="empty-state">로딩 중...</div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">조건에 맞는 고객이 없습니다.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 40, textAlign: 'center', cursor: 'pointer' }} onClick={toggleAll}>
                      {selectedIds.size > 0 && selectedIds.size === filtered.length ? <CheckSquare size={18}/> : <Square size={18}/>}
                    </th>
                    <th>이름</th>
                    <th>연락처</th>
                    <th>차종</th>
                    <th>만기일</th>
                    <th>상태</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(c => {
                    const isSel = selectedIds.has(c.id);
                    return (
                      <tr key={c.id} className={isSel ? 'selected' : ''} onClick={() => toggleOne(c.id)} style={{ cursor: 'pointer' }}>
                        <td style={{ textAlign: 'center' }}>
                          {isSel ? <CheckSquare size={18} color="var(--primary)"/> : <Square size={18} color="var(--border)"/>}
                        </td>
                        <td style={{ fontWeight: 500 }}>{c.name}</td>
                        <td>{c.contact}</td>
                        <td>{c.contract_car || '-'}</td>
                        <td>{c.expiry_date || '-'}</td>
                        <td>
                          {Number(c.is_contracted) > 0 && <span className="chip" style={{ background: 'var(--success-bg)', color: 'var(--success)', padding: '2px 8px', fontSize: '0.75rem' }}>기고객</span>}
                          {Number(c.is_prospect) > 0 && <span className="chip" style={{ background: 'var(--warning-bg)', color: 'var(--warning)', padding: '2px 8px', fontSize: '0.75rem', marginLeft: 4 }}>상담</span>}
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
        <div className="card" style={{ flex: '1 1 45%', minWidth: 400 }}>
          <div className="card-hd">
            <h3 className="card-tit">메시지 작성</h3>
          </div>
          <div style={{ padding: 20 }}>
            <div className="alert alert-info" style={{ marginBottom: 15, padding: '12px 16px', fontSize: '0.85rem', display: 'flex', alignItems: 'flex-start' }}>
              <AlertCircle size={16} style={{ marginRight: 8, flexShrink: 0, marginTop: 2 }}/>
              <span style={{ lineHeight: 1.5 }}>
                <code>{`{{이름}}`}</code>, <code>{`{{차종}}`}</code> 등의 변수를 사용하면 고객별 맞춤 텍스트로 자동 치환됩니다.
              </span>
            </div>
            
            <textarea
              className="form-control"
              style={{ width: '100%', height: 280, resize: 'none', marginBottom: 15, fontFamily: 'inherit', fontSize: '0.95rem', padding: 15, lineHeight: 1.6 }}
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="전송할 메시지 내용을 입력하세요."
            />

            {/* Image Attachment Area */}
            <div style={{ marginBottom: 25, border: '1px dashed var(--border)', borderRadius: 8, padding: 15, background: 'var(--bg-card)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: imagePreview ? 15 : 0 }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-1)', fontWeight: 500, display: 'flex', alignItems: 'center' }}>
                  <ImageIcon size={16} style={{ marginRight: 6 }}/> 이미지 첨부 (선택)
                </span>
                <button 
                  className="btn btn-outline" 
                  style={{ padding: '6px 12px', fontSize: '0.85rem' }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  파일 선택
                </button>
                <input 
                  type="file" 
                  accept="image/*" 
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  onChange={handleImageChange}
                />
              </div>

              {imagePreview && (
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <img src={imagePreview} alt="첨부 이미지 미리보기" style={{ maxWidth: 200, maxHeight: 150, borderRadius: 6, border: '1px solid var(--border)' }} />
                  <button 
                    onClick={removeImage}
                    style={{ position: 'absolute', top: -10, right: -10, background: 'var(--danger)', color: 'white', border: 'none', borderRadius: '50%', width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 5px rgba(0,0,0,0.2)' }}
                    title="이미지 삭제"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            <button 
              className="btn btn-primary" 
              style={{ width: '100%', justifyContent: 'center', height: 48, fontSize: '1.05rem', fontWeight: 600 }}
              onClick={handleSend}
              disabled={selectedIds.size === 0}
            >
              <Send size={20} style={{ marginRight: 8 }}/>
              {selectedIds.size > 0 ? `${selectedIds.size}명에게 발송하기` : '발송 대상을 선택하세요'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

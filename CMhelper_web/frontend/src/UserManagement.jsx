import React, { useState, useEffect } from 'react';
import { Shield, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import * as api from './api';

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await api.getUsers();
      setUsers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleStatusChange = async (userId, newStatus) => {
    try {
      await api.updateUserStatus(userId, newStatus);
      fetchUsers();
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) return <div style={{ padding: '2rem' }}>로딩 중...</div>;
  if (error) return <div style={{ padding: '2rem', color: 'var(--danger)' }}>오류: {error}</div>;

  return (
    <div className="dashboard-content" style={{ padding: '2rem' }}>
      <header className="dash-header" style={{ marginBottom: '2rem' }}>
        <h1 className="dash-title">사용자 관리</h1>
        <p className="dash-subtitle">회사 내 사용자 계정 상태와 권한을 관리합니다.</p>
      </header>

      <div className="table-container" style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', boxShadow: '0 4px 15px var(--shadow)', overflow: 'hidden' }}>
        <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ background: 'var(--bg-table-head)', color: 'var(--text-3)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            <tr>
              <th style={{ padding: '1rem', textAlign: 'left', fontWeight: 600 }}>이름</th>
              <th style={{ padding: '1rem', textAlign: 'left', fontWeight: 600 }}>이메일</th>
              <th style={{ padding: '1rem', textAlign: 'left', fontWeight: 600 }}>역할</th>
              <th style={{ padding: '1rem', textAlign: 'left', fontWeight: 600 }}>상태</th>
              <th style={{ padding: '1rem', textAlign: 'center', fontWeight: 600 }}>가입일</th>
              <th style={{ padding: '1rem', textAlign: 'center', fontWeight: 600 }}>관리</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '1rem' }}><strong>{u.name}</strong></td>
                <td style={{ padding: '1rem', color: 'var(--text-2)' }}>{u.email}</td>
                <td style={{ padding: '1rem' }}>
                  <span className="badge" style={{ backgroundColor: u.role === 'OWNER' ? 'rgba(99,102,241,0.1)' : 'var(--bg-input)', color: u.role === 'OWNER' ? 'var(--primary)' : 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px' }}>
                    {u.role === 'OWNER' ? '최고 관리자' : '일반 사용자'}
                  </span>
                </td>
                <td style={{ padding: '1rem' }}>
                  {u.status === 'ACTIVE' && <span className="badge" style={{ color: 'var(--success)', background: 'var(--success-bg)', padding: '0.3rem 0.6rem', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}><CheckCircle size={14}/> 정상</span>}
                  {u.status === 'PENDING' && <span className="badge" style={{ color: 'var(--warn)', background: 'var(--warn-bg)', padding: '0.3rem 0.6rem', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}><Clock size={14}/> 승인 대기</span>}
                  {u.status === 'INACTIVE' && <span className="badge" style={{ color: 'var(--danger)', background: 'rgba(244,63,94,0.1)', padding: '0.3rem 0.6rem', borderRadius: '4px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}><XCircle size={14}/> 비활성</span>}
                </td>
                <td style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)', fontSize: '0.9rem' }}>
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '1rem', textAlign: 'center' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                    {u.status === 'PENDING' && (
                      <button className="btn btn-sm" style={{ background: 'var(--success)', color: 'white', border: 'none' }} onClick={() => handleStatusChange(u.id, 'ACTIVE')}>
                        승인
                      </button>
                    )}
                    {u.status === 'ACTIVE' && u.role !== 'OWNER' && (
                      <button className="btn btn-sm btn-ghost" style={{ color: 'var(--danger)' }} onClick={() => { if(window.confirm('이 사용자를 비활성화하시겠습니까?')) handleStatusChange(u.id, 'INACTIVE'); }}>
                        비활성화
                      </button>
                    )}
                    {u.status === 'INACTIVE' && (
                      <button className="btn btn-sm btn-ghost" style={{ color: 'var(--success)' }} onClick={() => handleStatusChange(u.id, 'ACTIVE')}>
                        활성화
                      </button>
                    )}
                    {u.role === 'OWNER' && (
                      <span style={{ color: 'var(--text-3)', fontSize: '0.85rem' }}>관리 불가</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan="6" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-3)' }}>
                  사용자가 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import React, { useState } from 'react';

export default function LoginForm({ onLogin, switchToRegister }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onLogin({ email, password });
    } catch (err) {
      setError(err.message || '로그인에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-card">
      <h2 className="auth-title">Welcome Back</h2>
      <p className="auth-subtitle">CMhelper 계정에 로그인하세요</p>
      
      {error && <div className="auth-error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="auth-form-group">
          <label className="auth-label">이메일 주소</label>
          <input 
            type="email" 
            className="auth-input" 
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@cmhelper.com"
            required 
          />
        </div>
        <div className="auth-form-group">
          <label className="auth-label">비밀번호</label>
          <input 
            type="password" 
            className="auth-input" 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required 
          />
        </div>
        
        <button type="submit" className="auth-button" disabled={loading}>
          {loading ? '로그인 중...' : '로그인'}
        </button>
      </form>
      
      <div className="auth-switch">
        계정이 없으신가요? 
        <span className="auth-switch-link" onClick={switchToRegister}>
          회원가입
        </span>
      </div>
    </div>
  );
}

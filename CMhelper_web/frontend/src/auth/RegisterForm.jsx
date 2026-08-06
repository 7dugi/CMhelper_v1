import React, { useState } from 'react';

export default function RegisterForm({ onRegister, switchToLogin }) {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    password_confirm: '',
    invite_code: ''
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({...formData, [e.target.name]: e.target.value});
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (formData.password !== formData.password_confirm) {
      return setError('비밀번호가 일치하지 않습니다.');
    }
    if (formData.password.length < 8) {
      return setError('비밀번호는 최소 8자 이상이어야 합니다.');
    }
    setLoading(true);
    try {
      await onRegister(formData);
    } catch (err) {
      setError(err.message || '회원가입에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-card">
      <h2 className="auth-title">Create Account</h2>
      <p className="auth-subtitle">초대코드를 입력하고 CMhelper를 시작하세요</p>
      
      {error && <div className="auth-error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="auth-form-group">
          <label className="auth-label">이름</label>
          <input 
            type="text" 
            name="name"
            className="auth-input" 
            value={formData.name}
            onChange={handleChange}
            placeholder="홍길동"
            required 
          />
        </div>
        <div className="auth-form-group">
          <label className="auth-label">이메일 주소</label>
          <input 
            type="email" 
            name="email"
            className="auth-input" 
            value={formData.email}
            onChange={handleChange}
            placeholder="admin@cmhelper.com"
            required 
          />
        </div>
        <div className="auth-form-group">
          <label className="auth-label">비밀번호 (8자 이상)</label>
          <input 
            type="password" 
            name="password"
            className="auth-input" 
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            required 
            minLength={8}
          />
        </div>
        <div className="auth-form-group">
          <label className="auth-label">비밀번호 확인</label>
          <input 
            type="password" 
            name="password_confirm"
            className="auth-input" 
            value={formData.password_confirm}
            onChange={handleChange}
            placeholder="••••••••"
            required 
            minLength={8}
          />
        </div>
        <div className="auth-form-group">
          <label className="auth-label">초대코드</label>
          <input 
            type="text" 
            name="invite_code"
            className="auth-input" 
            value={formData.invite_code}
            onChange={handleChange}
            placeholder="CMHELPER2026"
            required 
          />
        </div>
        
        <button type="submit" className="auth-button" disabled={loading}>
          {loading ? '가입 중...' : '회원가입'}
        </button>
      </form>
      
      <div className="auth-switch">
        이미 계정이 있으신가요? 
        <span className="auth-switch-link" onClick={switchToLogin}>
          로그인
        </span>
      </div>
    </div>
  );
}

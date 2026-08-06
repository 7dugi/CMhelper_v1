import React, { useState } from 'react';
import './auth.css';
import LoginForm from './LoginForm';
import RegisterForm from './RegisterForm';
import { registerUser, loginUser } from '../api';

export default function AuthScreen({ onLoginSuccess }) {
  const [view, setView] = useState('login'); // 'login' | 'register'

  const handleLogin = async (credentials) => {
    const res = await loginUser(credentials);
    // Token is returned in res.access_token
    sessionStorage.setItem('cmhelper_token', res.access_token);
    await onLoginSuccess();
  };

  const handleRegister = async (data) => {
    // Register user
    await registerUser(data);
    // Auto login after successful register
    const res = await loginUser({ email: data.email, password: data.password });
    sessionStorage.setItem('cmhelper_token', res.access_token);
    await onLoginSuccess();
  };

  return (
    <div className="auth-container">
      {view === 'login' ? (
        <LoginForm 
          onLogin={handleLogin} 
          switchToRegister={() => setView('register')} 
        />
      ) : (
        <RegisterForm 
          onRegister={handleRegister} 
          switchToLogin={() => setView('login')} 
        />
      )}
    </div>
  );
}

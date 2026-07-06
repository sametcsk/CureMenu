// frontend/modules/auth-manager.js

window.AuthManager = {
    getUser() {
        return {
            telefon: localStorage.getItem('cm_telefon') || '',
            kullanici_adi: localStorage.getItem('cm_kullanici_adi') || ''
        };
    },

    requireAuth() {
        const user = this.getUser();
        if (!user.telefon || localStorage.getItem('cm_disclaimer_ok') !== 'true') {
            window.location.href = '/giris';
            return null;
        }
        return user;
    },

    async login(telefon, sifre) {
        const loginRes = await fetch((window.API || '') + '/api/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telefon, sifre }),
        });
        
        const loginData = await loginRes.json();
        
        if (!loginRes.ok || !loginData.success) {
            throw new Error(loginData.detail || 'Giriş yapılamadı.');
        }

        localStorage.setItem('cm_telefon', telefon);
        localStorage.setItem('cm_kullanici_adi', loginData.kullanici_adi || '');
        localStorage.setItem('cm_has_profile', loginData.has_profile ? 'true' : 'false');
        localStorage.setItem('cm_disclaimer_ok', 'true');
        
        return loginData;
    },

    async register(telefon, kullanici_adi, sifre) {
        const registerRes = await fetch((window.API || '') + '/api/register', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telefon, kullanici_adi, sifre }),
        });
        
        const registerData = await registerRes.json();
        
        if (!registerRes.ok || !registerData.success) {
            throw new Error(registerData.detail || 'Kayıt yapılamadı.');
        }
        
        return registerData;
    },

    async logout() {
        try {
            await fetch((window.API || '') + '/api/logout', { method: 'POST', credentials: 'include' });
        } catch(e) {}
        
        ['cm_telefon', 'cm_kullanici_adi', 'cm_has_profile', 'cm_onboarding_done', 'cm_disclaimer_ok'].forEach(k => localStorage.removeItem(k));
        window.location.href = '/';
    }
};

// Expose legacy global functions for backward compatibility with inline HTML handlers
window.getUser = () => window.AuthManager.getUser();
window.logout = () => window.AuthManager.logout();

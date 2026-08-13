/* First-party product analytics. Never include message text or health/profile values. */
(function () {
  'use strict';
  const SESSION_KEY = 'cm_analytics_session', ANON_KEY = 'cm_analytics_anonymous', COHORT_KEY = 'cm_research_cohort', INACTIVE_MS = 45000;
  const tabs = { dashboard: 'home', profile: 'profile', plan: 'weekly_plan', tarayici: 'menu_analysis', buzdolabi: 'fridge', tahlil: 'lab', curebot: 'curebot', gecmis: 'history' };
  let currentScreen = '', startedAt = 0, lastActivity = Date.now();
  function uuid() { if (window.crypto?.randomUUID) return window.crypto.randomUUID(); return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = Math.random() * 16 | 0; return (c === 'x' ? r : (r & 3 | 8)).toString(16); }); }
  function stored(key, storage) { let value = storage.getItem(key); if (!value) { value = uuid(); storage.setItem(key, value); } return value; }
  function cohort() { const value = (new URLSearchParams(location.search).get('cohort') || localStorage.getItem(COHORT_KEY) || '').toUpperCase(); if (/^C\d{2,3}$/.test(value)) { localStorage.setItem(COHORT_KEY, value); return value; } return ''; }
  function send(eventName, fields) { const body = JSON.stringify(Object.assign({ event_name: eventName, session_id: stored(SESSION_KEY, sessionStorage), anonymous_user_id: stored(ANON_KEY, localStorage), app_version: 'web-v1', research_cohort: cohort() }, fields || {})); try { if (navigator.sendBeacon) navigator.sendBeacon('/api/analytics/event', new Blob([body], { type: 'application/json' })); else fetch('/api/analytics/event', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body }).catch(() => {}); } catch (_) {} }
  function flush() { if (!currentScreen || !startedAt) return; const duration = Date.now() - startedAt; if (duration > 500) send('screen_active_time', { screen: currentScreen, active_duration_ms: Math.min(duration, INACTIVE_MS) }); startedAt = 0; }
  function screenViewed(tab) { flush(); currentScreen = tabs[tab] || ''; startedAt = Date.now(); if (!currentScreen) return; send('screen_viewed', { screen: currentScreen }); const opened = { curebot: 'curebot_opened', plan: 'weekly_plan_opened', tarayici: 'menu_analysis_opened', buzdolabi: 'fridge_analysis_opened', tahlil: 'lab_analysis_opened' }[tab]; if (opened) send(opened, { screen: currentScreen, feature: currentScreen === 'weekly_plan' ? 'weekly_plan' : currentScreen.replace('_analysis', '') }); }
  ['click', 'keydown', 'touchstart', 'scroll'].forEach(name => document.addEventListener(name, () => { lastActivity = Date.now(); }, { passive: true }));
  document.addEventListener('click', event => { const target = event.target.closest?.('[data-analytics-id]'); const actionId = target?.dataset.analyticsId; if (/^[a-z0-9][a-z0-9_-]{0,63}$/.test(actionId || '')) send('cta_clicked', { metadata: { action_id: actionId } }); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) flush(); else startedAt = Date.now(); }); window.addEventListener('pagehide', flush);
  window.setInterval(() => { if (Date.now() - lastActivity < INACTIVE_MS && currentScreen) send('session_heartbeat', { screen: currentScreen }); }, 30000);
  window.CureMenuAnalytics = { track: send, screenViewed, feature: (feature, eventName, metadata) => send(eventName, { feature, metadata: metadata || {} }) }; send('session_started');
})();

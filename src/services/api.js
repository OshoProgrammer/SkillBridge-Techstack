let authToken = null;
export function setAuthToken(token) { authToken = token; }
function apiFetch(input, init = {}) {
    const headers = new Headers(init.headers);
    if (authToken)
        headers.set('Authorization', `Bearer ${authToken}`);
    return fetch(input, { ...init, headers });
}
/**
 * SkillBridge — API Service Client
 * Handles server communication, offline caching, and PWA synchronization.
 */
export async function fetchAppState() {
    try {
        const res = await apiFetch('/api/state');
        if (!res.ok)
            throw new Error('Failed to fetch state');
        const data = await res.json();
        // Cache snapshot in localStorage for offline availability
        localStorage.setItem('skillbridge_offline_state', JSON.stringify(data));
        return data;
    }
    catch (err) {
        console.warn('Network unavailable, loading offline cached state:', err);
        const cached = localStorage.getItem('skillbridge_offline_state');
        if (cached) {
            return JSON.parse(cached);
        }
        throw err;
    }
}
export async function resetAppState() {
    const res = await apiFetch('/api/reset-state', { method: 'POST' });
    return res.json();
}
export async function updateRoleCompetencies(roleId, requiredCompetencies, actorName) {
    const res = await apiFetch(`/api/roles/${roleId}/competencies`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requiredCompetencies, actorName }),
    });
    return res.json();
}
export async function submitAssessment(payload) {
    if (payload.isOffline) {
        // Queue offline submission
        const queue = JSON.parse(localStorage.getItem('skillbridge_offline_queue') || '[]');
        queue.push({
            ...payload,
            id: `offline-sub-${Date.now()}`,
            submittedAt: new Date().toISOString(),
        });
        localStorage.setItem('skillbridge_offline_queue', JSON.stringify(queue));
        return {
            success: true,
            offlineQueued: true,
            message: 'Assessment saved locally. Will automatically sync when reconnected.',
        };
    }
    const res = await apiFetch(`/api/employees/${payload.employeeId}/assessments/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function completeCourse(employeeId, courseId) {
    const res = await apiFetch(`/api/employees/${employeeId}/courses/${courseId}/complete`, {
        method: 'POST',
    });
    return res.json();
}
export async function checkDuplicateKnowledge(payload) {
    const res = await apiFetch('/api/knowledge/check-duplicate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function executeKnowledgeAction(payload) {
    const res = await apiFetch('/api/knowledge/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function extractKnowledgeWithAI(payload) {
    const res = await apiFetch('/api/ai/extract-knowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function advanceDraftPipeline(payload) {
    const res = await apiFetch('/api/ai/drafts/pipeline-action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function sendManagerNudge(payload) {
    const res = await apiFetch('/api/manager/nudge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function syncOfflineSubmissions() {
    const queue = JSON.parse(localStorage.getItem('skillbridge_offline_queue') || '[]');
    if (queue.length === 0)
        return { success: true, syncedCount: 0 };
    const res = await apiFetch('/api/offline/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ submissions: queue }),
    });
    const data = await res.json();
    if (data.success) {
        localStorage.removeItem('skillbridge_offline_queue');
    }
    return data;
}
export async function explainLearningPathWithAI(payload) {
    try {
        const res = await apiFetch('/api/ai/explain-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        return res.json();
    }
    catch (err) {
        return {
            explanation: `Targeted to elevate ${payload.competencyName} from ${payload.currentScore}% to Level ${payload.requiredLevel} readiness benchmark.`,
        };
    }
}
export async function loginOfficer(payload) {
    const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
/**
 * Demo Persona session: starts a credential-free sandbox session for the
 * predefined demo personas only. Password / Gmail OTP are never requested.
 * Real officers must keep using `loginOfficer` + `sendGmailOtp`/`verifyGmailOtp`.
 */
export async function loginAsDemoPersona(personaId) {
    const res = await apiFetch('/api/auth/demo-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personaId }),
    });
    return res.json();
}
export async function sendGmailOtp(payload) {
    const res = await apiFetch('/api/auth/send-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function verifyGmailOtp(payload) {
    const res = await apiFetch('/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}
export async function getSmtpStatus() {
    const res = await fetch('/api/auth/smtp-status');
    return res.json();
}
export async function configureSmtp(payload) {
    const res = await fetch('/api/auth/smtp-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    return res.json();
}

// ============================================================
// API 服务类 — 封装所有后端接口调用
// ============================================================
class ApiService {
    constructor(baseUrl = "http://localhost:8000") {
        this.baseUrl = baseUrl;
        this.token = localStorage.getItem("auth_token");
    }

    setToken(token) {
        this.token = token;
        if (token) localStorage.setItem("auth_token", token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem("auth_token");
    }

    async _fetch(path, options = {}) {
        const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
        if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
        const res = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            throw new ApiError(res.status, body.detail || `请求失败 (${res.status})`);
        }
        return res.json();
    }

    _get(path)  { return this._fetch(path); }
    _post(path, body) { return this._fetch(path, { method: "POST", body: JSON.stringify(body) }); }
    _delete(path) { return this._fetch(path, { method: "DELETE" }); }

    async login(username, password) {
        const data = await this._post("/login", { username, password });
        this.setToken(data.access_token);
        return data;
    }

    async chat(message, sessionId = null) {
        const body = { message };
        if (sessionId) body.session_id = sessionId;
        return this._post("/chat", body);
    }

    async getSessions() {
        const data = await this._get("/chat/sessions");
        return data.sessions || [];
    }

    async getSessionMessages(sessionId) {
        const data = await this._get(`/chat/session/${sessionId}/messages`);
        return data.messages || [];
    }

    async getSessionStats(sessionId) {
        return this._get(`/chat/session/${sessionId}`);
    }

    async deleteSession(sessionId) {
        return this._delete(`/chat/session/${sessionId}`);
    }
}

class ApiError extends Error {
    constructor(status, message) { super(message); this.status = status; this.name = "ApiError"; }
}

// ============================================================
// 全局实例 & 状态
// ============================================================
const api = new ApiService("http://localhost:8000");
let currentSessionId = null;
let allSessions = [];
let currentUser = JSON.parse(localStorage.getItem("current_user") || "null");

// ============================================================
// DOM
// ============================================================
const chatMessages = document.getElementById("chatMessages");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const historyList = document.getElementById("historyList");
const loginOverlay = document.getElementById("loginOverlay");
const loginError = document.getElementById("loginError");
const loginBtn = document.getElementById("loginBtn");
const userAvatar = document.getElementById("userAvatar");
const userNameEl = document.getElementById("userName");

// ============================================================
// 富文本渲染
// ============================================================
function formatContent(text) {
    let html = escapeHtml(text);
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g,
        (_, lang, code) => `<pre class="code-block"><code>${escapeHtml(code.trim())}</code></pre>`);
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    if (html.includes("|") && html.includes("\n")) {
        html = html.replace(/((?:^|\n)\|.+\|(?:\n\|[-:| ]+\|)?(?:\n\|.+\|)+)/g, (table) => {
            const rows = table.trim().split("\n").filter(r => r.includes("|") && !r.match(/^\|[-:| ]+\|$/));
            return `<table class="msg-table"><tbody>${rows.map(r =>
                "<tr>" + r.split("|").slice(1, -1).map(c => `<td>${c.trim()}</td>`).join("") + "</tr>"
            ).join("")}</tbody></table>`;
        });
    }
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    html = html.replace(/^---+$/gm, '<hr>');
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    return `<p>${html}</p>`.replace(/<p><\/p>/g, '');
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// 认证
// ============================================================
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value;
    loginError.textContent = "";
    loginBtn.disabled = true;
    loginBtn.textContent = "登录中...";
    try {
        const data = await api.login(username, password);
        currentUser = { name: data.name, role: data.role, username: data.username };
        localStorage.setItem("current_user", JSON.stringify(currentUser));
        loginOverlay.classList.add("hidden");
        updateUserDisplay();
        await loadHistoryList();
    } catch (err) {
        loginError.textContent = err.message;
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = "登 录";
    }
}

function fillLogin(u, p) { document.getElementById("loginUsername").value = u; document.getElementById("loginPassword").value = p; }

function logout() {
    api.clearToken(); currentUser = null;
    localStorage.removeItem("current_user");
    currentSessionId = null;
    chatMessages.innerHTML = "";
    showWelcomeCard();
    historyList.innerHTML = '<p class="history-hint">暂无对话记录</p>';
    loginOverlay.classList.remove("hidden");
    updateUserDisplay();
}

function updateUserDisplay() {
    if (currentUser) {
        userAvatar.textContent = currentUser.name[0];
        userNameEl.textContent = `${currentUser.name} · ${currentUser.role}`;
    } else {
        userAvatar.textContent = "?"; userNameEl.textContent = "未登录";
    }
}

// ============================================================
// 会话历史
// ============================================================
async function loadHistoryList() {
    try { allSessions = await api.getSessions(); renderHistoryList(); }
    catch (e) { console.error("加载历史失败:", e); }
}

function renderHistoryList() {
    historyList.innerHTML = "";
    if (!allSessions.length) { historyList.innerHTML = '<p class="history-hint">暂无对话记录</p>'; return; }
    allSessions.forEach(s => {
        const div = document.createElement("div");
        div.className = `history-item${s.session_id === currentSessionId ? " active" : ""}`;
        div.innerHTML = `<svg class="history-item-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span class="history-item-text" title="${escapeHtml(s.title)}">${escapeHtml(s.title)}</span>
            <button class="history-item-delete" title="删除对话">&times;</button>`;
        div.addEventListener("click", e => { if (!e.target.classList.contains("history-item-delete")) loadSession(s.session_id); });
        div.querySelector(".history-item-delete").addEventListener("click", async e => {
            e.stopPropagation(); await api.deleteSession(s.session_id);
            if (currentSessionId === s.session_id) newChat(); await loadHistoryList();
        });
        historyList.appendChild(div);
    });
}

async function loadSession(sessionId) {
    try {
        const stats = await api.getSessionStats(sessionId);
        currentSessionId = sessionId; chatMessages.innerHTML = "";
        if (stats.message_count > 0) {
            const msgs = await api.getSessionMessages(sessionId);
            msgs.forEach(m => addMessage(m.role, m.content));
        } else showWelcomeCard();
        renderHistoryList();
    } catch (e) { console.error("加载会话失败:", e); }
}

// ============================================================
// 消息渲染
// ============================================================
function addMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const avatar = role === "user" ? "🧑" : "🤖";
    const body = role === "assistant" ? formatContent(content) : escapeHtml(content);
    div.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-content">${body}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
    return div;
}

function addTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message assistant"; div.id = "typingIndicator";
    div.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
}

// ============================================================
// 发送消息
// ============================================================
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    messageInput.value = ""; messageInput.style.height = "auto";
    sendBtn.disabled = true; messageInput.disabled = true;
    removeWelcomeCard(); addMessage("user", message); addTypingIndicator();
    try {
        const data = await api.chat(message, currentSessionId);
        currentSessionId = data.session_id;
        removeTypingIndicator();
        addMessage("assistant", data.reply);
        await loadHistoryList();
    } catch (error) {
        removeTypingIndicator();
        addMessage("assistant", `❌ 出错了：${error.message}`);
    } finally {
        sendBtn.disabled = false; messageInput.disabled = false; messageInput.focus();
    }
}

function sendSuggestion(text) { messageInput.value = text; sendMessage(); }

// ============================================================
// 辅助
// ============================================================
function scrollToBottom() { chatMessages.scrollTop = chatMessages.scrollHeight; }
function removeWelcomeCard() { const w = document.querySelector(".welcome-card"); if (w) w.remove(); }
function removeTypingIndicator() { const el = document.getElementById("typingIndicator"); if (el) el.remove(); }

function handleKeyDown(e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }
messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + "px";
});

function newChat() { currentSessionId = null; showWelcomeCard(); renderHistoryList(); messageInput.focus(); }

function showWelcomeCard() {
    chatMessages.innerHTML = `<div class="welcome-card">
        <div class="welcome-icon"><svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg></div>
        <h2>你好，我是你的 AI 助手</h2>
        <p>基于 Qwen 大模型，查询销售数据、分析趋势</p>
        <div class="suggestions">
            <button class="suggestion-chip" onclick="sendSuggestion('帮我查一下各区域的销售总额')">📊 各区域销售总额</button>
            <button class="suggestion-chip" onclick="sendSuggestion('最近销售趋势怎么样？')">📈 最近销售趋势</button>
            <button class="suggestion-chip" onclick="sendSuggestion('哪个产品类别利润最高？')">🏆 利润最高类别</button>
            <button class="suggestion-chip" onclick="sendSuggestion('请用一句话介绍你自己')">💡 介绍一下你自己</button>
        </div></div>`;
}

// ============================================================
// 初始化
// ============================================================
if (api.token && currentUser) {
    loginOverlay.classList.add("hidden");
    updateUserDisplay();
    loadHistoryList();
} else {
    loginOverlay.classList.remove("hidden");
    updateUserDisplay();
}
messageInput.focus();

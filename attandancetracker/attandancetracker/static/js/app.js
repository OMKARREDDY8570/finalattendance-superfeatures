/* ─── State ────────────────────────────────────────────────────────────────── */
let attendanceData  = null;
let currentRoll     = null;
let currentPassword = null;
let pieChart        = null;
let barChart        = null;
let isSubscribed    = false;

/* ─── DOM refs ─────────────────────────────────────────────────────────────── */
const loginModal      = document.getElementById('login-modal');
const loginForm       = document.getElementById('login-form');
const loginError      = document.getElementById('login-error');
const loginBtn        = document.getElementById('login-btn');
const loginBtnText    = document.getElementById('login-btn-text');
const loginSpinner    = document.getElementById('login-spinner');
const dashboard       = document.getElementById('dashboard');
const sidebar         = document.getElementById('sidebar');
const sidebarOverlay  = document.getElementById('sidebar-overlay');
const menuToggle      = document.getElementById('menu-toggle');
const darkModeToggle  = document.getElementById('dark-mode-toggle');
const darkIcon        = document.getElementById('dark-icon');
const userDisplay     = document.getElementById('user-display');
const userAvatar      = document.getElementById('user-avatar');
const alertBanner     = document.getElementById('alert-banner');
const dangerBar       = document.getElementById('danger-bar');
const dangerBarMsg    = document.getElementById('danger-bar-msg');
const subBadge        = document.getElementById('sub-badge');
const subBtnText      = document.getElementById('sub-btn-text');
const getDailyBtn     = document.getElementById('get-daily-updates-btn');
const unsubBtn        = document.getElementById('unsub-btn');
const sendNowBtn      = document.getElementById('send-now-btn');
const toast           = document.getElementById('toast');
const toastIcon       = document.getElementById('toast-icon');
const toastMsg        = document.getElementById('toast-msg');

/* ─── Login password toggle ───────────────────────────────────────────────── */
document.getElementById('toggle-login-pw')?.addEventListener('click', () => {
    const inp  = document.getElementById('password');
    const icon = document.getElementById('toggle-login-pw-icon');
    if (inp.type === 'password') {
        inp.type = 'text';
        icon.className = 'fas fa-eye-slash text-sm';
    } else {
        inp.type = 'password';
        icon.className = 'fas fa-eye text-sm';
    }
});

/* ─── Toast ────────────────────────────────────────────────────────────────── */
let toastTimer;
const toastColors = {
    success: 'border-green-300 bg-green-50 text-green-800',
    error:   'border-red-300 bg-red-50 text-red-800',
    info:    'border-blue-300 bg-blue-50 text-blue-800',
    warning: 'border-amber-300 bg-amber-50 text-amber-800'
};
const toastColorsDark = {
    success: 'border-green-700 bg-green-900 text-green-200',
    error:   'border-red-700 bg-red-900 text-red-200',
    info:    'border-blue-700 bg-blue-900 text-blue-200',
    warning: 'border-amber-700 bg-amber-900 text-amber-200'
};
function showToast(msg, type = 'success') {
    clearTimeout(toastTimer);
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const isDark = document.documentElement.classList.contains('dark');
    const colorClass = isDark ? (toastColorsDark[type] || toastColorsDark.info) : (toastColors[type] || toastColors.info);
    toast.className = `toast-hide fixed bottom-6 right-6 z-[9999] px-5 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-sm font-medium max-w-xs border ${colorClass}`;
    toastIcon.textContent = icons[type] || '•';
    toastMsg.textContent  = msg;
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            toast.classList.remove('toast-hide');
        });
    });
    toastTimer = setTimeout(() => toast.classList.add('toast-hide'), 4000);
}

/* ─── Dark Mode ────────────────────────────────────────────────────────────── */
function applyTheme(dark) {
    document.documentElement.classList.toggle('dark', dark);
    darkIcon.className = dark ? 'fas fa-sun' : 'fas fa-moon';
}
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
applyTheme(localStorage.theme === 'dark' || (!('theme' in localStorage) && prefersDark));

darkModeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.theme = isDark ? 'dark' : 'light';
    darkIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
});

/* ─── Mobile sidebar ───────────────────────────────────────────────────────── */
menuToggle.addEventListener('click', () => {
    sidebar.classList.toggle('mobile-hidden');
    sidebarOverlay.classList.toggle('hidden');
});
sidebarOverlay.addEventListener('click', () => {
    sidebar.classList.add('mobile-hidden');
    sidebarOverlay.classList.add('hidden');
});

/* ─── Animated counter ─────────────────────────────────────────────────────── */
function animateValue(id, start, end, duration) {
    const el = document.getElementById(id);
    const range = end - start;
    const startTime = performance.now();
    const isFloat   = !Number.isInteger(end);
    function step(now) {
        let progress = Math.min((now - startTime) / duration, 1);
        progress = 1 - Math.pow(1 - progress, 3);
        const val = start + range * progress;
        el.textContent = isFloat ? val.toFixed(2) : Math.round(val);
        if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

/* ─── Login ────────────────────────────────────────────────────────────────── */
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const roll     = document.getElementById('roll').value.trim();
    const password = document.getElementById('password').value;

    loginBtn.disabled = true;
    loginBtnText.textContent = 'Fetching data…';
    loginSpinner.classList.remove('hidden');
    loginError.classList.add('hidden');

    try {
        const res  = await fetch('/api/attendance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll, password })
        });
        const data = await res.json();

        if (data.status === 'success') {
            attendanceData  = data.data;
            currentRoll     = roll;
            currentPassword = password;

            userDisplay.textContent = roll;
            userAvatar.textContent  = roll[0].toUpperCase();
            document.getElementById('last-updated-label').textContent =
                'Last updated: ' + new Date().toLocaleTimeString();

            updateSubscriptionUI(data.subscription);

            loginModal.style.opacity    = '0';
            loginModal.style.transform  = 'scale(0.95)';
            loginModal.style.transition = 'opacity .3s, transform .3s';
            setTimeout(() => {
                loginModal.style.display = 'none';
                dashboard.classList.remove('hidden');
                dashboard.style.opacity    = '0';
                dashboard.style.transition = 'opacity .4s';
                requestAnimationFrame(() => { dashboard.style.opacity = '1'; });
            }, 300);

            if (!data.subscription || !data.subscription.telegram_enabled) {
                setTimeout(showTgJoinPopup, 2000);
            }

            initDashboard(attendanceData);
        } else {
            throw new Error(data.message || 'Login failed');
        }
    } catch (err) {
        loginError.textContent = err.message;
        loginError.classList.remove('hidden');
    } finally {
        loginBtn.disabled = false;
        loginBtnText.textContent = 'Sign In';
        loginSpinner.classList.add('hidden');
    }
});

/* ─── Subscription UI state ─────────────────────────────────────────────────── */
function updateSubscriptionUI(sub) {
    isSubscribed = sub && sub.telegram_enabled;

    if (isSubscribed) {
        subBadge.classList.remove('hidden');
        subBtnText.textContent = 'Telegram Linked ✓';
        unsubBtn.classList.remove('hidden');
        sendNowBtn.classList.remove('hidden');
        alertBanner.classList.remove('hidden');
        alertBanner.classList.add('flex');
        if (tgJoinPopup) hideTgJoinPopup();
    } else {
        subBadge.classList.add('hidden');
        subBtnText.textContent = 'Get Daily Updates';
        unsubBtn.classList.add('hidden');
        sendNowBtn.classList.add('hidden');
        alertBanner.classList.add('hidden');
        alertBanner.classList.remove('flex');
    }
}

/* ─── Dashboard init ───────────────────────────────────────────────────────── */
function initDashboard(data) {
    const ov = data.overall;

    animateValue('overall-percent',  0, ov.percentage, 1200);
    animateValue('overall-attended', 0, ov.attended,   1000);
    animateValue('overall-skip',     0, ov.max_skip,   1000);
    animateValue('overall-need',     0, ov.need_to_attend, 1000);

    const statusEl = document.getElementById('overall-status');
    let statusText, statusClass;
    if (ov.percentage >= 80) {
        statusText = 'Safe'; statusClass = 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400';
    } else if (ov.percentage >= 75) {
        statusText = 'Warning'; statusClass = 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400';
    } else {
        statusText = 'Critical'; statusClass = 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400';
    }
    statusEl.textContent = statusText;
    statusEl.className   = `text-xs font-bold px-2.5 py-1 rounded-full ${statusClass}`;

    if (ov.percentage < 75) {
        dangerBarMsg.textContent = `⚠️ Danger! Your attendance is ${ov.percentage.toFixed(2)}% — below 75%. You must attend ${ov.need_to_attend} more class(es) immediately.`;
        dangerBar.classList.remove('hidden');
    } else {
        dangerBar.classList.add('hidden');
    }

    renderCharts(data);
    renderTable(data.subjects);
    initPredictor();
}

/* ─── Charts ───────────────────────────────────────────────────────────────── */
function getChartColors() {
    const isDark = document.documentElement.classList.contains('dark');
    return { grid: isDark ? '#374151' : '#e5e7eb', text: isDark ? '#9ca3af' : '#6b7280' };
}

function renderCharts(data) {
    if (pieChart)  pieChart.destroy();
    if (barChart)  barChart.destroy();

    const ov   = data.overall;
    const pcts = data.subjects.map(s => s.percentage);
    const lbls = data.subjects.map(s => s.name.length > 18 ? s.name.slice(0, 18) + '…' : s.name);
    const { grid, text } = getChartColors();

    pieChart = new Chart(document.getElementById('pieChart'), {
        type: 'doughnut',
        data: {
            labels: ['Attended', 'Missed'],
            datasets: [{
                data: [ov.attended, ov.total - ov.attended],
                backgroundColor: ['#6366f1', '#e5e7eb'],
                borderWidth: 0,
                hoverOffset: 6
            }]
        },
        options: {
            cutout: '72%',
            plugins: {
                legend: { position: 'bottom', labels: { color: text, font: { size: 12 }, padding: 16 } }
            }
        }
    });

    barChart = new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: {
            labels: lbls,
            datasets: [{
                label: 'Attendance %',
                data: pcts,
                backgroundColor: pcts.map(p => p >= 75 ? '#10b981' : '#ef4444'),
                borderRadius: 8,
                borderSkipped: false
            }, {
                label: '75% threshold',
                data: Array(pcts.length).fill(75),
                type: 'line',
                borderColor: '#f59e0b',
                borderDash: [5, 5],
                borderWidth: 2,
                pointRadius: 0,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true, max: 100,
                    grid: { color: grid },
                    ticks: { color: text, font: { size: 11 } }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: text, font: { size: 10 }, maxRotation: 45 }
                }
            },
            plugins: { legend: { labels: { color: text, font: { size: 11 } } } }
        }
    });
}

/* ─── Subject Table ─────────────────────────────────────────────────────────── */
function renderTable(subjects) {
    const list = document.getElementById('subject-list');
    if (!subjects.length) {
        list.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-400 text-sm">No subjects found.</td></tr>';
        return;
    }
    list.innerHTML = subjects.map(s => {
        const pct        = s.percentage;
        const barColor   = pct >= 80 ? 'bg-secondary' : pct >= 75 ? 'bg-warning' : 'bg-danger';
        const badgeClass = pct >= 80
            ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400'
            : pct >= 75
            ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400'
            : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400';
        const badgeText  = pct >= 80 ? 'Safe' : pct >= 75 ? 'Warning' : 'Critical';
        const icon       = pct >= 75 ? 'fa-check text-secondary' : 'fa-exclamation-triangle text-danger';

        return `
        <tr class="hover:bg-gray-50/80 dark:hover:bg-gray-900/60 transition-colors">
            <td class="px-5 py-4">
                <div class="font-medium text-sm">${s.name}</div>
                <div class="text-xs text-gray-400 mt-0.5">${s.attended} attended / ${s.total} total</div>
            </td>
            <td class="px-5 py-4">
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div class="${barColor} h-2 rounded-full prog-bar" style="width:0%" data-pct="${pct}"></div>
                </div>
            </td>
            <td class="px-5 py-4 text-right font-bold tabular-nums">${pct.toFixed(2)}%</td>
            <td class="px-5 py-4">
                <span class="text-xs font-medium flex items-center gap-1">
                    <i class="fas ${icon}"></i> ${s.action}
                </span>
            </td>
            <td class="px-5 py-4 text-center">
                <span class="text-[10px] font-bold px-2.5 py-1 rounded-full uppercase ${badgeClass}">${badgeText}</span>
            </td>
        </tr>`;
    }).join('');

    requestAnimationFrame(() => {
        document.querySelectorAll('.prog-bar').forEach(bar => {
            bar.style.width = bar.dataset.pct + '%';
        });
    });
}

/* ─── Search / Sort / Filter ────────────────────────────────────────────────── */
function applyFilters() {
    if (!attendanceData) return;
    const term   = document.getElementById('search-input').value.toLowerCase();
    const sort   = document.getElementById('sort-select').value;
    const filter = document.getElementById('filter-select').value;

    let subjects = [...attendanceData.subjects];
    if (term)                subjects = subjects.filter(s => s.name.toLowerCase().includes(term));
    if (filter === 'safe')   subjects = subjects.filter(s => s.percentage >= 75);
    if (filter === 'danger') subjects = subjects.filter(s => s.percentage < 75);
    if (sort === 'percent-desc') subjects.sort((a, b) => b.percentage - a.percentage);
    if (sort === 'percent-asc')  subjects.sort((a, b) => a.percentage - b.percentage);

    renderTable(subjects);
}

document.getElementById('search-input').addEventListener('input', applyFilters);
document.getElementById('sort-select').addEventListener('change', applyFilters);
document.getElementById('filter-select').addEventListener('change', applyFilters);

/* ─── Export PDF ────────────────────────────────────────────────────────────── */
function downloadPDF() {
    if (!attendanceData) return;
    const { jsPDF } = window.jspdf;
    const doc  = new jsPDF();
    const ov   = attendanceData.overall;

    doc.setFontSize(18);
    doc.setTextColor(99, 102, 241);
    doc.text('MITS Attendance Report', 14, 18);

    doc.setFontSize(10);
    doc.setTextColor(100);
    doc.text(`Student: ${currentRoll}   |   Generated: ${new Date().toLocaleString()}`, 14, 26);
    doc.text(`Overall: ${ov.percentage.toFixed(2)}%  |  Attended: ${ov.attended}/${ov.total}  |  Can skip: ${ov.max_skip}`, 14, 32);

    doc.autoTable({
        startY: 38,
        head: [['Subject', 'Attended', 'Total', '%', 'Recommendation', 'Status']],
        body: attendanceData.subjects.map(s => [
            s.name, s.attended, s.total, s.percentage.toFixed(2) + '%',
            s.action, s.percentage >= 75 ? 'Safe' : 'At Risk'
        ]),
        headStyles: { fillColor: [99, 102, 241], fontSize: 9 },
        bodyStyles: { fontSize: 8 },
        alternateRowStyles: { fillColor: [245, 247, 250] },
        didParseCell: (data) => {
            if (data.column.index === 5 && data.section === 'body') {
                data.cell.styles.textColor = data.cell.text[0] === 'Safe'
                    ? [16, 185, 129] : [239, 68, 68];
                data.cell.styles.fontStyle = 'bold';
            }
        }
    });

    doc.save(`MITS_Attendance_${currentRoll}_${new Date().toISOString().slice(0,10)}.pdf`);
    showToast('PDF downloaded!', 'success');
}

/* ─── Export CSV ────────────────────────────────────────────────────────────── */
function downloadCSV() {
    if (!attendanceData) return;
    let csv = 'Subject,Attended,Total,Percentage,Recommendation,Status\n';
    attendanceData.subjects.forEach(s => {
        csv += `"${s.name}",${s.attended},${s.total},${s.percentage.toFixed(2)},"${s.action}","${s.percentage >= 75 ? 'Safe' : 'At Risk'}"\n`;
    });
    const a = Object.assign(document.createElement('a'), {
        href:     URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
        download: `MITS_Attendance_${currentRoll}.csv`
    });
    a.click();
    showToast('CSV downloaded!', 'success');
}

['download-pdf', 'sidebar-download-pdf'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', downloadPDF);
});
['download-csv', 'sidebar-download-csv'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', downloadCSV);
});
['print-btn', 'sidebar-print-btn'].forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => window.print());
});

/* ─── Telegram Modal ────────────────────────────────────────────────────────── */
const tgOverlay      = document.getElementById('telegram-modal-overlay');
const tgEnableBtn    = document.getElementById('tg-enable-btn');
const tgEnableBtnTxt = document.getElementById('tg-enable-btn-text');
const tgEnableSpin   = document.getElementById('tg-enable-spinner');
const tgChatInput    = document.getElementById('tg-chat-id-input');
const tgSuccessMsg   = document.getElementById('tg-success-msg');
const tgErrorMsg     = document.getElementById('tg-error-msg');
const tgSubForm      = document.getElementById('tg-subscribe-form');

function openTelegramModal() {
    tgOverlay.classList.remove('hidden');
    tgSuccessMsg.classList.add('hidden');
    tgErrorMsg.classList.add('hidden');
    tgSubForm.classList.remove('hidden');
    tgChatInput.value = '';
}

function closeTelegramModal() {
    tgOverlay.classList.add('hidden');
}

document.getElementById('tg-modal-close')?.addEventListener('click', closeTelegramModal);
tgOverlay?.addEventListener('click', (e) => { if (e.target === tgOverlay) closeTelegramModal(); });

getDailyBtn.addEventListener('click', () => {
    if (!currentRoll) { showToast('Please log in first', 'warning'); return; }
    openTelegramModal();
});

tgEnableBtn.addEventListener('click', async () => {
    const chatId = tgChatInput.value.trim();
    if (!chatId) { showToast('Please enter your Telegram Chat ID', 'warning'); return; }

    tgEnableBtn.disabled = true;
    tgEnableBtnTxt.textContent = 'Enabling…';
    tgEnableSpin.classList.remove('hidden');
    tgErrorMsg.classList.add('hidden');

    try {
        const res  = await fetch('/api/telegram-subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll: currentRoll, password: currentPassword, chat_id: chatId })
        });
        const data = await res.json();

        if (data.status === 'success') {
            tgSubForm.classList.add('hidden');
            tgSuccessMsg.classList.remove('hidden');
            updateSubscriptionUI({ telegram_enabled: true });
            showToast('Telegram alerts enabled! 🎉', 'success');
        } else {
            tgErrorMsg.textContent = data.message || 'Something went wrong.';
            tgErrorMsg.classList.remove('hidden');
        }
    } catch (err) {
        tgErrorMsg.textContent = err.message || 'Network error.';
        tgErrorMsg.classList.remove('hidden');
    } finally {
        tgEnableBtn.disabled = false;
        tgEnableBtnTxt.textContent = 'Enable Daily Updates';
        tgEnableSpin.classList.add('hidden');
    }
});

/* ─── Telegram Join Popup ───────────────────────────────────────────────────── */
const tgJoinPopup = document.getElementById('tg-join-popup');
let tgJoinTimer;

function showTgJoinPopup() {
    if (isSubscribed) return;
    tgJoinPopup.classList.remove('hidden');
    tgJoinPopup.style.transition = 'opacity 0.4s, transform 0.4s';
    tgJoinPopup.style.opacity = '0';
    tgJoinPopup.style.transform = 'translateY(20px)';
    requestAnimationFrame(() => requestAnimationFrame(() => {
        tgJoinPopup.style.opacity = '1';
        tgJoinPopup.style.transform = 'translateY(0)';
    }));
    tgJoinTimer = setTimeout(hideTgJoinPopup, 10000);
}

function hideTgJoinPopup() {
    clearTimeout(tgJoinTimer);
    tgJoinPopup.style.opacity = '0';
    tgJoinPopup.style.transform = 'translateY(20px)';
    setTimeout(() => tgJoinPopup.classList.add('hidden'), 400);
}

document.getElementById('tg-join-popup-close')?.addEventListener('click', hideTgJoinPopup);
document.getElementById('tg-join-popup-skip')?.addEventListener('click', hideTgJoinPopup);
document.getElementById('tg-join-popup-yes')?.addEventListener('click', () => {
    hideTgJoinPopup();
    openTelegramModal();
});

/* ─── Unsubscribe ───────────────────────────────────────────────────────────── */
async function doUnsubscribe() {
    if (!currentRoll) return;
    try {
        await fetch('/api/telegram-unsubscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll: currentRoll })
        });
        updateSubscriptionUI({ telegram_enabled: false });
        showToast('Daily updates disabled.', 'info');
    } catch (err) {
        showToast('Failed to unsubscribe.', 'error');
    }
}

unsubBtn.addEventListener('click', doUnsubscribe);
document.getElementById('unsub-header-btn')?.addEventListener('click', doUnsubscribe);

/* ─── Send Now ──────────────────────────────────────────────────────────────── */
sendNowBtn.addEventListener('click', async () => {
    if (!currentRoll) return;
    sendNowBtn.disabled = true;
    sendNowBtn.innerHTML = '<svg class="spin w-4 h-4 inline mr-1" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"/><path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="4" stroke-linecap="round" class="opacity-75"/></svg> Sending…';
    try {
        const res  = await fetch('/api/send-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ roll: currentRoll, password: currentPassword })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Attendance report sent to Telegram! 📊', 'success');
        } else {
            showToast(data.message || 'Failed to send.', 'error');
        }
    } catch {
        showToast('Failed to send report.', 'error');
    } finally {
        sendNowBtn.disabled = false;
        sendNowBtn.innerHTML = '<i class="fas fa-paper-plane mr-1"></i> Send Report Now';
    }
});

/* ─── Logout ────────────────────────────────────────────────────────────────── */
document.getElementById('logout-btn').addEventListener('click', () => window.location.reload());

/* ─── Attendance Predictor ──────────────────────────────────────────────────── */
const predSkipInput     = document.getElementById('pred-skip-input');
const predDec           = document.getElementById('pred-dec');
const predInc           = document.getElementById('pred-inc');
const predSubjectSelect = document.getElementById('pred-subject-select');
const predNewPct        = document.getElementById('pred-new-pct');
const predDelta         = document.getElementById('pred-delta');
const predCanSkip       = document.getElementById('pred-can-skip');
const predStatus        = document.getElementById('pred-status');
const predSubjectTable  = document.getElementById('pred-subject-table');
const predSubjectRows   = document.getElementById('pred-subject-rows');
const predEmptyMsg      = document.getElementById('pred-empty-msg');

function runPredictor() {
    if (!attendanceData) return;
    const skip    = Math.max(0, parseInt(predSkipInput.value) || 0);
    const target  = predSubjectSelect.value;
    const overall = attendanceData.overall;
    const subjects = attendanceData.subjects;

    let newAttended = overall.attended;
    let newTotal    = overall.total;
    if (target === 'all') {
        newTotal = overall.total + skip;
    } else {
        newTotal = overall.total + skip;
    }

    const newPct  = newTotal > 0 ? (newAttended / newTotal) * 100 : 0;
    const delta   = newPct - overall.percentage;
    const canSkip = Math.max(0, Math.floor(newAttended / 0.75 - newTotal));

    predNewPct.textContent = newPct.toFixed(1) + '%';
    predNewPct.className   = 'text-2xl font-bold ' + (newPct >= 75 ? 'text-green-500' : 'text-red-500');
    predDelta.textContent  = (delta >= 0 ? '+' : '') + delta.toFixed(1) + '%';
    predDelta.className    = 'text-2xl font-bold ' + (delta >= 0 ? 'text-green-500' : 'text-red-500');
    predCanSkip.textContent = canSkip;

    if (newPct >= 85) {
        predStatus.textContent = 'Safe Zone';
        predStatus.className   = 'text-sm font-bold mt-1 text-green-500';
    } else if (newPct >= 75) {
        predStatus.textContent = 'Borderline';
        predStatus.className   = 'text-sm font-bold mt-1 text-amber-500';
    } else {
        predStatus.textContent = 'Below 75% ⚠';
        predStatus.className   = 'text-sm font-bold mt-1 text-red-500';
    }

    if (skip === 0 || target === 'all') {
        predSubjectTable.classList.add('hidden');
        return;
    }
    predSubjectTable.classList.remove('hidden');

    predSubjectRows.innerHTML = subjects.map(s => {
        const sSkip    = (target === s.name) ? skip : 0;
        const sNewTotal = s.total + sSkip;
        const sNewPct   = sNewTotal > 0 ? (s.attended / sNewTotal) * 100 : 0;
        const sDelta    = sNewPct - s.percentage;
        const dropsBelow = s.percentage >= 75 && sNewPct < 75;
        return `<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors ${dropsBelow ? 'bg-red-50 dark:bg-red-900/10' : ''}">
            <td class="px-4 py-2.5 font-medium text-xs max-w-[180px] truncate" title="${s.name}">${s.name}</td>
            <td class="px-4 py-2.5 text-center font-mono text-xs ${s.percentage >= 75 ? 'text-green-600' : 'text-red-500'}">${s.percentage.toFixed(1)}%</td>
            <td class="px-4 py-2.5 text-center font-mono text-xs font-bold ${sNewPct >= 75 ? 'text-green-600' : 'text-red-500'}">${sNewPct.toFixed(1)}%</td>
            <td class="px-4 py-2.5 text-center text-xs font-semibold ${sDelta >= 0 ? 'text-green-500' : 'text-red-500'}">
                ${sDelta >= 0 ? '+' : ''}${sDelta.toFixed(1)}%
                ${dropsBelow ? '<span class="ml-1 text-red-400 font-bold">⚠</span>' : ''}
            </td>
        </tr>`;
    }).join('');
}

function initPredictor() {
    if (!attendanceData) return;
    predEmptyMsg.classList.add('hidden');
    predSubjectSelect.innerHTML = '<option value="all">All subjects (equally)</option>';
    attendanceData.subjects.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.name;
        opt.textContent = s.name;
        predSubjectSelect.appendChild(opt);
    });
    runPredictor();
}

predDec.addEventListener('click', () => {
    const v = parseInt(predSkipInput.value) || 0;
    if (v > 0) { predSkipInput.value = v - 1; runPredictor(); }
});
predInc.addEventListener('click', () => {
    predSkipInput.value = (parseInt(predSkipInput.value) || 0) + 1;
    runPredictor();
});
predSkipInput.addEventListener('input', runPredictor);
predSubjectSelect.addEventListener('change', runPredictor);

/* ─── PWA ───────────────────────────────────────────────────────────────────── */
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
}

let _deferredInstallPrompt = null;
const installBtn     = document.getElementById('install-app-btn');
const installBtnText = document.getElementById('install-btn-text');

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferredInstallPrompt = e;
    if (installBtn) installBtn.disabled = false;
});

installBtn?.addEventListener('click', async () => {
    if (!_deferredInstallPrompt) {
        showToast('Open your browser menu → "Add to Home Screen" to install.', 'info');
        return;
    }
    _deferredInstallPrompt.prompt();
    const { outcome } = await _deferredInstallPrompt.userChoice;
    if (outcome === 'accepted') {
        installBtnText.textContent = 'App Installed ✓';
        installBtn.classList.add('opacity-60', 'cursor-default');
        installBtn.disabled = true;
        showToast('MITS Attendance installed on your device! 🎉', 'success');
    }
    _deferredInstallPrompt = null;
});

if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
    if (installBtnText) installBtnText.textContent = 'App Already Installed ✓';
    if (installBtn) {
        installBtn.disabled = true;
        installBtn.classList.add('opacity-60', 'cursor-default');
    }
}

/* =====================================================================
   main.js - shared front-end behaviour
   theme switch | mobile menu | dropdowns | toasts | add-to-cart
   ===================================================================== */

/* ------------------------------------------------------------- Theme */
(function initTheme() {
    const saved = localStorage.getItem('shopsphere-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);

    document.addEventListener('DOMContentLoaded', () => {
        const btn = document.getElementById('themeBtn');
        if (!btn) return;
        const paint = () =>
            btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
        paint();
        btn.addEventListener('click', () => {
            const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('shopsphere-theme', next);
            paint();
        });
    });
})();

/* ------------------------------------------------------------ Toasts */
function toast(message, type = 'info', timeout = 3600) {
    let area = document.getElementById('toastArea');
    if (!area) {
        area = document.createElement('div');
        area.id = 'toastArea';
        area.className = 'toast-area';
        document.body.appendChild(area);
    }
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.innerHTML = '<span></span><button aria-label="Dismiss">&times;</button>';
    el.firstChild.textContent = message;
    el.querySelector('button').onclick = () => el.remove();
    area.appendChild(el);
    setTimeout(() => {
        el.classList.add('hide');
        setTimeout(() => el.remove(), 300);
    }, timeout);
}

/* ------------------------------------------------------- Cart helpers */
function setCartBadge(count) {
    const badge = document.getElementById('cartBadge');
    if (!badge) return;
    badge.textContent = count;
    badge.hidden = count === 0;
    badge.classList.remove('pop');
    void badge.offsetWidth;          // restart the animation
    badge.classList.add('pop');
}

async function postJSON(url, body) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
    return { res, data };
}

/* --------------------------------------------------------- DOM wiring */
document.addEventListener('DOMContentLoaded', () => {

    /* mobile menu */
    const burger = document.getElementById('burger');
    const menu = document.getElementById('mobileMenu');
    if (burger && menu) burger.addEventListener('click', () => menu.classList.toggle('open'));

    /* account dropdown */
    const dd = document.getElementById('userMenu');
    if (dd) {
        dd.querySelector('button').addEventListener('click', (e) => {
            e.stopPropagation();
            dd.classList.toggle('open');
        });
        document.addEventListener('click', () => dd.classList.remove('open'));
    }

    /* show / hide password */
    document.querySelectorAll('.pw-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = document.getElementById(btn.dataset.target);
            input.type = input.type === 'password' ? 'text' : 'password';
        });
    });

    /* add to cart - works on every product card and the detail page */
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', async () => {
            const qtyEl = btn.dataset.qtyFrom ? document.getElementById(btn.dataset.qtyFrom) : null;
            const quantity = qtyEl ? parseInt(qtyEl.textContent, 10) : 1;
            const label = btn.textContent;

            btn.disabled = true;
            btn.textContent = 'Adding...';

            const { res, data } = await postJSON('/cart/api/add', {
                product_id: btn.dataset.id, quantity,
            });

            if (res.status === 401 && data.login_required) {
                toast(data.message, 'warning');
                setTimeout(() => location.href = '/login?next=' + encodeURIComponent(location.pathname), 900);
                return;
            }

            btn.disabled = false;
            btn.textContent = label;

            if (data.ok) {
                setCartBadge(data.count);
                toast(data.message, 'success');
                btn.textContent = '✓ Added';
                setTimeout(() => { btn.textContent = label; }, 1400);
            } else {
                toast(data.message || 'Could not add this item', 'danger');
            }
        });
    });

    /* auto-dismiss server-rendered flash messages */
    document.querySelectorAll('#toastArea .toast').forEach((el, i) => {
        setTimeout(() => {
            el.classList.add('hide');
            setTimeout(() => el.remove(), 300);
        }, 4200 + i * 300);
    });
});

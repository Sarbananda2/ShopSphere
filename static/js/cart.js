/* =====================================================================
   cart.js - quantity stepper, remove, coupon (all without a page reload)
   ===================================================================== */

function money(value) {
    return Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function applyResponse(data) {
    setCartBadge(data.count);

    const box = document.getElementById('summaryBox');
    if (box && data.summary_html) box.innerHTML = data.summary_html;

    // Refresh each visible line total; drop rows that are gone.
    document.querySelectorAll('[data-row]').forEach(row => {
        const id = row.dataset.row;
        if (data.lines && Object.prototype.hasOwnProperty.call(data.lines, id)) {
            const cell = row.querySelector('[data-line="' + id + '"]');
            if (cell) cell.textContent = '₹' + money(data.lines[id]);
        } else {
            row.remove();
        }
    });

    // Highlight the coupon badge that the server actually applied.
    if (data.summary) markCoupon(data.summary.coupon);

    if (data.empty) setTimeout(() => location.reload(), 500);
}

function markCoupon(code) {
    document.querySelectorAll('[data-coupon]').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.coupon === code);
    });
}

document.addEventListener('DOMContentLoaded', () => {

    /* ---------------------------------------------- quantity + / - */
    document.querySelectorAll('.cart-step').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const out = document.querySelector('[data-qty="' + id + '"]');
            const next = parseInt(out.textContent, 10) + parseInt(btn.dataset.delta, 10);

            if (next < 1) {
                if (!confirm('Remove this item from your cart?')) return;
                return removeItem(id);
            }

            btn.disabled = true;
            const { data } = await postJSON('/cart/api/update', { product_id: id, quantity: next });
            btn.disabled = false;

            if (data.ok) {
                out.textContent = next;
                applyResponse(data);
            } else {
                toast(data.message || 'Could not update the cart', 'danger');
            }
        });
    });

    /* -------------------------------------------------------- remove */
    document.querySelectorAll('.cart-remove').forEach(btn => {
        btn.addEventListener('click', () => removeItem(btn.dataset.id));
    });

    /* -------------------------------------------------------- coupon */
    const couponBtn = document.getElementById('couponBtn');
    if (couponBtn) {
        couponBtn.addEventListener('click', async () => {
            const input = document.getElementById('couponInput');
            couponBtn.disabled = true;
            const { data } = await postJSON('/cart/api/coupon', { code: input.value.trim() });
            couponBtn.disabled = false;

            applyResponse(data);
            toast(data.message, data.ok ? 'success' : 'danger');
            if (!data.ok) input.value = '';
        });
    }

    /* ---------------------------------------- coupon quick-pick badges */
    document.querySelectorAll('[data-coupon]').forEach(chip => {
        chip.addEventListener('click', () => {
            const input = document.getElementById('couponInput');
            if (!input) return;
            input.value = chip.dataset.coupon;
            input.focus();
        });
    });
});

async function removeItem(id) {
    const { data } = await postJSON('/cart/api/remove', { product_id: id });
    if (data.ok) {
        applyResponse(data);
        toast(data.message, 'info');
    } else {
        toast(data.message || 'Could not remove the item', 'danger');
    }
}

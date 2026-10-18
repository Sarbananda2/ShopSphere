/* =====================================================================
   payment.js - method switching, live card preview, client-side checks,
                OTP box behaviour
   ===================================================================== */

/* Luhn check mirrored from payment_gateway.py so the user gets instant
   feedback; the server always validates again before charging. */
function luhnValid(number) {
    const digits = number.replace(/\D/g, '');
    if (digits.length < 12) return false;
    let sum = 0;
    const parity = digits.length % 2;
    for (let i = 0; i < digits.length; i++) {
        let d = parseInt(digits[i], 10);
        if (i % 2 === parity) { d *= 2; if (d > 9) d -= 9; }
        sum += d;
    }
    return sum % 10 === 0;
}

function network(number) {
    const n = number.replace(/\D/g, '');
    if (/^4/.test(n)) return 'VISA';
    if (/^5[1-5]/.test(n) || /^2[2-7]/.test(n)) return 'MASTERCARD';
    if (/^3[47]/.test(n)) return 'AMEX';
    if (/^6/.test(n)) return 'RUPAY';
    return 'CARD';
}

document.addEventListener('DOMContentLoaded', () => {

    /* ------------------------------------------------ method switch */
    const methods = document.querySelectorAll('.method');
    methods.forEach(label => {
        label.addEventListener('click', () => {
            const chosen = label.dataset.method;
            methods.forEach(m => m.classList.toggle('selected', m === label));
            document.querySelectorAll('.method-body').forEach(body => {
                body.classList.toggle('show', body.dataset.body === chosen);
            });
        });
    });

    /* ------------------------------------------- live card preview */
    const num = document.getElementById('card_number');
    const name = document.getElementById('card_name');
    const month = document.getElementById('expiry_month');
    const year = document.getElementById('expiry_year');
    const hint = document.getElementById('cardHint');

    const paintExpiry = () => {
        if (!month || !year) return;
        document.getElementById('cardExpPreview').textContent =
            month.value + '/' + String(year.value).slice(-2);
    };

    if (num) {
        num.addEventListener('input', () => {
            // group digits in blocks of four as the user types
            const digits = num.value.replace(/\D/g, '').slice(0, 19);
            num.value = digits.replace(/(.{4})/g, '$1 ').trim();

            document.getElementById('cardNumPreview').textContent =
                (num.value || '•••• •••• •••• ••••');
            document.getElementById('netLabel').textContent = digits ? network(digits) : 'CARD';

            if (digits.length >= 12) {
                const ok = luhnValid(digits);
                hint.textContent = ok ? '✓ Card number looks valid' : '✗ Invalid card number';
                hint.style.color = ok ? 'var(--ok)' : 'var(--err)';
                num.classList.toggle('err', !ok);
            } else {
                hint.textContent = 'Test card: 4111 1111 1111 1111 (any future expiry, any CVV)';
                hint.style.color = '';
                num.classList.remove('err');
            }
        });
    }

    if (name) {
        name.addEventListener('input', () => {
            document.getElementById('cardNamePreview').textContent =
                name.value.toUpperCase() || 'YOUR NAME';
        });
    }
    if (month) month.addEventListener('change', paintExpiry);
    if (year) year.addEventListener('change', paintExpiry);
    paintExpiry();

    /* ------------------------------------------------ UPI shortcuts */
    document.querySelectorAll('.upi-suffix').forEach(btn => {
        btn.addEventListener('click', () => {
            const field = document.getElementById('upi_id');
            field.value = (field.value.split('@')[0] || 'student') + btn.dataset.suffix;
            field.focus();
        });
    });

    /* ------------------------------------- client-side guard on submit */
    const form = document.getElementById('payForm');
    if (form) {
        form.addEventListener('submit', (e) => {
            const method = form.querySelector('input[name="method"]:checked').value;

            if (method === 'CARD') {
                const digits = (num.value || '').replace(/\D/g, '');
                const cvv = document.getElementById('cvv').value;
                if (!luhnValid(digits)) {
                    e.preventDefault();
                    return toast('Please enter a valid card number', 'danger');
                }
                if (!/^\d{3,4}$/.test(cvv)) {
                    e.preventDefault();
                    return toast('CVV must be 3 or 4 digits', 'danger');
                }
            }
            if (method === 'UPI') {
                const vpa = document.getElementById('upi_id').value.trim();
                if (!/^[\w.\-]{3,}@[a-zA-Z]{3,}$/.test(vpa)) {
                    e.preventDefault();
                    return toast('Enter a valid UPI ID, e.g. name@okhdfcbank', 'danger');
                }
            }
            if (method === 'NETBANKING' && !document.getElementById('bank_code').value) {
                e.preventDefault();
                return toast('Please choose your bank', 'danger');
            }

            const btn = document.getElementById('payBtn');
            btn.disabled = true;
            btn.textContent = 'Contacting the bank...';
        });
    }

    /* ------------------------------------------------------- OTP page */
    const boxes = document.querySelectorAll('.otp-box');
    if (boxes.length) {
        boxes[0].focus();
        boxes.forEach((box, i) => {
            box.addEventListener('input', () => {
                box.value = box.value.replace(/\D/g, '');
                if (box.value && i < boxes.length - 1) boxes[i + 1].focus();
                collectOtp();
            });
            box.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !box.value && i > 0) boxes[i - 1].focus();
            });
            box.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = (e.clipboardData.getData('text') || '').replace(/\D/g, '');
                boxes.forEach((b, j) => b.value = text[j] || '');
                collectOtp();
                boxes[Math.min(text.length, boxes.length - 1)].focus();
            });
        });

        function collectOtp() {
            document.getElementById('otpValue').value =
                Array.from(boxes).map(b => b.value).join('');
        }

        document.getElementById('otpForm').addEventListener('submit', (e) => {
            collectOtp();
            if (document.getElementById('otpValue').value.length !== 6) {
                e.preventDefault();
                toast('Please enter all 6 digits of the OTP', 'danger');
            }
        });
    }
});

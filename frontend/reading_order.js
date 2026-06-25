/**
 * Порядок чтения: нумерация, перестановка, попап «№», иконки chrome-кнопок.
 */
(function () {
    const ORDER_KEY = 'reading_order';

    function getOrder(item, key) {
        key = key || ORDER_KEY;
        const v = item[key];
        return typeof v === 'number' && v > 0 ? v : null;
    }

    function ensureOrders(items, key) {
        key = key || ORDER_KEY;
        if (!items || !items.length) return;
        const missing = items.filter((it) => getOrder(it, key) == null);
        if (!missing.length && items.length === 1) return;
        if (missing.length === items.length) {
            items.forEach((it, i) => {
                it[key] = i + 1;
            });
            return;
        }
        let next = 1;
        const used = new Set(items.map((it) => getOrder(it, key)).filter((v) => v != null));
        while (used.has(next)) next++;
        missing.forEach((it) => {
            while (used.has(next)) next++;
            it[key] = next;
            used.add(next);
            next++;
        });
    }

    function normalizeOrders(items, key) {
        key = key || ORDER_KEY;
        if (!items || !items.length) return;
        ensureOrders(items, key);
        const sorted = [...items].sort((a, b) => a[key] - b[key]);
        sorted.forEach((it, i) => {
            it[key] = i + 1;
        });
    }

    function sortItemsByOrder(items, key) {
        key = key || ORDER_KEY;
        ensureOrders(items, key);
        items.sort((a, b) => a[key] - b[key]);
    }

    function setItemOrder(items, itemId, newOrder, getId, key) {
        key = key || ORDER_KEY;
        getId = getId || ((it) => it.id);
        if (!items || !items.length) return false;
        ensureOrders(items, key);
        sortItemsByOrder(items, key);
        const target = items.find((it) => getId(it) === itemId);
        if (!target) return false;
        newOrder = Math.max(1, Math.min(items.length, Math.round(Number(newOrder)) || 1));
        const oldOrder = target[key];
        if (oldOrder === newOrder) return true;
        items.forEach((it) => {
            if (getId(it) === itemId) return;
            if (oldOrder < newOrder) {
                if (it[key] > oldOrder && it[key] <= newOrder) it[key] -= 1;
            } else if (it[key] >= newOrder && it[key] < oldOrder) {
                it[key] += 1;
            }
        });
        target[key] = newOrder;
        sortItemsByOrder(items, key);
        normalizeOrders(items, key);
        return true;
    }

    function moveItem(items, itemId, delta, getId, key) {
        key = key || ORDER_KEY;
        getId = getId || ((it) => it.id);
        ensureOrders(items, key);
        sortItemsByOrder(items, key);
        const idx = items.findIndex((it) => getId(it) === itemId);
        if (idx < 0) return false;
        const newIdx = idx + delta;
        if (newIdx < 0 || newIdx >= items.length) return false;
        return setItemOrder(items, itemId, newIdx + 1, getId, key);
    }

    let popupEl = null;
    let popupCleanup = null;

    function ensurePopup() {
        if (popupEl) return popupEl;
        popupEl = document.createElement('div');
        popupEl.id = 'ro-popup';
        popupEl.className = 'ro-popup';
        popupEl.innerHTML =
            '<div class="ro-popup-card">' +
            '<div class="ro-popup-title">Номер в очереди</div>' +
            '<input type="number" class="ro-popup-input inp" min="1" step="1" />' +
            '<div class="ro-popup-actions">' +
            '<button type="button" class="btn btn-s ro-popup-cancel">Отмена</button>' +
            '<button type="button" class="btn btn-p ro-popup-ok">OK</button>' +
            '</div></div>';
        document.body.appendChild(popupEl);
        popupEl.addEventListener('click', (e) => {
            if (e.target === popupEl) closeOrderPopup();
        });
        return popupEl;
    }

    function closeOrderPopup() {
        if (popupCleanup) {
            popupCleanup();
            popupCleanup = null;
        }
        if (popupEl) popupEl.style.display = 'none';
    }

    function showOrderPopup(opts) {
        const el = ensurePopup();
        const input = el.querySelector('.ro-popup-input');
        const okBtn = el.querySelector('.ro-popup-ok');
        const cancelBtn = el.querySelector('.ro-popup-cancel');
        const max = Math.max(1, opts.max || 1);
        const current = Math.max(1, Math.min(max, opts.current || 1));

        input.value = String(current);
        input.min = '1';
        input.max = String(max);
        el.style.display = 'flex';

        const rect = opts.anchorRect;
        if (rect) {
            const left = Math.min(rect.left, window.innerWidth - 240);
            const top = rect.bottom + 6;
            el.style.left = left + 'px';
            el.style.top = top + 'px';
        } else {
            el.style.left = '50%';
            el.style.top = '40%';
            el.style.transform = 'translate(-50%, -50%)';
        }

        const apply = () => {
            const n = parseInt(input.value, 10);
            if (!Number.isFinite(n) || n < 1 || n > max) {
                input.focus();
                return;
            }
            if (opts.onApply) opts.onApply(n);
            closeOrderPopup();
        };

        const onKey = (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                apply();
            }
            if (e.key === 'Escape') closeOrderPopup();
        };

        okBtn.onclick = apply;
        cancelBtn.onclick = closeOrderPopup;
        input.onkeydown = onKey;
        popupCleanup = () => {
            okBtn.onclick = null;
            cancelBtn.onclick = null;
            input.onkeydown = null;
            el.style.transform = '';
        };
        setTimeout(() => input.select(), 0);
    }

    const SVG_NS = 'http://www.w3.org/2000/svg';

    function iconSvg(pathD, secondD) {
        const svg = document.createElementNS(SVG_NS, 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('aria-hidden', 'true');
        svg.classList.add('chrome-icon');
        [pathD, secondD].filter(Boolean).forEach((d) => {
            const p = document.createElementNS(SVG_NS, 'path');
            p.setAttribute('d', d);
            svg.appendChild(p);
        });
        return svg;
    }

    const Icons = {
        close: () => iconSvg('M6 18L18 6M6 6l12 12'),
        refresh: () => iconSvg(
            'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15'
        ),
        chevronUp: () => iconSvg('M5 15l7-7 7 7'),
        chevronDown: () => iconSvg('M19 9l-7 7-7-7'),
    };

    function mountIconButton(btn, iconName, label) {
        if (!btn) return;
        btn.innerHTML = '';
        btn.title = label;
        btn.setAttribute('aria-label', label);
        btn.classList.remove('chrome-btn-text');
        if (iconName === 'order') {
            btn.textContent = '№';
            btn.classList.add('chrome-btn-text');
            return;
        }
        if (Icons[iconName]) btn.appendChild(Icons[iconName]());
    }

    window.ReadingOrder = {
        ORDER_KEY,
        getOrder,
        ensureOrders,
        normalizeOrders,
        sortItemsByOrder,
        setItemOrder,
        moveItem,
        showOrderPopup,
        closeOrderPopup,
        mountIconButton,
        Icons,
    };
})();

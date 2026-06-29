/**
 * Simple prev/next counter for batch page lists (Split pages, etc.).
 */
(function () {
    function createNav(options) {
        const state = {
            items: [],
            index: 0,
            onChange: options.onChange || (() => {}),
            labelEl: options.labelEl || null,
            prevBtn: options.prevBtn || null,
            nextBtn: options.nextBtn || null,
        };

        function updateUi() {
            const total = state.items.length;
            const i = state.index;
            if (state.labelEl) {
                state.labelEl.textContent = total
                    ? `Стр. ${i + 1} / ${total}`
                    : (options.emptyLabel || 'Нет страниц');
            }
            if (state.prevBtn) state.prevBtn.disabled = i <= 0 || total === 0;
            if (state.nextBtn) state.nextBtn.disabled = i >= total - 1 || total === 0;
        }

        return {
            setItems(items, startIndex) {
                state.items = Array.isArray(items) ? items.slice() : [];
                state.index = Math.max(0, Math.min(startIndex || 0, state.items.length - 1));
                updateUi();
                if (state.items.length) state.onChange(state.items[state.index], state.index);
            },
            current() {
                return state.items[state.index];
            },
            index() {
                return state.index;
            },
            prev() {
                if (state.index <= 0) return null;
                state.index -= 1;
                updateUi();
                const item = state.items[state.index];
                state.onChange(item, state.index);
                return item;
            },
            next() {
                if (state.index >= state.items.length - 1) return null;
                state.index += 1;
                updateUi();
                const item = state.items[state.index];
                state.onChange(item, state.index);
                return item;
            },
            updateUi,
        };
    }

    window.ComicSplitPanelNav = { createNav };
})();

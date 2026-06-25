/**
 * Story Analyzer — Stage 2a: Bubble OCR corrector (Konva + HITL).
 */
(function () {
    const RO = () => window.ReadingOrder;
    const BUBBLE_COLORS = {
        speech: '#60a5fa',
        thought: '#c084fc',
        sfx: '#f472b6',
        narration: '#4ade80',
    };

    const S2 = {
        project: '',
        panelsDir: '',
        document: null,
        panelPaths: {},
        panelIndex: 0,
        selBubbleId: null,
        scale: 1,
        imgW: 0,
        imgH: 0,
        frameLayouts: {},
        reocrBusy: false,
    };

    let stage2a, imgLayer2a, bubbleLayer2a, kImg2a;
    let isPanning2a = false;
    let panStart2a = { x: 0, y: 0 };
    let panOrigin2a = { x: 0, y: 0 };
    let frameDrag2a = null;
    let frameResize2a = null;

    const $ = (id) => document.getElementById(id);

    function normBbox(bbox) {
        return bbox.map((v) => Math.round(Number(v)));
    }

    function readUiFields() {
        return {
            project: ($('s2a-project') || {}).value?.trim() || '',
            panelsDir: ($('s2a-panels-dir') || {}).value?.trim() || '',
        };
    }

    function syncFieldsFromUi() {
        const f = readUiFields();
        if (f.project) S2.project = f.project;
        if (f.panelsDir) S2.panelsDir = f.panelsDir;
    }

    function formatApiError(data, fallback) {
        if (!data) return fallback;
        if (typeof data.detail === 'string') return data.detail;
        if (Array.isArray(data.detail)) {
            return data.detail.map((e) => e.msg || JSON.stringify(e)).join('; ');
        }
        if (data.errors) return JSON.stringify(data.errors);
        return fallback;
    }

    function toast(msg, kind) {
        if (window.toast) window.toast(msg, kind);
    }

    function setStatus2a(text) {
        if (window.setStatus) window.setStatus(text, '');
    }

    function bubbleIdOf(b) {
        return b.bubble_id;
    }

    function sortPanelBubbles(panel) {
        if (!panel || !RO()) return;
        RO().ensureOrders(panel.bubbles, 'reading_order');
        RO().sortItemsByOrder(panel.bubbles, 'reading_order');
    }

    function normalizeDocument(doc) {
        if (!doc || !RO()) return;
        (doc.panels || []).forEach((panel) => sortPanelBubbles(panel));
    }

    function currentPanel() {
        if (!S2.document || !S2.document.panels.length) return null;
        return S2.document.panels[S2.panelIndex] || null;
    }

    function bubbleById(id) {
        const panel = currentPanel();
        if (!panel || !id) return null;
        return panel.bubbles.find((b) => b.bubble_id === id) || null;
    }

    function layerToImg(lx, ly) {
        return { x: lx / S2.scale, y: ly / S2.scale };
    }

    function invPoint(pos) {
        return {
            x: (pos.x - imgLayer2a.x()) / S2.scale,
            y: (pos.y - imgLayer2a.y()) / S2.scale,
        };
    }

    function resizeBubbleBbox(b, cornerIdx, ix, iy) {
        const { imgW, imgH } = S2;
        ix = Math.round(Math.max(0, Math.min(ix, imgW)));
        iy = Math.round(Math.max(0, Math.min(iy, imgH)));
        let [bx1, by1, bx2, by2] = b.bbox;
        if (cornerIdx === 0) {
            bx1 = Math.min(ix, bx2 - 10);
            by1 = Math.min(iy, by2 - 10);
        } else if (cornerIdx === 1) {
            bx2 = Math.max(ix, bx1 + 10);
            by1 = Math.min(iy, by2 - 10);
        } else if (cornerIdx === 2) {
            bx2 = Math.max(ix, bx1 + 10);
            by2 = Math.max(iy, by1 + 10);
        } else if (cornerIdx === 3) {
            bx1 = Math.min(ix, bx2 - 10);
            by2 = Math.max(iy, by1 + 10);
        }
        b.bbox = normBbox([bx1, by1, bx2, by2]);
    }

    function syncBubbleKonva(b, fill, box, badge, handles) {
        const [x1, y1, x2, y2] = b.bbox;
        const sp = { x: x1 * S2.scale, y: y1 * S2.scale };
        const pw = (x2 - x1) * S2.scale;
        const ph = (y2 - y1) * S2.scale;
        fill.position({ x: sp.x, y: sp.y });
        fill.size({ width: pw, height: ph });
        box.position({ x: sp.x, y: sp.y });
        box.size({ width: pw, height: ph });
        badge.position({ x: sp.x + 2, y: sp.y + 2 });
        badge.text(String(b.reading_order || ''));
        if (handles) {
            const coords = [
                [x1, y1], [x2, y1], [x2, y2], [x1, y2],
            ];
            handles.forEach((h, ci) => {
                h.position({ x: coords[ci][0] * S2.scale - 6, y: coords[ci][1] * S2.scale - 6 });
            });
        }
        bubbleLayer2a.batchDraw();
    }

    const FRAME_MIN_W = 140;
    const FRAME_MIN_H = 72;
    const CHROME_H = 26;

    function viewStory2aBox() {
        const wrap = $('view-story2a');
        if (!wrap) return { left: 0, top: 0, width: 800, height: 600 };
        return {
            left: wrap.offsetLeft,
            top: wrap.offsetTop,
            width: wrap.clientWidth,
            height: wrap.clientHeight,
        };
    }

    function kv2aOffset() {
        const kv = $('kv-2a');
        if (!kv || kv.style.display === 'none') return { x: 0, y: 0 };
        return { x: kv.offsetLeft, y: kv.offsetTop };
    }

    function bubbleLayerRect(b) {
        const off = kv2aOffset();
        const layerX = imgLayer2a ? imgLayer2a.x() : 0;
        const layerY = imgLayer2a ? imgLayer2a.y() : 0;
        const [x1, y1, x2, y2] = b.bbox;
        return {
            left: off.x + layerX + x1 * S2.scale,
            top: off.y + layerY + y1 * S2.scale,
            width: (x2 - x1) * S2.scale,
            height: (y2 - y1) * S2.scale,
        };
    }

    function defaultFrameLayout(b) {
        const wrap = viewStory2aBox();
        const br = bubbleLayerRect(b);
        const gap = 12;
        const fw = Math.max(220, Math.min(340, Math.max(br.width * 1.1, 220)));
        const fh = Math.max(120, Math.min(240, Math.max(br.height * 1.2, 120)));
        let left = br.left + br.width + gap;
        let top = br.top;
        if (left + fw > wrap.width - 8) {
            left = br.left - fw - gap;
        }
        if (left < 8) left = 8;
        if (top + fh > wrap.height - 8) top = wrap.height - fh - 8;
        if (top < 8) top = 8;
        return { left, top, w: fw, h: fh };
    }

    function getFrameLayout(b, forceDefault) {
        const id = b.bubble_id;
        if (forceDefault || !S2.frameLayouts[id]) {
            S2.frameLayouts[id] = defaultFrameLayout(b);
        }
        return S2.frameLayouts[id];
    }

    function clampFrameLayout(layout) {
        const wrap = viewStory2aBox();
        layout.w = Math.max(FRAME_MIN_W, layout.w);
        layout.h = Math.max(FRAME_MIN_H, layout.h);
        layout.left = Math.max(0, Math.min(wrap.width - layout.w, layout.left));
        layout.top = Math.max(0, Math.min(wrap.height - layout.h, layout.top));
        return layout;
    }

    function applyFrameLayout(layout) {
        const frame = $('s2a-bubble-frame');
        const ed = $('s2a-inline-edit');
        if (!frame) return;
        clampFrameLayout(layout);
        frame.style.display = 'flex';
        frame.style.left = layout.left + 'px';
        frame.style.top = layout.top + 'px';
        frame.style.width = layout.w + 'px';
        frame.style.height = layout.h + 'px';
        if (ed) ed.style.minHeight = Math.max(28, layout.h - CHROME_H) + 'px';
    }

    function updatePanelNav() {
        const panel = currentPanel();
        const total = S2.document ? S2.document.panels.length : 0;
        const nav = $('s2a-panel-nav');
        if (nav) {
            nav.textContent = total
                ? `Панель ${S2.panelIndex + 1} / ${total}`
                : 'Нет панелей';
        }
        if ($('s2a-prev')) $('s2a-prev').disabled = S2.panelIndex <= 0;
        if ($('s2a-next')) $('s2a-next').disabled = S2.panelIndex >= total - 1;
        renderBubbleList();
    }

    function renderBubbleList() {
        const list = $('s2a-bubble-list');
        if (!list) return;
        list.innerHTML = '';
        const panel = currentPanel();
        if (!panel) return;
        sortPanelBubbles(panel);
        panel.bubbles.forEach((b) => {
            const row = document.createElement('div');
            row.className = 's2a-bubble-row' + (b.bubble_id === S2.selBubbleId ? ' active' : '');
            row.title = b.bubble_id ? `ID: ${b.bubble_id}` : '';
            const order = document.createElement('span');
            order.className = 's2a-bubble-row-order';
            order.textContent = String(b.reading_order || '·');
            const main = document.createElement('span');
            main.className = 's2a-bubble-row-main';
            const preview = (b.corrected_text || b.raw_text || '').trim();
            main.textContent = preview ? preview.slice(0, 48) : '— текст —';
            const actions = document.createElement('div');
            actions.className = 's2a-bubble-row-actions';
            actions.onclick = (e) => e.stopPropagation();

            ['order', 'chevronUp', 'chevronDown'].forEach((icon, idx) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'chrome-btn' + (icon === 'order' ? '' : '');
                if (icon === 'order') {
                    RO().mountIconButton(btn, 'order', 'Номер в очереди');
                    btn.onclick = () => openBubbleOrderPopup(b.bubble_id, btn.getBoundingClientRect());
                } else if (icon === 'chevronUp') {
                    RO().mountIconButton(btn, 'chevronUp', 'Выше');
                    btn.onclick = () => moveBubbleOrder(b.bubble_id, -1);
                } else {
                    RO().mountIconButton(btn, 'chevronDown', 'Ниже');
                    btn.onclick = () => moveBubbleOrder(b.bubble_id, 1);
                }
                actions.appendChild(btn);
            });

            row.appendChild(order);
            row.appendChild(main);
            row.appendChild(actions);
            row.onclick = () => selectBubble(b.bubble_id);
            list.appendChild(row);
        });
    }

    function moveBubbleOrder(bubbleId, delta) {
        const panel = currentPanel();
        if (!panel || !RO()) return;
        RO().moveItem(panel.bubbles, bubbleId, delta, bubbleIdOf, 'reading_order');
        renderBubbleList();
        redrawBubbles();
        updateChromeState();
    }

    function openBubbleOrderPopup(bubbleId, anchorRect) {
        const panel = currentPanel();
        const b = bubbleById(bubbleId);
        if (!panel || !b || !RO()) return;
        sortPanelBubbles(panel);
        RO().showOrderPopup({
            current: b.reading_order || 1,
            max: panel.bubbles.length,
            anchorRect,
            onApply: (n) => {
                RO().setItemOrder(panel.bubbles, bubbleId, n, bubbleIdOf, 'reading_order');
                renderBubbleList();
                redrawBubbles();
                updateChromeState();
            },
        });
    }

    function selectBubble(id, opts) {
        S2.selBubbleId = id;
        const b = bubbleById(id);
        if (!id || !b) {
            const frame = $('s2a-bubble-frame');
            if (frame) frame.style.display = 'none';
            renderBubbleList();
            redrawBubbles();
            return;
        }
        if ($('s2a-bubble-type')) $('s2a-bubble-type').value = b.type || 'speech';
        if ($('s2a-bubble-text')) $('s2a-bubble-text').value = b.corrected_text || '';
        renderBubbleList();
        redrawBubbles();
        positionBubbleFrame(!!(opts && opts.forceFrameLayout));
        updateChromeState();
    }

    function syncSelectedFromSidebar() {
        const b = bubbleById(S2.selBubbleId);
        if (!b) return;
        if ($('s2a-bubble-type')) b.type = $('s2a-bubble-type').value;
        if ($('s2a-bubble-text')) b.corrected_text = $('s2a-bubble-text').value;
        redrawBubbles();
        renderBubbleList();
    }

    function updateChromeState() {
        const b = bubbleById(S2.selBubbleId);
        const orderEl = $('s2a-chrome-order');
        const reocrBtn = $('s2a-chrome-reocr');
        if (orderEl) orderEl.textContent = b ? String(b.reading_order || '·') : '';
        if (reocrBtn) {
            const hasText = b && (b.raw_text || b.corrected_text);
            reocrBtn.title = hasText ? 'Перераспознать' : 'Распознать';
            reocrBtn.setAttribute('aria-label', reocrBtn.title);
        }
    }

    function initStage2a(w, h) {
        const container = $('kv-2a');
        if (!container) return;
        if (stage2a) {
            stage2a.destroy();
            stage2a = null;
        }
        container.style.display = 'block';
        $('s2a-empty').style.display = 'none';

        stage2a = new Konva.Stage({ container: 'kv-2a', width: w, height: h });
        imgLayer2a = new Konva.Layer();
        bubbleLayer2a = new Konva.Layer();
        stage2a.add(imgLayer2a);
        stage2a.add(bubbleLayer2a);

        stage2a.on('mousedown touchstart', (e) => {
            if (e.target === stage2a) {
                isPanning2a = true;
                panStart2a = { x: e.evt.clientX, y: e.evt.clientY };
                panOrigin2a = { x: imgLayer2a.x(), y: imgLayer2a.y() };
            }
        });
        stage2a.on('mouseup touchend', () => {
            isPanning2a = false;
        });
        stage2a.on('mousemove', (e) => {
            if (!isPanning2a) return;
            const dx = e.evt.clientX - panStart2a.x;
            const dy = e.evt.clientY - panStart2a.y;
            const p = { x: panOrigin2a.x + dx, y: panOrigin2a.y + dy };
            imgLayer2a.position(p);
            bubbleLayer2a.position(p);
            imgLayer2a.batchDraw();
            bubbleLayer2a.batchDraw();
        });
    }

    function fitScale(imgW, imgH) {
        const main = document.querySelector('main');
        const mw = main ? main.clientWidth - 32 : 800;
        const mh = main ? main.clientHeight - 48 : 600;
        return Math.min(1, mw / imgW, mh / imgH);
    }

    function loadPanelImage(absPath) {
        const url = `/api/image?path=${encodeURIComponent(absPath)}`;
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Не удалось загрузить изображение'));
            img.src = url;
        });
    }

    async function showCurrentPanel() {
        const panel = currentPanel();
        if (!panel) return;
        sortPanelBubbles(panel);
        const abs = S2.panelPaths[panel.panel_id];
        if (!abs) {
            toast('Нет файла панели: ' + panel.image_path, 'err');
            return;
        }
        try {
            const img = await loadPanelImage(abs);
            S2.imgW = img.width;
            S2.imgH = img.height;
            S2.scale = fitScale(img.width, img.height);
            const w = Math.round(img.width * S2.scale);
            const h = Math.round(img.height * S2.scale);
            initStage2a(w, h);
            kImg2a = new Konva.Image({ image: img, width: w, height: h, listening: false });
            imgLayer2a.destroyChildren();
            bubbleLayer2a.destroyChildren();
            imgLayer2a.add(kImg2a);
            imgLayer2a.position({ x: 0, y: 0 });
            bubbleLayer2a.position({ x: 0, y: 0 });
            redrawBubbles();
            S2.selBubbleId = panel.bubbles.length ? panel.bubbles[0].bubble_id : null;
            selectBubble(S2.selBubbleId);
        } catch (e) {
            toast(e.message, 'err');
        }
    }

    function redrawBubbles() {
        if (!bubbleLayer2a) return;
        bubbleLayer2a.destroyChildren();
        const panel = currentPanel();
        if (!panel) return;
        sortPanelBubbles(panel);

        panel.bubbles.forEach((b) => {
            const sel = b.bubble_id === S2.selBubbleId;
            const col = BUBBLE_COLORS[b.type] || BUBBLE_COLORS.speech;
            const [x1, y1, x2, y2] = b.bbox;
            const sp = { x: x1 * S2.scale, y: y1 * S2.scale };
            const pw = (x2 - x1) * S2.scale;
            const ph = (y2 - y1) * S2.scale;
            const g = new Konva.Group({ id: b.bubble_id, name: 'bubble-group' });

            const fill = new Konva.Rect({
                x: sp.x, y: sp.y, width: pw, height: ph, fill: col, opacity: 0.12,
            });
            const box = new Konva.Rect({
                x: sp.x, y: sp.y, width: pw, height: ph,
                stroke: col, strokeWidth: 2,
                dash: sel ? [] : [6, 4],
                draggable: sel,
                name: 'bubble-box',
            });
            const badge = new Konva.Text({
                x: sp.x + 2, y: sp.y + 2,
                text: String(b.reading_order || ''),
                fontSize: Math.max(10, 11 * S2.scale),
                fontStyle: 'bold',
                fill: col,
                listening: false,
            });
            g.add(fill, box, badge);

            let handles = null;
            if (sel) {
                handles = [];
                [
                    { ci: 0, cur: 'nwse-resize' },
                    { ci: 1, cur: 'nesw-resize' },
                    { ci: 2, cur: 'nwse-resize' },
                    { ci: 3, cur: 'nesw-resize' },
                ].forEach(({ ci, cur }) => {
                    const cx = ci === 0 || ci === 3 ? x1 : x2;
                    const cy = ci === 0 || ci === 1 ? y1 : y2;
                    const h = new Konva.Rect({
                        x: cx * S2.scale - 6, y: cy * S2.scale - 6,
                        width: 12, height: 12,
                        fill: col, opacity: 0.9, cornerRadius: 2,
                        draggable: true, name: 'corner',
                    });
                    h.on('mouseenter', () => { document.body.style.cursor = cur; });
                    h.on('mouseleave', () => { document.body.style.cursor = 'default'; });
                    h.on('dragmove', () => {
                        const hp = h.position();
                        const ip = layerToImg(hp.x + 6, hp.y + 6);
                        resizeBubbleBbox(b, ci, ip.x, ip.y);
                        syncBubbleKonva(b, fill, box, badge, handles);
                    });
                    handles.push(h);
                    g.add(h);
                });

                box.on('dragmove', () => {
                    const pos = box.position();
                    const ip = layerToImg(pos.x, pos.y);
                    const bw = b.bbox[2] - b.bbox[0];
                    const bh = b.bbox[3] - b.bbox[1];
                    const nx1 = Math.max(0, Math.min(Math.round(ip.x), S2.imgW - bw));
                    const ny1 = Math.max(0, Math.min(Math.round(ip.y), S2.imgH - bh));
                    b.bbox = normBbox([nx1, ny1, nx1 + bw, ny1 + bh]);
                    syncBubbleKonva(b, fill, box, badge, handles);
                });
            }

            g.on('click tap', (e) => {
                if (e.target.name() === 'corner') return;
                selectBubble(b.bubble_id);
            });
            bubbleLayer2a.add(g);
        });
        bubbleLayer2a.batchDraw();
        positionBubbleFrame();
    }

    function positionBubbleFrame(forceDefault) {
        const frame = $('s2a-bubble-frame');
        const ed = $('s2a-inline-edit');
        const b = bubbleById(S2.selBubbleId);
        if (!frame || !b || !stage2a) {
            if (frame) frame.style.display = 'none';
            return;
        }
        const layout = getFrameLayout(b, forceDefault);
        applyFrameLayout(layout);
        if (ed && document.activeElement !== ed) ed.textContent = b.corrected_text || '';
    }

    function onInlineEditInput() {
        const ed = $('s2a-inline-edit');
        const b = bubbleById(S2.selBubbleId);
        if (!ed || !b) return;
        b.corrected_text = ed.textContent || '';
        if ($('s2a-bubble-text')) $('s2a-bubble-text').value = b.corrected_text;
        redrawBubbles();
        renderBubbleList();
    }

    function nextBubbleId(panel) {
        let n = panel.bubbles.length + 1;
        let bid = `${panel.panel_id}_b${n}`;
        while (panel.bubbles.some((b) => b.bubble_id === bid)) {
            n += 1;
            bid = `${panel.panel_id}_b${n}`;
        }
        return bid;
    }

    function defaultManualBubbleBbox() {
        const w = S2.imgW || 400;
        const h = S2.imgH || 400;
        return normBbox([
            Math.round(w * 0.1),
            Math.round(h * 0.1),
            Math.round(w * 0.4),
            Math.round(h * 0.4),
        ]);
    }

    function addManualBubbleFromButton() {
        if (!stage2a || !S2.document) {
            toast('Сначала загрузите панель (OCR или проект)', 'err');
            return;
        }
        addManualBubble(defaultManualBubbleBbox());
    }

    function addManualBubble(bbox) {
        const panel = currentPanel();
        if (!panel) return;
        sortPanelBubbles(panel);
        const bid = nextBubbleId(panel);
        const order = panel.bubbles.length + 1;
        panel.bubbles.push({
            bubble_id: bid,
            bbox: normBbox(bbox),
            raw_text: '',
            corrected_text: '',
            type: 'speech',
            reading_order: order,
        });
        delete S2.frameLayouts[bid];
        selectBubble(bid, { forceFrameLayout: true });
        toast('Подгоните рамку бабла на панели, затем «Распознать»', 'ok');
    }

    function deleteBubble() {
        const panel = currentPanel();
        if (!panel || !S2.selBubbleId) return;
        const removed = S2.selBubbleId;
        panel.bubbles = panel.bubbles.filter((b) => b.bubble_id !== removed);
        delete S2.frameLayouts[removed];
        if (RO()) RO().normalizeOrders(panel.bubbles, 'reading_order');
        S2.selBubbleId = panel.bubbles.length ? panel.bubbles[0].bubble_id : null;
        selectBubble(S2.selBubbleId);
        toast('Бабл удалён', 'ok');
    }

    async function reocrBubble2a() {
        if (S2.reocrBusy) return;
        const b = bubbleById(S2.selBubbleId);
        const panel = currentPanel();
        syncFieldsFromUi();
        const project = S2.document?.project || S2.project || readUiFields().project;
        if (!b || !panel || !project) {
            toast('Выберите бабл и проект', 'err');
            return;
        }
        syncSelectedFromSidebar();
        b.bbox = normBbox(b.bbox);
        const panelAbs = S2.panelPaths[panel.panel_id] || null;
        const reocrBtn = $('s2a-chrome-reocr');
        S2.reocrBusy = true;
        if (reocrBtn) reocrBtn.disabled = true;
        try {
            const r = await fetch(`/api/story/stage_2a/${encodeURIComponent(project)}/reocr`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify({
                    panel_id: panel.panel_id,
                    bubble_id: b.bubble_id,
                    bbox: b.bbox,
                    image_path: panel.image_path,
                    panel_abs_path: panelAbs,
                }),
            });
            let data = null;
            try {
                data = await r.json();
            } catch (_) {
                throw new Error(r.statusText || 'Ответ сервера не JSON');
            }
            if (!r.ok) throw new Error(formatApiError(data, r.statusText));
            b.raw_text = data.raw_text || '';
            b.corrected_text = data.corrected_text || data.raw_text || '';
            selectBubble(b.bubble_id);
            toast(`${b.raw_text ? 'Перераспознано' : 'Распознано'} (${data.ocr_engine}, ${data.ocr_ms}ms)`, 'ok');
        } catch (e) {
            toast(e.message, 'err');
        } finally {
            S2.reocrBusy = false;
            if (reocrBtn) reocrBtn.disabled = false;
        }
    }

    async function fetchPanelPaths(project) {
        const r = await fetch(`/api/story/stage_2a/${encodeURIComponent(project)}`);
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || r.statusText);
        const map = {};
        (data.panel_paths || []).forEach((row) => {
            if (row.abs_path) map[row.panel_id] = row.abs_path;
        });
        return map;
    }

    let stage2aOptions = null;

    async function loadStage2aOptions() {
        if (stage2aOptions) return stage2aOptions;
        try {
            const r = await fetch('/api/story/stage_2a/options');
            stage2aOptions = await r.json();
            const hint = $('s2a-engine-hint');
            if (hint && stage2aOptions) {
                const pp = stage2aOptions.ocr_preprocess || {};
                const sf = stage2aOptions.siliconflow_model
                    ? ` · ${stage2aOptions.siliconflow_model}`
                    : '';
                hint.textContent =
                    `OCR: ${stage2aOptions.ocr_engine || 'siliconflow'}${sf} · ` +
                    `preprocess ×${pp.upscale_factor || 3} ${pp.contrast || 'clahe'} · ` +
                    `langs: ${(stage2aOptions.ocr_languages || []).join(', ')}`;
            }
        } catch (_) {
            stage2aOptions = {};
        }
        return stage2aOptions;
    }

    function formatStats(data) {
        if (!data?.stats) return '';
        const s = data.stats;
        const eng = s.ocr_engine ? `, OCR: ${s.ocr_engine}` : '';
        return `Панелей: ${s.panels}, баблов: ${s.bubbles}, YOLO: ${s.yolo_ms}ms, OCR: ${s.ocr_ms}ms${eng}`;
    }

    async function runProcess2a() {
        syncFieldsFromUi();
        const { project, panelsDir } = readUiFields();
        if (!project || !panelsDir) {
            toast('Укажите проект и папку панелей', 'err');
            return;
        }
        const btn = $('s2a-btn-run');
        if (btn) btn.disabled = true;
        setStatus2a('YOLO + OCR…');
        await loadStage2aOptions();
        try {
            const r = await fetch('/api/story/stage_2a/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify({ project, panels_dir: panelsDir }),
            });
            const data = await r.json();
            if (!r.ok) throw new Error(formatApiError(data, r.statusText));
            S2.project = data.document?.project || project;
            S2.panelsDir = panelsDir;
            if ($('s2a-project') && S2.project) $('s2a-project').value = S2.project;
            S2.document = data.document;
            normalizeDocument(S2.document);
            S2.panelPaths = await fetchPanelPaths(S2.project);
            S2.panelIndex = 0;
            if (data.stats && $('s2a-stats')) {
                $('s2a-stats').style.display = 'block';
                $('s2a-stats-text').textContent = formatStats(data);
            }
            updatePanelNav();
            await showCurrentPanel();
            if (window.ComicSplitUiState) ComicSplitUiState.scheduleSave();
            toast(`Готово: ${data.stats.bubbles} баблов`, 'ok');
        } catch (e) {
            toast(e.message, 'err');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async function loadProject2a() {
        syncFieldsFromUi();
        const project = readUiFields().project;
        if (!project) return;
        try {
            const r = await fetch(`/api/story/stage_2a/${encodeURIComponent(project)}`);
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || r.statusText);
            S2.project = data.document?.project || project;
            S2.document = data.document;
            normalizeDocument(S2.document);
            S2.panelPaths = {};
            (data.panel_paths || []).forEach((row) => {
                if (row.abs_path) S2.panelPaths[row.panel_id] = row.abs_path;
            });
            if ($('s2a-project') && S2.project) $('s2a-project').value = S2.project;
            S2.panelIndex = 0;
            updatePanelNav();
            await showCurrentPanel();
            if (window.ComicSplitUiState) ComicSplitUiState.scheduleSave();
            toast('Проект загружен', 'ok');
        } catch (e) {
            toast(e.message, 'err');
        }
    }

    async function saveProject2a() {
        if (!S2.document) {
            toast('Нет данных для сохранения', 'err');
            return;
        }
        syncSelectedFromSidebar();
        (S2.document.panels || []).forEach((p) => sortPanelBubbles(p));
        const project = S2.project || S2.document.project;
        try {
            const r = await fetch(`/api/story/stage_2a/${encodeURIComponent(project)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify({ document: S2.document }),
            });
            const data = await r.json();
            if (!r.ok) {
                const msg = data.errors ? JSON.stringify(data.errors) : (data.detail || r.statusText);
                throw new Error(msg);
            }
            toast('JSON сохранён и проверен', 'ok');
            if ($('s2a-save-hint')) $('s2a-save-hint').textContent = data.path || '';
        } catch (e) {
            toast('Ошибка: ' + e.message, 'err');
        }
    }

    function setupFrameInteractions() {
        const frame = $('s2a-bubble-frame');
        const chrome = frame && frame.querySelector('.s2a-chrome');
        const resize = $('s2a-frame-resize');
        if (!frame || !chrome) return;

        chrome.addEventListener('mousedown', (e) => {
            if (e.button !== 0 || e.target.closest('button')) return;
            const b = bubbleById(S2.selBubbleId);
            if (!b) return;
            const layout = getFrameLayout(b);
            const wrap = $('view-story2a');
            frameDrag2a = {
                bubbleId: b.bubble_id,
                startX: e.clientX,
                startY: e.clientY,
                origLeft: layout.left,
                origTop: layout.top,
                maxW: wrap ? wrap.clientWidth : 800,
                maxH: wrap ? wrap.clientHeight : 600,
            };
            e.preventDefault();
        });

        if (resize) {
            resize.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                const b = bubbleById(S2.selBubbleId);
                if (!b) return;
                const layout = getFrameLayout(b);
                const wrap = $('view-story2a');
                frameResize2a = {
                    bubbleId: b.bubble_id,
                    startX: e.clientX,
                    startY: e.clientY,
                    origW: layout.w,
                    origH: layout.h,
                    maxW: wrap ? wrap.clientWidth : 800,
                    maxH: wrap ? wrap.clientHeight : 600,
                };
                e.preventDefault();
                e.stopPropagation();
            });
        }

        if (window.__s2aFramePointerBound) return;
        window.__s2aFramePointerBound = true;

        document.addEventListener('mousemove', (e) => {
            if (frameDrag2a) {
                const layout = S2.frameLayouts[frameDrag2a.bubbleId];
                if (!layout) return;
                layout.left = frameDrag2a.origLeft + (e.clientX - frameDrag2a.startX);
                layout.top = frameDrag2a.origTop + (e.clientY - frameDrag2a.startY);
                applyFrameLayout(layout);
            }
            if (frameResize2a) {
                const layout = S2.frameLayouts[frameResize2a.bubbleId];
                if (!layout) return;
                layout.w = frameResize2a.origW + (e.clientX - frameResize2a.startX);
                layout.h = frameResize2a.origH + (e.clientY - frameResize2a.startY);
                applyFrameLayout(layout);
            }
        });
        document.addEventListener('mouseup', () => {
            frameDrag2a = null;
            frameResize2a = null;
        });
    }

    function setupChromeButtons() {
        if (!RO()) return;
        RO().mountIconButton($('s2a-chrome-order-btn'), 'order', 'Номер в очереди');
        RO().mountIconButton($('s2a-chrome-reocr'), 'refresh', 'Перераспознать');
        RO().mountIconButton($('s2a-chrome-delete'), 'close', 'Удалить бабл');
        if ($('s2a-chrome-delete')) {
            $('s2a-chrome-delete').onclick = (e) => {
                e.stopPropagation();
                deleteBubble();
            };
        }
        if ($('s2a-chrome-reocr')) {
            $('s2a-chrome-reocr').onclick = (e) => {
                e.stopPropagation();
                reocrBubble2a();
            };
        }
        if ($('s2a-chrome-order-btn')) {
            $('s2a-chrome-order-btn').onclick = (e) => {
                e.stopPropagation();
                if (S2.selBubbleId) {
                    openBubbleOrderPopup(S2.selBubbleId, e.currentTarget.getBoundingClientRect());
                }
            };
        }
    }

    function bindUi() {
        setupChromeButtons();
        setupFrameInteractions();
        if ($('s2a-btn-run')) $('s2a-btn-run').onclick = runProcess2a;
        if ($('s2a-btn-load')) $('s2a-btn-load').onclick = loadProject2a;
        if ($('s2a-btn-save')) $('s2a-btn-save').onclick = saveProject2a;
        if ($('s2a-prev')) $('s2a-prev').onclick = () => {
            syncSelectedFromSidebar();
            if (S2.panelIndex > 0) {
                S2.panelIndex -= 1;
                updatePanelNav();
                showCurrentPanel();
            }
        };
        if ($('s2a-next')) $('s2a-next').onclick = () => {
            syncSelectedFromSidebar();
            if (S2.document && S2.panelIndex < S2.document.panels.length - 1) {
                S2.panelIndex += 1;
                updatePanelNav();
                showCurrentPanel();
            }
        };
        if ($('s2a-bubble-type')) $('s2a-bubble-type').onchange = syncSelectedFromSidebar;
        if ($('s2a-bubble-text')) $('s2a-bubble-text').oninput = () => {
            const b = bubbleById(S2.selBubbleId);
            if (b && $('s2a-bubble-text')) {
                b.corrected_text = $('s2a-bubble-text').value;
                if ($('s2a-inline-edit') && document.activeElement !== $('s2a-inline-edit')) {
                    $('s2a-inline-edit').textContent = b.corrected_text;
                }
                redrawBubbles();
                renderBubbleList();
            }
        };
        if ($('s2a-add-mode')) {
            $('s2a-add-mode').onclick = addManualBubbleFromButton;
        }
        const ed = $('s2a-inline-edit');
        if (ed) {
            ed.addEventListener('input', onInlineEditInput);
            ed.addEventListener('blur', onInlineEditInput);
        }
        window.addEventListener('resize', () => {
            const b = bubbleById(S2.selBubbleId);
            if (b && S2.frameLayouts[b.bubble_id]) applyFrameLayout(S2.frameLayouts[b.bubble_id]);
        });
    }

    window.Story2a = {
        syncFieldsFromUi,
        onTabShow: () => {
            syncFieldsFromUi();
            setStatus2a('Stage 2a: OCR баблов');
            loadStage2aOptions();
            positionBubbleFrame(false);
        },
    };
    document.addEventListener('DOMContentLoaded', bindUi);
})();

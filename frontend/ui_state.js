/**
 * Память настроек UI (:8000): localStorage + sync PUT /api/ui/state.
 * Gradio :7860 использует тот же файл через utils/ui_state.py.
 */
(function () {
    const LS_KEY = 'comicsplit.ui.v1';
    const VERSION = 1;
    let saveTimer = null;
    let restoring = false;

    const $ = (id) => document.getElementById(id);

    function hooks() {
        return window.__uiStateHooks || {};
    }

    function collectGlobal() {
        const cp = typeof window.currentPreset !== 'undefined' ? window.currentPreset : 'standard';
        const at = typeof window.activeTab !== 'undefined' ? window.activeTab : 'split';
        return {
            active_preset: cp,
            preset_persist: !!$('preset-persist')?.checked,
            active_tab: at,
        };
    }

    function collectSplit() {
        return {
            source_path: $('img-path')?.value?.trim() || '',
            folder_path: '',
            output_dir: $('out-dir')?.value?.trim() || '',
            panel_detector: $('panel-detector')?.value || 'comic',
            use_sam: !!$('use-sam')?.checked,
            reading_order: $('reading-order')?.checked !== false,
            rtl: !!$('rtl')?.checked,
            confidence_threshold: parseFloat($('conf-thr')?.value || '0.35'),
            iou_threshold: parseFloat($('iou-thr')?.value || '0.45'),
            poly_mode: !!$('poly-mode')?.checked,
        };
    }

    function collectUpscale(prefix) {
        const p = prefix || 'up';
        return {
            panels_dir: $(`${p}-panels`)?.value?.trim() || '',
            output_dir: $(`${p}-output`)?.value?.trim() || '',
            scale: parseInt($(`${p}-scale`)?.value, 10) || 2,
            backend: $(`${p}-backend`)?.value || 'realesrgan',
            model: $(`${p}-model`)?.value || 'animevideov3',
            gpu_id: parseInt($(`${p}-gpu`)?.value, 10) || 0,
            cugan_noise: parseInt($(`${p}-cugan-noise`)?.value, 10),
            cugan_syncgap: parseInt($(`${p}-cugan-syncgap`)?.value, 10),
        };
    }

    function collectVideo() {
        return {
            ...collectUpscale('vid'),
            mode: $('vid-mode')?.value || 'opencv_zoom',
            upscale_enabled: $('vid-upscale')?.checked !== false,
            harmonize_mode: $('vid-harm-mode')?.value || 'auto',
            harmonize_blur_sigma: parseFloat($('vid-harm-blur')?.value || '60'),
            harmonize_vignette: parseFloat($('vid-harm-vig')?.value || '0.7'),
            intensity: parseFloat($('vid-intensity')?.value || '0.3'),
            depthflow_animation: $('vid-df-anim')?.value || 'zoom',
            tpsmm_driving_video: $('vid-tpsmm-driving')?.value?.trim() || '',
            duration: parseFloat($('vid-duration')?.value || '3'),
            fps: parseInt($('vid-fps')?.value, 10) || 24,
            do_concat: $('vid-concat')?.checked !== false,
        };
    }

    function collectStory2a() {
        return {
            project: $('s2a-project')?.value?.trim() || '',
            panels_dir: $('s2a-panels-dir')?.value?.trim() || '',
        };
    }

    function collectStory2aForPersist() {
        const s = collectStory2a();
        const out = {};
        if (s.project) out.project = s.project;
        if (s.panels_dir) out.panels_dir = s.panels_dir;
        return Object.keys(out).length ? out : null;
    }

    function mergeStory2aSection(server, local) {
        const s = server || {};
        const l = local || {};
        return {
            project: (l.project && String(l.project).trim()) || s.project || '',
            panels_dir: (l.panels_dir && String(l.panels_dir).trim()) || s.panels_dir || '',
        };
    }

    function mergeUiState(server, local) {
        const base = server && server.version === VERSION ? server : { version: VERSION };
        if (!local || local.version !== VERSION) {
            return {
                version: VERSION,
                global: base.global || {},
                split: base.split || {},
                upscale: base.upscale || {},
                video: base.video || {},
                story2a: base.story2a || {},
            };
        }
        return {
            version: VERSION,
            global: { ...(base.global || {}), ...(local.global || {}) },
            split: { ...(base.split || {}), ...(local.split || {}) },
            upscale: { ...(base.upscale || {}), ...(local.upscale || {}) },
            video: { ...(base.video || {}), ...(local.video || {}) },
            story2a: mergeStory2aSection(base.story2a, local.story2a),
        };
    }

    function collectAll() {
        return {
            version: VERSION,
            global: collectGlobal(),
            split: collectSplit(),
            upscale: collectUpscale('up'),
            video: collectVideo(),
            story2a: collectStory2a(),
        };
    }

    function setRange(id, val) {
        const h = hooks().setRange;
        if (h) h(id, val);
        else {
            const el = $(id);
            if (el) {
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    }

    function applyUpscaleSection(u, prefix) {
        const p = prefix || 'up';
        if ($( `${p}-panels`)) $(`${p}-panels`).value = u.panels_dir || '';
        if ($( `${p}-output`)) $(`${p}-output`).value = u.output_dir || (p === 'up' ? 'output_upscaled' : 'story_out');
        if ($( `${p}-backend`)) $(`${p}-backend`).value = u.backend || 'realesrgan';
        if ($( `${p}-model`)) $(`${p}-model`).value = u.model || 'animevideov3';
        if ($( `${p}-cugan-noise`)) setRange(`${p}-cugan-noise`, u.cugan_noise ?? -1);
        if ($( `${p}-cugan-syncgap`)) $(`${p}-cugan-syncgap`).value = String(u.cugan_syncgap ?? 3);
        const h = hooks();
        if (h.refreshUpscaleUI) h.refreshUpscaleUI(p);
        let scale = u.scale ?? 2;
        if (h.isX4OnlyUpscaleModel && h.isX4OnlyUpscaleModel($( `${p}-model`)?.value) && scale === 2) scale = 4;
        if (h.setSegScale) h.setSegScale(`${p}-scale-seg`, `${p}-scale`, scale);
        const gpu = String(u.gpu_id ?? 0);
        const gpuEl = $(`${p}-gpu`);
        if (gpuEl && gpuEl.querySelector(`option[value="${gpu}"]`)) gpuEl.value = gpu;
    }

    function applyState(st) {
        if (!st || st.version !== VERSION) return false;
        restoring = true;
        window.__uiRestoring = true;
        const g = st.global || {};
        const s = st.split || {};
        const u = st.upscale || {};
        const v = st.video || {};
        const s2 = st.story2a || {};

        if (g.active_preset && hooks().setPresetActive) hooks().setPresetActive(g.active_preset);
        if ($('preset-persist')) $('preset-persist').checked = !!g.preset_persist;

        if ($('img-path')) $('img-path').value = s.source_path || '';
        if ($('out-dir')) $('out-dir').value = s.output_dir || '';
        if ($('panel-detector')) $('panel-detector').value = s.panel_detector || 'comic';
        if ($('use-sam')) $('use-sam').checked = !!s.use_sam;
        if ($('reading-order')) $('reading-order').checked = s.reading_order !== false;
        if ($('rtl')) $('rtl').checked = !!s.rtl;
        setRange('conf-thr', s.confidence_threshold ?? 0.35);
        setRange('iou-thr', s.iou_threshold ?? 0.45);
        if ($('poly-mode')) {
            $('poly-mode').checked = !!s.poly_mode;
            if (typeof window.S !== 'undefined') window.S.polyMode = !!s.poly_mode;
            const ph = $('poly-hint');
            if (ph) ph.className = 'poly-hint' + (s.poly_mode ? ' show' : '');
        }

        applyUpscaleSection(u, 'up');
        applyUpscaleSection(v, 'vid');

        if ($('vid-mode')) $('vid-mode').value = v.mode || 'opencv_zoom';
        if ($('vid-upscale')) $('vid-upscale').checked = v.upscale_enabled !== false;
        if ($('vid-harm-mode')) $('vid-harm-mode').value = v.harmonize_mode || 'auto';
        setRange('vid-harm-blur', v.harmonize_blur_sigma ?? 60);
        setRange('vid-harm-vig', v.harmonize_vignette ?? 0.7);
        setRange('vid-intensity', v.intensity ?? 0.3);
        if ($('vid-df-anim')) $('vid-df-anim').value = v.depthflow_animation || 'zoom';
        if ($('vid-tpsmm-driving')) $('vid-tpsmm-driving').value = v.tpsmm_driving_video || '';
        setRange('vid-duration', v.duration ?? 3);
        setRange('vid-fps', v.fps ?? 24);
        if ($('vid-concat')) $('vid-concat').checked = v.do_concat !== false;

        if ($('s2a-project')) $('s2a-project').value = s2.project || '';
        if ($('s2a-panels-dir')) $('s2a-panels-dir').value = s2.panels_dir || '';
        if (hooks().syncStory2aFromUi) hooks().syncStory2aFromUi();

        if (g.active_tab && hooks().switchTab) hooks().switchTab(g.active_tab);

        if (hooks().updateSamHint) hooks().updateSamHint();
        if (hooks().syncVideoAdvancedVisibility) hooks().syncVideoAdvancedVisibility();
        if (hooks().applyPresetModeUI) hooks().applyPresetModeUI();
        if (hooks().loadSplitOptions) hooks().loadSplitOptions(true);

        restoring = false;
        window.__uiRestoring = false;
        return true;
    }

    async function persist() {
        if (restoring) return;
        const body = collectAll();
        try {
            localStorage.setItem(LS_KEY, JSON.stringify(body));
        } catch (_) { /* quota */ }
        try {
            const patch = {
                global: body.global,
                split: body.split,
                upscale: body.upscale,
                video: body.video,
            };
            const s2a = collectStory2aForPersist();
            if (s2a) patch.story2a = s2a;
            await fetch('/api/ui/state', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify(patch),
            });
        } catch (_) { /* offline */ }
    }

    function scheduleSave() {
        if (restoring) return;
        clearTimeout(saveTimer);
        saveTimer = setTimeout(persist, 400);
    }

    async function restore() {
        let local = null;
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (raw) local = JSON.parse(raw);
        } catch (_) { /* ignore */ }

        let server = null;
        try {
            const r = await fetch('/api/ui/state');
            if (r.ok) server = await r.json();
        } catch (_) { /* offline */ }

        if (!local && !server) return false;
        const st = mergeUiState(server, local);
        const ok = applyState(st);
        if (ok) {
            try {
                localStorage.setItem(LS_KEY, JSON.stringify(collectAll()));
            } catch (_) { /* quota */ }
        }
        return ok;
    }

    async function resetSection(section) {
        try {
            const r = await fetch('/api/ui/state/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify({ section }),
            });
            if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
            const st = await r.json();
            localStorage.setItem(LS_KEY, JSON.stringify(st));
            applyState(st);
            if (hooks().toast) hooks().toast(`Сброс настроек: ${section}`);
            return st;
        } catch (e) {
            if (hooks().toast) hooks().toast(e.message || 'Сброс не удался', 'err');
            return null;
        }
    }

    function bindAutoSave() {
        const root = $('app') || document.body;
        root.querySelectorAll('input, select, textarea').forEach((el) => {
            if (el.id === 'preset-persist') return;
            el.addEventListener('change', scheduleSave);
            el.addEventListener('input', scheduleSave);
        });
        document.querySelectorAll('.seg-btn').forEach((btn) => {
            btn.addEventListener('click', () => setTimeout(scheduleSave, 50));
        });
    }

    window.ComicSplitUiState = {
        LS_KEY,
        collectAll,
        applyState,
        scheduleSave,
        persist,
        restore,
        resetSection,
        bindAutoSave,
    };
})();

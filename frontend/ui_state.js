/**
 * Память настроек UI (:8000): localStorage + sync PUT /api/ui/state.
 * Gradio :7860 использует тот же файл через utils/ui_state.py.
 */
(function () {
    const LS_KEY = 'comicsplit.ui.v1';
    const VERSION = 1;
    let saveTimer = null;
    let restoring = false;
    let persistGeneration = 0;

    const $ = (id) => document.getElementById(id);

    function hooks() {
        return window.__uiStateHooks || {};
    }

    function collectGlobal() {
        const cp = typeof window.currentPreset !== 'undefined' ? window.currentPreset : 'standard';
        const at = typeof window.activeTab !== 'undefined' ? window.activeTab : 'split';
        const base = {
            active_preset: cp,
            preset_persist: !!$('preset-persist')?.checked,
            active_tab: at,
            current_project: '',
        };
        if (window.ComicSplitWorkspace) {
            Object.assign(base, ComicSplitWorkspace.collectWorkspaceGlobal());
        }
        return base;
    }

    function collectSplit() {
        const snapModeEl = document.querySelector('input[name="split-snap-mode"]:checked');
        const base = {
            source_path: $('img-path')?.value?.trim() || '',
            folder_path: $('split-folder-path')?.value?.trim() || '',
            output_dir: $('out-dir')?.value?.trim() || '',
            panel_detector: $('panel-detector')?.value || 'comic',
            use_sam: !!$('use-sam')?.checked,
            reading_order: $('reading-order')?.checked !== false,
            rtl: !!$('rtl')?.checked,
            confidence_threshold: parseFloat($('conf-thr')?.value || '0.35'),
            iou_threshold: parseFloat($('iou-thr')?.value || '0.45'),
            poly_mode: !!$('poly-mode')?.checked,
            snap_mode: snapModeEl ? snapModeEl.value : 'off',
            snap_grid_step: parseInt($('split-snap-step')?.value, 10) || 8,
            use_project: false,
            project: '',
        };
        if (window.ComicSplitWorkspace) {
            Object.assign(base, ComicSplitWorkspace.collectWorkspaceSection('split'));
        }
        return base;
    }

    function collectUpscale(prefix) {
        const p = prefix || 'up';
        const tabKey = p === 'vid' ? 'vid' : 'up';
        const base = {
            panels_dir: $(`${p}-panels`)?.value?.trim() || '',
            output_dir: $(`${p}-output`)?.value?.trim() || '',
            scale: parseInt($(`${p}-scale`)?.value, 10) || 2,
            backend: $(`${p}-backend`)?.value || 'realesrgan',
            model: $(`${p}-model`)?.value || 'animevideov3',
            gpu_id: parseInt($(`${p}-gpu`)?.value, 10) || 0,
            cugan_noise: parseInt($(`${p}-cugan-noise`)?.value, 10),
            cugan_syncgap: parseInt($(`${p}-cugan-syncgap`)?.value, 10),
            use_project: false,
            project: '',
        };
        if (window.ComicSplitWorkspace) {
            Object.assign(base, ComicSplitWorkspace.collectWorkspaceSection(tabKey));
        }
        return base;
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
        const manual = $('s2a-mode-manual');
        const mode = (manual && manual.checked) ? 'manual' : 'auto';
        const base = {
            project: $('s2a-project')?.value?.trim() || '',
            panels_dir: $('s2a-panels-dir')?.value?.trim() || '',
            workflow_mode: mode,
            output_json_path: $('s2a-json-path')?.value?.trim() || '',
            use_project: false,
        };
        if (window.ComicSplitWorkspace) {
            Object.assign(base, ComicSplitWorkspace.collectWorkspaceSection('s2a'));
        }
        return base;
    }

    function collectStory2aForPersist() {
        return collectStory2a();
    }

    const SECTION_PATH_KEYS = {
        split: ['source_path', 'folder_path', 'output_dir'],
        upscale: ['panels_dir', 'output_dir'],
        video: ['panels_dir', 'output_dir', 'tpsmm_driving_video'],
        story2a: ['project', 'panels_dir', 'output_json_path'],
    };

    const SECTION_ENUM_FIELDS = {
        split: { snap_mode: ['off', 'grid', 'objects'] },
        story2a: { workflow_mode: ['manual', 'auto'] },
    };

    function mergePathSection(server, local, pathKeys, enumFields) {
        const s = server || {};
        const l = local || {};
        if (local == null) return { ...s };
        const out = { ...s, ...l };
        (pathKeys || []).forEach((key) => {
            if (Object.prototype.hasOwnProperty.call(l, key)) {
                out[key] = l[key] != null ? String(l[key]).trim() : '';
            }
        });
        Object.entries(enumFields || {}).forEach(([key, allowed]) => {
            if (!Object.prototype.hasOwnProperty.call(l, key)) return;
            out[key] = allowed.includes(l[key])
                ? l[key]
                : (allowed.includes(s[key]) ? s[key] : allowed[0]);
        });
        return out;
    }

    function mergeStory2aSection(server, local) {
        return mergePathSection(
            server,
            local,
            SECTION_PATH_KEYS.story2a,
            SECTION_ENUM_FIELDS.story2a,
        );
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
            split: mergePathSection(base.split, local.split, SECTION_PATH_KEYS.split, SECTION_ENUM_FIELDS.split),
            upscale: mergePathSection(base.upscale, local.upscale, SECTION_PATH_KEYS.upscale),
            video: mergePathSection(base.video, local.video, SECTION_PATH_KEYS.video),
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
        const outDefault = p === 'up' ? 'output_upscaled' : 'story_out';
        if ($(`${p}-panels`)) {
            $(`${p}-panels`).value = u.panels_dir != null ? u.panels_dir : '';
        }
        if ($(`${p}-output`)) {
            $(`${p}-output`).value = u.output_dir != null ? u.output_dir : outDefault;
        }
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
        if (window.ComicSplitWorkspace) ComicSplitWorkspace.applyWorkspaceGlobal(g);

        if ($('img-path')) $('img-path').value = s.source_path != null ? s.source_path : '';
        if ($('split-folder-path')) $('split-folder-path').value = s.folder_path != null ? s.folder_path : '';
        if ($('out-dir')) $('out-dir').value = s.output_dir != null ? s.output_dir : '';
        if (window.ComicSplitWorkspace) {
            if (s.use_project != null && $('split-use-project')) $('split-use-project').checked = !!s.use_project;
            if (s.project) ComicSplitWorkspace.setCurrentProject(s.project, { syncInputs: true });
        }
        if ($('panel-detector')) $('panel-detector').value = s.panel_detector || 'comic';
        if ($('use-sam')) $('use-sam').checked = !!s.use_sam;
        if ($('reading-order')) $('reading-order').checked = s.reading_order !== false;
        if ($('rtl')) $('rtl').checked = !!s.rtl;
        setRange('conf-thr', s.confidence_threshold ?? 0.35);
        setRange('iou-thr', s.iou_threshold ?? 0.45);
        if ($('poly-mode')) {
            $('poly-mode').checked = !!s.poly_mode;
            if (typeof window.S !== 'undefined') window.S.polyMode = !!s.poly_mode;
        }
        {
            const snapMode = ['off', 'grid', 'objects'].includes(s.snap_mode) ? s.snap_mode : 'off';
            const snapRadio = document.querySelector(`input[name="split-snap-mode"][value="${snapMode}"]`);
            if (snapRadio) snapRadio.checked = true;
            setRange('split-snap-step', s.snap_grid_step ?? 8);
            if (typeof window.S !== 'undefined') {
                window.S.snapMode = snapMode;
                window.S.snapGridStep = s.snap_grid_step ?? 8;
            }
        }

        applyUpscaleSection(u, 'up');
        applyUpscaleSection(v, 'vid');
        if (window.ComicSplitWorkspace) {
            if (u.use_project != null && $('up-use-project')) $('up-use-project').checked = !!u.use_project;
            if (u.project) ComicSplitWorkspace.setProjectInputValue('up-project', u.project);
            if (v.use_project != null && $('vid-use-project')) $('vid-use-project').checked = !!v.use_project;
            if (v.project) ComicSplitWorkspace.setProjectInputValue('vid-project', v.project);
        }

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

        if ($('s2a-project')) {
            if (window.ComicSplitWorkspace && s2.project) {
                ComicSplitWorkspace.setProjectInputValue('s2a-project', s2.project);
            }
        }
        if ($('s2a-panels-dir')) $('s2a-panels-dir').value = s2.panels_dir != null ? s2.panels_dir : '';
        if ($('s2a-json-path')) $('s2a-json-path').value = s2.output_json_path != null ? s2.output_json_path : '';
        if (window.ComicSplitWorkspace && s2.use_project != null && $('s2a-use-project')) {
            $('s2a-use-project').checked = !!s2.use_project;
        }
        const mode = s2.workflow_mode === 'auto' ? 'auto' : 'manual';
        const rm = $('s2a-mode-manual');
        const ra = $('s2a-mode-auto');
        if (rm) rm.checked = mode === 'manual';
        if (ra) ra.checked = mode === 'auto';
        if (hooks().syncStory2aFromUi) hooks().syncStory2aFromUi();

        if (g.active_tab && hooks().switchTab) hooks().switchTab(g.active_tab);

        if (hooks().updateSamHint) hooks().updateSamHint();
        if (hooks().syncVideoAdvancedVisibility) hooks().syncVideoAdvancedVisibility();
        if (hooks().applyPresetModeUI) hooks().applyPresetModeUI();
        if (hooks().loadSplitOptions) hooks().loadSplitOptions(true);

        if (window.ComicSplitWorkspace) {
            const anyUseProject = [s, u, v, s2].some((sec) => sec && sec.use_project);
            const projectName =
                g.current_project || s.project || u.project || v.project || s2.project;
            if (anyUseProject && projectName) {
                ComicSplitWorkspace.activateProjectGlobally(projectName);
            }
        }

        restoring = false;
        window.__uiRestoring = false;
        return true;
    }

    async function persist() {
        if (restoring) return;
        const gen = ++persistGeneration;
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
            patch.story2a = s2a;
            const r = await fetch('/api/ui/state', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                body: JSON.stringify(patch),
            });
            if (gen !== persistGeneration) return;
            if (!r.ok) return;
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
        clearTimeout(saveTimer);
        saveTimer = null;
        persistGeneration += 1;
        restoring = true;
        window.__uiRestoring = true;
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
            if (hooks().onUiResetSection) hooks().onUiResetSection(section);
            if (hooks().toast) hooks().toast(`Сброс настроек: ${section}`);
            return st;
        } catch (e) {
            if (hooks().toast) hooks().toast(e.message || 'Сброс не удался', 'err');
            return null;
        } finally {
            restoring = false;
            window.__uiRestoring = false;
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

/**
 * Workspace / project mode — shared across Split, Upscale, Video, ExText.
 */
(function () {
    const $ = (id) => document.getElementById(id);

    const TAB_CONFIG = {
        split: {
            use: 'split-use-project',
            project: 'split-project',
            pathFields: ['out-dir'],
            extraPathFields: ['split-folder-path'],
        },
        up: {
            use: 'up-use-project',
            project: 'up-project',
            pathFields: ['up-panels', 'up-output'],
        },
        vid: {
            use: 'vid-use-project',
            project: 'vid-project',
            pathFields: ['vid-panels', 'vid-output'],
        },
        s2a: {
            use: 's2a-use-project',
            project: 's2a-project',
            pathFields: ['s2a-panels-dir', 's2a-json-path'],
        },
    };

    const TAB_KEYS = Object.keys(TAB_CONFIG);
    const PROJECT_INPUTS = ['split-project', 'up-project', 'vid-project', 's2a-project'];

    let layoutCache = {};
    let knownProjects = [];
    let syncingProjectCheckboxes = false;
    let openComboMenu = null;
    let comboActiveIdx = -1;

    function hooks() {
        return window.__uiStateHooks || {};
    }

    function toast(msg, kind) {
        if (hooks().toast) hooks().toast(msg, kind);
    }

    function scheduleSave() {
        if (window.ComicSplitUiState) ComicSplitUiState.scheduleSave();
    }

    function getCurrentProject() {
        return (window.__currentProject || '').trim();
    }

    function setProjectInputValue(inputId, name) {
        const el = $(inputId);
        if (!el) return;
        el.value = (name || '').trim();
    }

    function setCurrentProject(name, opts) {
        const options = opts || {};
        const v = (name || '').trim();
        window.__currentProject = v;
        if (options.syncInputs !== false) {
            PROJECT_INPUTS.forEach((id) => setProjectInputValue(id, v));
        }
        scheduleSave();
    }

    function isProjectMode(tabKey) {
        const cfg = TAB_CONFIG[tabKey];
        if (!cfg) return false;
        return !!$(cfg.use)?.checked;
    }

    function projectInputId(tabKey) {
        return TAB_CONFIG[tabKey]?.project || '';
    }

    function readProjectForTab(tabKey) {
        const id = projectInputId(tabKey);
        const v = id ? ($(id)?.value || '').trim() : '';
        return v || getCurrentProject();
    }

    function getComboElements(inputId) {
        const input = $(inputId);
        if (!input) return {};
        const wrap = input.closest('.project-combo');
        const menu = wrap?.querySelector('.project-combo-menu');
        const toggle = wrap?.querySelector('.project-combo-toggle');
        return { input, wrap, menu, toggle };
    }

    function filteredProjects(query) {
        const q = (query || '').trim().toLowerCase();
        if (!q) return knownProjects.slice();
        return knownProjects.filter((p) => p.toLowerCase().includes(q));
    }

    function comboMenuItems(inputId, filter) {
        if (!filter) return knownProjects.slice();
        const input = $(inputId);
        return filteredProjects(input?.value);
    }

    function closeComboMenu() {
        if (openComboMenu) {
            openComboMenu.hidden = true;
            openComboMenu = null;
        }
        comboActiveIdx = -1;
    }

    function renderComboMenu(menu, inputId, items, activeIdx, opts) {
        const options = opts || {};
        if (!menu) return;
        menu.innerHTML = '';
        menu._inputId = inputId;
        menu._filter = !!options.filter;
        const current = ($(inputId)?.value || '').trim();
        if (!items.length) {
            const li = document.createElement('li');
            li.className = 'empty';
            li.textContent = knownProjects.length ? 'Нет совпадений' : 'Нет проектов';
            menu.appendChild(li);
            return;
        }
        items.forEach((name, i) => {
            const li = document.createElement('li');
            li.textContent = name;
            li.setAttribute('role', 'option');
            if (i === activeIdx) li.classList.add('active');
            if (!options.filter && current && name === current) li.classList.add('selected');
            li.addEventListener('mousedown', (e) => {
                e.preventDefault();
                selectComboItem(inputId, name);
            });
            menu.appendChild(li);
        });
        if (!options.filter && current) {
            const selected = menu.querySelector('li.selected');
            selected?.scrollIntoView({ block: 'nearest' });
        }
    }

    function refreshOpenComboMenu() {
        if (!openComboMenu || !openComboMenu._inputId) return;
        const inputId = openComboMenu._inputId;
        const items = comboMenuItems(inputId, openComboMenu._filter);
        if (comboActiveIdx >= items.length) comboActiveIdx = items.length - 1;
        renderComboMenu(openComboMenu, inputId, items, comboActiveIdx, { filter: openComboMenu._filter });
    }

    function openComboForInput(inputId, opts) {
        const options = opts || {};
        const filter = !!options.filter;
        const { input, menu } = getComboElements(inputId);
        if (!input || !menu) return;
        if (openComboMenu && openComboMenu !== menu) closeComboMenu();
        const items = comboMenuItems(inputId, filter);
        const current = (input.value || '').trim();
        comboActiveIdx = !filter && current ? items.indexOf(current) : -1;
        renderComboMenu(menu, inputId, items, comboActiveIdx, { filter });
        menu.hidden = false;
        openComboMenu = menu;
    }

    function moveComboHighlight(delta) {
        if (!openComboMenu) return;
        const items = openComboMenu.querySelectorAll('li:not(.empty)');
        if (!items.length) return;
        comboActiveIdx += delta;
        if (comboActiveIdx < 0) comboActiveIdx = items.length - 1;
        if (comboActiveIdx >= items.length) comboActiveIdx = 0;
        items.forEach((li, i) => li.classList.toggle('active', i === comboActiveIdx));
        items[comboActiveIdx].scrollIntoView({ block: 'nearest' });
    }

    function selectComboItem(inputId, name) {
        const n = (name || '').trim();
        if (!n) return;
        PROJECT_INPUTS.forEach((id) => setProjectInputValue(id, n));
        closeComboMenu();
        activateProjectGlobally(n);
    }

    function fillProjectsDatalist(projects) {
        knownProjects = Array.isArray(projects) ? projects.slice() : [];
        refreshOpenComboMenu();
    }

    function ensureDatalistOption(name) {
        const n = (name || '').trim();
        if (!n || knownProjects.includes(n)) return;
        knownProjects.push(n);
        knownProjects.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
        fillProjectsDatalist(knownProjects);
    }

    async function loadProjectsDatalist() {
        let projects = [];
        try {
            const r = await fetch('/api/projects');
            const data = await r.json();
            projects = data.projects || [];
        } catch (e) {
            console.error('loadProjectsDatalist', e);
        }
        fillProjectsDatalist(projects);
        const cur = getCurrentProject();
        if (cur) ensureDatalistOption(cur);
        return projects;
    }

    async function loadProjectSelects() {
        return loadProjectsDatalist();
    }

    async function fetchLayout(projectName) {
        const key = (projectName || '').trim();
        if (!key) return null;
        if (layoutCache[key]) return layoutCache[key];
        try {
            const r = await fetch(`/api/projects/${encodeURIComponent(key)}/layout`);
            if (!r.ok) return null;
            const data = await r.json();
            layoutCache[key] = data;
            return data;
        } catch (_) {
            return null;
        }
    }

    function toWinPath(p) {
        return (p || '').replace(/\//g, '\\');
    }

    function setPathFields(ids, value, readonly) {
        ids.forEach((id) => {
            const el = $(id);
            if (!el) return;
            if (value != null) el.value = toWinPath(value);
            el.readOnly = !!readonly;
            el.classList.toggle('path-readonly', !!readonly);
        });
    }

    function applyLayoutToTab(tabKey, layout) {
        if (!layout) return;
        if (tabKey === 'split') {
            const el = $('out-dir');
            if (el) {
                if (!el.value.trim()) el.value = toWinPath(layout.panels);
                el.readOnly = false;
                el.classList.remove('path-readonly');
            }
        } else if (tabKey === 'up') {
            setPathFields(['up-panels', 'up-output'], null, true);
            $('up-panels').value = toWinPath(layout.panels);
            $('up-output').value = toWinPath(layout.upscale);
        } else if (tabKey === 'vid') {
            setPathFields(['vid-panels', 'vid-output'], null, true);
            $('vid-panels').value = toWinPath(layout.panels);
            $('vid-output').value = toWinPath(layout.video);
        } else if (tabKey === 's2a') {
            setPathFields(['s2a-panels-dir', 's2a-json-path'], null, true);
            $('s2a-panels-dir').value = toWinPath(layout.panels);
            $('s2a-json-path').value = toWinPath(layout.stage_2a_json);
            if (hooks().syncStory2aFromUi) hooks().syncStory2aFromUi();
        }
    }

    function setAllProjectCheckboxes(enabled) {
        syncingProjectCheckboxes = true;
        TAB_KEYS.forEach((tabKey) => {
            const cb = $(TAB_CONFIG[tabKey].use);
            if (cb) cb.checked = !!enabled;
        });
        syncingProjectCheckboxes = false;
    }

    function releaseAllPathFields() {
        TAB_KEYS.forEach((tabKey) => releasePathFields(tabKey));
    }

    async function activateProjectGlobally(name) {
        const n = (name || '').trim();
        if (!n) {
            toast('Укажите имя проекта', 'err');
            return null;
        }
        setCurrentProject(n);
        ensureDatalistOption(n);
        layoutCache = {};
        const layout = await fetchLayout(n);
        if (!layout) {
            toast('Не удалось загрузить layout проекта', 'err');
            return null;
        }
        setAllProjectCheckboxes(true);
        TAB_KEYS.forEach((tabKey) => applyLayoutToTab(tabKey, layout));
        scheduleSave();
        return layout;
    }

    async function applyProjectPaths(tabKey) {
        const cfg = TAB_CONFIG[tabKey];
        if (!cfg || !isProjectMode(tabKey)) return null;
        return activateProjectGlobally(readProjectForTab(tabKey));
    }

    function releasePathFields(tabKey) {
        const cfg = TAB_CONFIG[tabKey];
        if (!cfg) return;
        const ids = [...(cfg.pathFields || []), ...(cfg.extraPathFields || [])];
        ids.forEach((id) => {
            const el = $(id);
            if (!el) return;
            el.readOnly = false;
            el.classList.remove('path-readonly');
        });
    }

    async function onProjectCheckboxChange(sourceTabKey) {
        if (syncingProjectCheckboxes) return;
        const enabled = isProjectMode(sourceTabKey);
        setAllProjectCheckboxes(enabled);
        if (enabled) {
            await activateProjectGlobally(readProjectForTab(sourceTabKey));
        } else {
            releaseAllPathFields();
            scheduleSave();
        }
    }

    function collectWorkspaceGlobal() {
        return { current_project: getCurrentProject() };
    }

    function collectWorkspaceSection(tabKey) {
        const cfg = TAB_CONFIG[tabKey];
        if (!cfg) return {};
        const out = {
            use_project: isProjectMode(tabKey),
            project: readProjectForTab(tabKey),
        };
        if (tabKey === 'split' && $('split-folder-path')) {
            out.folder_path = $('split-folder-path').value.trim();
        }
        return out;
    }

    function applyWorkspaceGlobal(g) {
        if (!g) return;
        if (g.current_project) setCurrentProject(g.current_project, { syncInputs: true });
    }

    function applyWorkspaceSection(tabKey, section) {
        if (!section) return;
        if (section.project) setCurrentProject(section.project, { syncInputs: true });
        if (section.use_project != null) {
            setAllProjectCheckboxes(!!section.use_project);
        }
        if (tabKey === 'split' && section.folder_path && $('split-folder-path')) {
            $('split-folder-path').value = section.folder_path;
        }
        if (section.use_project && section.project) {
            activateProjectGlobally(section.project);
        } else if (!section.use_project) {
            releaseAllPathFields();
        }
    }

    function bindProjectInputs() {
        PROJECT_INPUTS.forEach((id) => {
            const { input, toggle } = getComboElements(id);
            if (!input) return;

            input.addEventListener('input', () => {
                const v = input.value;
                PROJECT_INPUTS.forEach((otherId) => {
                    if (otherId !== id) setProjectInputValue(otherId, v);
                });
                openComboForInput(id, { filter: true });
            });
            input.addEventListener('focus', () => openComboForInput(id, { filter: false }));
            input.addEventListener('click', () => openComboForInput(id, { filter: false }));
            input.addEventListener('keydown', (e) => {
                const menu = getComboElements(id).menu;
                const isOpen = menu && !menu.hidden;

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    if (!isOpen) openComboForInput(id, { filter: false });
                    else moveComboHighlight(1);
                    return;
                }
                if (e.key === 'ArrowUp' && isOpen) {
                    e.preventDefault();
                    moveComboHighlight(-1);
                    return;
                }
                if (e.key === 'Escape' && isOpen) {
                    e.preventDefault();
                    closeComboMenu();
                    return;
                }
                if (e.key !== 'Enter') return;

                e.preventDefault();
                if (isOpen && comboActiveIdx >= 0) {
                    const items = menu.querySelectorAll('li:not(.empty)');
                    if (items[comboActiveIdx]) {
                        selectComboItem(id, items[comboActiveIdx].textContent);
                        return;
                    }
                }
                closeComboMenu();
                activateProjectGlobally(input.value.trim());
            });
            input.addEventListener('change', () => {
                const v = input.value.trim();
                if (v && knownProjects.includes(v)) activateProjectGlobally(v);
            });

            toggle?.addEventListener('mousedown', (e) => {
                e.preventDefault();
                if (openComboMenu === getComboElements(id).menu && !openComboMenu?.hidden) {
                    closeComboMenu();
                } else {
                    input.focus();
                    openComboForInput(id, { filter: false });
                }
            });
        });

        document.addEventListener('mousedown', (e) => {
            if (!e.target.closest('.project-combo')) closeComboMenu();
        });

        TAB_KEYS.forEach((tabKey) => {
            const cb = $(TAB_CONFIG[tabKey].use);
            if (cb) cb.addEventListener('change', () => onProjectCheckboxChange(tabKey));
        });
    }

    function projectPayloadForApi(tabKey) {
        if (!isProjectMode(tabKey)) return null;
        const name = readProjectForTab(tabKey);
        return name || null;
    }

    function propagateAfterSplitExport(layout) {
        if (!layout) return;
        if (isProjectMode('up')) {
            $('up-panels').value = toWinPath(layout.panels);
        }
        if (isProjectMode('vid')) {
            $('vid-panels').value = toWinPath(layout.panels);
        }
        if (isProjectMode('s2a')) {
            $('s2a-panels-dir').value = toWinPath(layout.panels);
            if (hooks().syncStory2aFromUi) hooks().syncStory2aFromUi();
        }
        scheduleSave();
    }

    function init() {
        bindProjectInputs();
        loadProjectsDatalist();
    }

    window.ComicSplitWorkspace = {
        TAB_CONFIG,
        init,
        loadProjectSelects,
        loadProjectsDatalist,
        getCurrentProject,
        setCurrentProject,
        setProjectInputValue,
        setSelectProjectValue: setProjectInputValue,
        isProjectMode,
        readProjectForTab,
        applyProjectPaths,
        activateProjectGlobally,
        collectWorkspaceGlobal,
        collectWorkspaceSection,
        applyWorkspaceGlobal,
        applyWorkspaceSection,
        projectPayloadForApi,
        propagateAfterSplitExport,
        fetchLayout,
        toWinPath,
    };
})();

// Selector de jugadores de las convocatorias: búsqueda, filtros y contador.
(function () {
  const normalize = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  document.querySelectorAll('[data-selector]').forEach(function (root) {
    const picks = Array.from(root.querySelectorAll('.z-pick'));
    const search = root.querySelector('[data-selector-search]');
    const count = root.querySelector('[data-selector-count]');
    const hint = root.querySelector('[data-selector-hint]');
    const empty = root.querySelector('[data-selector-empty]');
    const min = parseInt(root.dataset.min, 10) || 0;
    let position = '';

    const box = (p) => p.querySelector('input[type="checkbox"]');

    function refresh() {
      const q = normalize(search.value);
      let visible = 0;
      picks.forEach(function (p) {
        const matchesText = !q || normalize(p.dataset.name).includes(q);
        const matchesPos = !position
          || (position === 'selected' ? box(p).checked : p.dataset.position === position);
        p.hidden = !(matchesText && matchesPos);
        if (!p.hidden) visible++;
      });
      empty.hidden = visible > 0 || !picks.length;

      const n = picks.filter((p) => box(p).checked).length;
      count.textContent = n;
      hint.textContent = min && n < min ? interpolate(gettext('Mínimo %(min)s para cerrar la convocatoria'), {min: min}, true) : '';
    }

    search.addEventListener('input', refresh);
    root.querySelectorAll('[data-selector-filter]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        position = btn.dataset.selectorFilter;
        root.querySelectorAll('[data-selector-filter]').forEach((b) => b.classList.toggle('active', b === btn));
        refresh();
      });
    });
    root.querySelector('[data-selector-all]').addEventListener('click', function () {
      picks.forEach((p) => { if (!p.hidden) box(p).checked = true; });
      refresh();
    });
    root.querySelector('[data-selector-none]').addEventListener('click', function () {
      picks.forEach((p) => { box(p).checked = false; });
      refresh();
    });
    picks.forEach((p) => box(p).addEventListener('change', refresh));
    refresh();
  });
})();

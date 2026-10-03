/*
 * Formulario de partido:
 *  - Modo Amistoso: oculta el tipo de partido (Enfrentamiento, Reto, Play Off).
 *  - Cards de local y visitante: al elegir un equipo en el desplegable se
 *    actualizan su nombre y su foto.
 */
(function () {
  const form = document.querySelector('[data-match-form]');
  if (!form) return;

  const typeRow = form.querySelector('[data-match-type-row]');
  const modes = form.querySelectorAll('input[name="mode"]');
  function syncMode() {
    const checked = form.querySelector('input[name="mode"]:checked');
    const friendly = checked && checked.value === 'amistoso';
    if (typeRow) typeRow.hidden = friendly;
    modes.forEach((r) => r.closest('label').classList.toggle('active', r.checked));
  }
  modes.forEach((r) => r.addEventListener('change', syncMode));
  syncMode();

  form.querySelectorAll('[data-team-card]').forEach((card) => {
    const select = card.querySelector('select');
    const name = card.querySelector('[data-team-name]');
    const photo = card.querySelector('[data-team-photo]');
    const empty = name.classList.contains('is-empty') ? name.textContent : gettext('Elige equipo');
    function sync() {
      const option = select.options[select.selectedIndex];
      const chosen = option && option.value !== '';
      name.textContent = chosen ? option.textContent.trim() : empty;
      name.classList.toggle('is-empty', !chosen);
      photo.src = (chosen && option.dataset.photo) || card.dataset.defaultPhoto;
    }
    select.addEventListener('change', sync);
    sync();
  });
})();

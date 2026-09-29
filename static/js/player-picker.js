/*
 * Selector con búsqueda para listas largas de jugadores.
 *
 * Uso: <select data-picker data-placeholder="Buscar jugador..."> ... </select>
 * El <select> original se oculta pero sigue siendo el que se envía en el
 * formulario, y recibe un evento "change" al elegir una opción (así siguen
 * funcionando los onchange="this.form.submit()" existentes).
 */
(function () {
  const normalize = (text) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  function enhance(select) {
    if (select.dataset.pickerReady) return;
    select.dataset.pickerReady = '1';

    const options = Array.from(select.options)
      .filter((o) => o.value !== '')
      .map((o) => ({ value: o.value, label: o.textContent.trim(), key: normalize(o.textContent) }));

    const wrap = document.createElement('div');
    wrap.className = 'z-picker';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'z-picker-input';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.placeholder = select.dataset.placeholder || 'Buscar...';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-autocomplete', 'list');
    if (select.id) {
      // El <label for="..."> apunta ahora al buscador
      input.id = select.id + '-search';
      document.querySelectorAll(`label[for="${select.id}"]`).forEach((l) => l.setAttribute('for', input.id));
    }
    const list = document.createElement('ul');
    list.className = 'z-picker-list';
    list.setAttribute('role', 'listbox');
    list.id = (select.id || 'picker') + '-list-' + Math.random().toString(36).slice(2, 7);
    input.setAttribute('aria-controls', list.id);

    select.hidden = true;
    select.tabIndex = -1;
    select.parentNode.insertBefore(wrap, select);
    wrap.append(input, list, select);

    let active = -1;
    let shown = [];
    const current = () => options.find((o) => o.value === select.value);
    const showSelected = () => { input.value = current() ? current().label : ''; };

    function render(query) {
      const q = normalize(query || '');
      shown = q ? options.filter((o) => o.key.includes(q)) : options;
      list.innerHTML = '';
      if (!shown.length) {
        const li = document.createElement('li');
        li.className = 'z-picker-empty';
        li.textContent = 'Sin resultados';
        list.appendChild(li);
      }
      shown.forEach((o, i) => {
        const li = document.createElement('li');
        li.className = 'z-picker-option';
        li.id = `${list.id}-${i}`;
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', String(o.value === select.value));
        li.textContent = o.label;
        li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(o); });
        list.appendChild(li);
      });
      setActive(shown.findIndex((o) => o.value === select.value));
    }

    function setActive(i) {
      active = i;
      list.querySelectorAll('.z-picker-option').forEach((li, n) => li.classList.toggle('is-active', n === i));
      const li = list.querySelector('.is-active');
      if (li) { input.setAttribute('aria-activedescendant', li.id); li.scrollIntoView({ block: 'nearest' }); }
      else input.removeAttribute('aria-activedescendant');
    }

    function open() { wrap.classList.add('is-open'); input.setAttribute('aria-expanded', 'true'); }
    function close() { wrap.classList.remove('is-open'); input.setAttribute('aria-expanded', 'false'); showSelected(); }

    function choose(o) {
      const changed = select.value !== o.value;
      select.value = o.value;
      close();
      input.blur();
      if (changed) select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    input.addEventListener('focus', () => { input.select(); render(''); open(); });
    input.addEventListener('input', () => { render(input.value); open(); setActive(shown.length ? 0 : -1); });
    input.addEventListener('blur', () => setTimeout(close, 120));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); open(); setActive(Math.min(active + 1, shown.length - 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(active - 1, 0)); }
      else if (e.key === 'Enter') { if (wrap.classList.contains('is-open') && shown[active]) { e.preventDefault(); choose(shown[active]); } }
      else if (e.key === 'Escape') { close(); input.blur(); }
    });

    showSelected();
  }

  function init() { document.querySelectorAll('select[data-picker]').forEach(enhance); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

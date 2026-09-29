// Alineación de parejas: evita repetir jugadores, calcula el orden por puntos
// y solo deja guardar cuando las 5 parejas están completas.
(function () {
  const form = document.querySelector('[data-lineup]');
  if (!form) return;
  const slots = Array.from(form.querySelectorAll('[data-slot]'));
  const selects = Array.from(form.querySelectorAll('select[data-player]'));
  const list = document.getElementById('pair-order-list');

  function refresh() {
    const chosen = selects.map((s) => s.value).filter(Boolean);
    selects.forEach(function (s) {
      Array.from(s.options).forEach(function (o) {
        const takenElsewhere = o.value && o.value !== s.value && chosen.includes(o.value);
        o.disabled = takenElsewhere;
        o.hidden = takenElsewhere;
      });
    });

    const pairs = [];
    slots.forEach(function (slot) {
      const [a, b] = slot.querySelectorAll('select[data-player]');
      if (!a.value || !b.value) return;
      const oa = a.selectedOptions[0], ob = b.selectedOptions[0];
      pairs.push({
        gameId: slot.dataset.gameId || null,
        player1Id: a.value,
        player2Id: b.value,
        label: `${oa.textContent.trim()} y ${ob.textContent.trim()}`,
        points: (parseFloat(oa.dataset.points) || 0) + (parseFloat(ob.dataset.points) || 0),
      });
    });
    pairs.sort((x, y) => y.points - x.points);

    list.innerHTML = '';
    pairs.forEach(function (p, i) {
      const li = document.createElement('li');
      li.textContent = `${p.label} · ${Math.round(p.points * 10) / 10} pts SNP · partido de ${i < 2 ? 3 : 2} puntos`;
      list.appendChild(li);
    });

    const complete = pairs.length === slots.length;
    form.querySelector('[data-lineup-output]').value = JSON.stringify(
      pairs.map((p) => ({ gameId: p.gameId, player1Id: p.player1Id, player2Id: p.player2Id }))
    );
    form.querySelector('[data-lineup-count]').textContent = pairs.length;
    form.querySelector('[data-lineup-hint]').textContent = complete ? '' : 'Completa todas las parejas para guardar';
    form.querySelector('[data-lineup-save]').disabled = !complete;
  }

  selects.forEach((s) => s.addEventListener('change', refresh));
  form.addEventListener('submit', function () {
    form.querySelector('[data-lineup-save]').disabled = true; // evita el doble envío
  });
  refresh();
})();

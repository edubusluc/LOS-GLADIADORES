/*
 * Aviso de nombres parecidos al crear un equipo o un jugador.
 *
 * Uso: <form data-similar-check> con <input type="hidden" name="confirm_similar">
 * y el modal de core/templates/includes/similar_modal.html.
 * Antes de enviar, el formulario se manda a la misma URL con la cabecera
 * X-Similar-Check (sin las fotos): si es válido y hay nombres parecidos se
 * muestra el modal y solo se crea si el usuario pulsa «Continuar».
 */
(function () {
  const form = document.querySelector('form[data-similar-check]');
  const modalEl = document.getElementById('similarModal');
  if (!form || !modalEl) return;

  const list = modalEl.querySelector('[data-similar-list]');
  const confirmInput = form.querySelector('input[name="confirm_similar"]');
  const send = () => HTMLFormElement.prototype.submit.call(form);
  const modal = () => bootstrap.Modal.getOrCreateInstance(modalEl);
  let checking = false;

  function show(names) {
    list.replaceChildren(...names.map((name) => {
      const li = document.createElement('li');
      li.textContent = name;
      return li;
    }));
    modal().show();
  }

  form.addEventListener('submit', function (event) {
    if (confirmInput.value === '1' || !window.fetch || !window.bootstrap) return;
    event.preventDefault();
    if (checking) return;
    checking = true;

    const data = new FormData(form);
    for (const [key, value] of Array.from(data.entries())) {
      if (value instanceof File) data.delete(key);
    }
    fetch(form.action || window.location.href, {
      method: 'POST',
      body: data,
      headers: { 'X-Similar-Check': '1' },
      credentials: 'same-origin',
    })
      .then((response) => (response.ok ? response.json() : null))
      .then((result) => {
        if (result && result.valid && result.similar.length) show(result.similar);
        else send(); // sin parecidos (o con errores, que muestra el servidor)
      })
      .catch(send)
      .finally(() => { checking = false; });
  });

  modalEl.querySelector('[data-similar-continue]').addEventListener('click', function () {
    confirmInput.value = '1';
    send();
  });

  // El servidor ya encontró nombres parecidos (envío sin JavaScript o sin comprobar).
  if (modalEl.dataset.open === '1' && window.bootstrap) modal().show();
})();

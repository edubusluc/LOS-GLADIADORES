from playwright.sync_api import sync_playwright

def scrape_scores(url, username, password):
    players_scores = []  # Lista para almacenar los jugadores y sus puntuaciones
    page_number = 2

    with sync_playwright() as p:
        try:
            # Lanzar el navegador
            browser = p.chromium.launch(headless=True)  # Usa headless=False si deseas ver el navegador
            page = browser.new_page()

            # URL de inicio de sesión
            login_url = 'https://intranet.seriesnacionalesdepadel.com/usuario/login'
            
            # Navegar a la página de inicio de sesión
            page.goto(login_url)

            # Completar el formulario de inicio de sesión
            page.fill('input[name="email"]', username)
            page.fill('input[name="password"]', password)
            page.click('input[type="submit"][value="Entrar"]')  # Asegúrate de que este selector sea correcto

            page.goto(url)

            # Esperar un momento antes de procesar la tabla
            page.wait_for_timeout(3000)  # Espera 3 segundos para ver la página antes de procesar

            while True:  # Bucle para manejar la paginación
                page.wait_for_selector('table.results')  # Esperar a que la tabla esté visible

                results_table = page.query_selector('table.results')

                if results_table:
                    rows = results_table.query_selector_all('tbody tr')
                    
                    for row in rows:
                        # Obtener las celdas específicas
                        name_cell = row.query_selector('td:nth-child(2)')  # Segunda celda para el nombre
                        value_cell = row.query_selector('td:nth-child(3)')  # Tercera celda para el valor

                        # Extraer el texto de las celdas
                        player_name = name_cell.inner_text().strip() if name_cell else ''
                        player_value = value_cell.inner_text().strip() if value_cell else None  # Usar None si no hay celda

                        # Limpiar el nombre del jugador
                        player_name_cleaned = ' '.join(player_name.split()[:-1])  # Eliminar el último elemento (500 o Future)

                        # Limpiar el valor y asignar 0 si es None o vacío
                        if player_value is None or player_value == '':
                            snp_score = 0.0  # Asignar puntuación de 0 si no hay valor
                        else:
                            if '/' in player_value:
                                player_value_cleaned = player_value.split('/')[0].strip()  # Tomar la parte anterior al '/'
                            else:
                                player_value_cleaned = player_value.strip()

                            # Convertir el valor a float
                            try:
                                snp_score = float(player_value_cleaned.replace('.', '').replace(',', '.'))
                            except ValueError:
                                print(f"Error al convertir la puntuación para {player_name_cleaned}. Valor: {player_value_cleaned}")
                                snp_score = 0.0  # Asignar 0 si hay un error en la conversión

                        # Añadir a la lista de resultados
                        players_scores.append({
                            'name': player_name_cleaned,
                            'score': snp_score
                        })

                else:
                    print("No se encontró la tabla de resultados.")
                    break  # Salir si no se encuentra la tabla

                # Intentar navegar a la siguiente página
                try:
                    # Seleccionar el botón de la siguiente página usando el atributo num_pagina
                    next_button = page.query_selector(f'a.pag_numerada.page-link[num_pagina="{page_number}"]')
                    if next_button and next_button.is_visible():
                        next_button.click()  # Hacer clic en el botón de siguiente
                        page_number += 1  # Incrementar el número de página
                        page.wait_for_timeout(3000)  # Esperar que cargue la siguiente página (ajusta según sea necesario)
                    else:
                        print("No hay más páginas.")
                        break  # Salir si no hay más páginas
                except Exception as e:
                    print(f"Ocurrió un error al navegar a la siguiente página: {e}")
                    break  # Salir si hay un error

        except Exception as e:
            print(f"Ocurrió un error: {e}")
        
        finally:
            # Cerrar el navegador
            browser.close()

    return players_scores  # Devolver la lista de jugadores y puntuaciones

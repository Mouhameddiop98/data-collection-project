"""
Scraping + nettoyage — Source 1 : Books to Scrape
https://books.toscrape.com/catalogue/page-1.html

Adapté à ton style de navigation explicite :
- Parcours des conteneurs 'article.product_pod'
- Clic sur le livre pour ouvrir sa sous-page et extraire l'ensemble des détails

Variables extraites :
V1_titre               : Titre du livre (h1)
V2_prix                : Prix en £ (float)
V3_disponibilite       : Statut (ex: "In stock")
V4_nb_produits_page    : Nombre d'exemplaires en stock (int)
V5_note                : Note convertie de 1 à 5 (int)
V6_nb_reviews          : Nombre de commentaires (int)
V7_description         : Description du livre
V8_categorie           : Type de produit / Catégorie
V9_tax                 : Taxe en £ (float)
"""

import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver_factory import get_driver

# Dictionnaire de conversion conforme à ton code
CONVERSION = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def scrape_books(max_pages: int = 50, fetch_details: bool = True, progress_callback=None) -> pd.DataFrame:
    driver = get_driver()
    df_final = pd.DataFrame()

    try:
        for page in range(1, max_pages + 1):
            url = f"https://books.toscrape.com/catalogue/page-{page}.html"
            driver.get(url)

            # Attente du chargement de la page catalogue
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.product_pod"))
                )
            except TimeoutException:
                break  # Plus de pages à charger

            containers = driver.find_elements(By.CSS_SELECTOR, "article.product_pod")
            if not containers:
                break

            data = []
            n_products = len(containers)

            for i in range(n_products):
                try:
                    # Ré-ouvrir la page courante et ré-instancier le container (évite le Stale Element)
                    driver.get(url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article.product_pod"))
                    )
                    containers = driver.find_elements(By.CSS_SELECTOR, "article.product_pod")
                    container = containers[i]

                    # Clic pour aller sur la sous-page du livre
                    link = container.find_element(By.CSS_SELECTOR, "h3 a")
                    link.click()

                    # --- Extraction dans la sous-page (selon tes sélecteurs exacts) ---
                    title = driver.find_element(By.TAG_NAME, "h1").text

                    price_text = driver.find_element(By.CSS_SELECTOR, "p.price_color").text
                    prix = float(price_text.replace("£", "").replace("Â", "").strip())

                    availability_text = driver.find_element(By.CSS_SELECTOR, "p.instock.availability").text
                    values = availability_text.split(" (")
                    disponibilite = values[0].strip()
                    nombre_de_produit = int(values[1].split()[0]) if len(values) > 1 else 0

                    rating_class = (
                        driver.find_element(By.CSS_SELECTOR, "p.star-rating")
                        .get_attribute("class")
                        .split()[-1]
                    )
                    note = CONVERSION.get(rating_class, None)

                    reviews_text = driver.find_element(
                        By.XPATH, "//th[text()='Number of reviews']/following-sibling::td"
                    ).text
                    nombre_de_review = int(reviews_text)

                    # Description (gestion de l'exception si absente)
                    try:
                        description = driver.find_element(By.CSS_SELECTOR, "div#product_description ~ p").text
                    except NoSuchElementException:
                        description = ""

                    type_de_produit = driver.find_element(
                        By.XPATH, "//th[text()='Product Type']/following-sibling::td"
                    ).text

                    tax_text = driver.find_element(
                        By.XPATH, "//th[text()='Tax']/following-sibling::td"
                    ).text
                    tax = float(tax_text.replace("£", "").replace("Â", "").strip())

                    # Dictionnaire ré-aligné sur les clés attendues par l'application Streamlit (V1..V9)
                    dic = {
                        "V1_titre": title,
                        "V2_prix": prix,
                        "V3_disponibilite": disponibilite,
                        "V4_nb_produits_page": nombre_de_produit,
                        "V5_note": note,
                        "V6_nb_reviews": nombre_de_review,
                        "V7_description": description,
                        "V8_categorie": type_de_produit,
                        "V9_tax": tax,
                        "page": page,
                    }

                    data.append(dic)

                except Exception:
                    pass

            # Concaténation par page
            df = pd.DataFrame(data)
            df_final = pd.concat([df_final, df], axis=0).reset_index(drop=True)

            if progress_callback:
                progress_callback(page, n_products)

            time.sleep(0.3)

    finally:
        driver.quit()

    if not df_final.empty:
        df_final = df_final.drop_duplicates(subset=["V1_titre", "V2_prix"]).reset_index(drop=True)

    return df_final


if __name__ == "__main__":
    # Test rapide en local sur 1 page
    df_test = scrape_books(max_pages=1)
    print(df_test.head())
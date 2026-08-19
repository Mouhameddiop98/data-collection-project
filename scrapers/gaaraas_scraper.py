"""
Scraping + nettoyage — Source 2 : Gaaraas (annonces auto Dakar)
Sélecteurs CSS ciblés sur les cartes d'annonces (a.common-ad-card).

Variables extraites :
V1_marque          : Marque du véhicule
V2_modele          : Modèle du véhicule
V3_annee           : Année de fabrication (int)
V4_prix            : Prix en CFA (float)
V5_kilometrage     : Kilométrage en km (float)
V6_boite_vitesse   : Type de boîte de vitesse (automatique / manuelle)
V7_region          : Région de vente
"""

import re
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .driver_factory import get_driver


def _clean_number(text: str) -> float:
    """Extrait uniquement les chiffres d'une chaîne texte (ex: '4 500 000 CFA' -> 4500000.0)."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    return float(digits) if digits else None


def _clean_int(text: str) -> int:
    """Extrait un entier (ex: '2018' -> 2018)."""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else None


def scrape_gaaraas(max_pages: int = 100, progress_callback=None) -> pd.DataFrame:
    driver = get_driver()
    df_final = pd.DataFrame()

    try:
        for i in range(1, max_pages + 1):
            url = f"https://www.gaaraas.com/petites-annonces-voitures?page={i}"
            driver.get(url)

            # Attente du chargement des annonces
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.common-ad-card"))
                )
            except TimeoutException:
                break  # Fin des pages disponibles

            containers = driver.find_elements(By.CSS_SELECTOR, "a.common-ad-card")
            if not containers:
                break

            data = []
            for container in containers:
                try:
                    # Extraction du titre et séparation en [Année, Marque, Modèle]
                    title = container.find_element(
                        By.CSS_SELECTOR, "div.specification-section h4"
                    ).get_attribute("title")
                    titre = title.strip().split(" ", 2)

                    # Extraction des éléments spécifiques selon tes sélecteurs CSS
                    prix = container.find_elements(
                        By.CSS_SELECTOR, ".price, .price-tag, .ad-price"
                    )
                    km = container.find_elements(
                        By.CSS_SELECTOR, "div.ad-vehicle-mileage .value"
                    )
                    boite = container.find_elements(
                        By.CSS_SELECTOR, ".transmission, .boite"
                    )
                    region = container.find_elements(By.CSS_SELECTOR, ".location")

                    # Structuration selon la nomenclature V1...V7 de l'application
                    dic = {
                        "V1_marque": titre[1].upper() if len(titre) > 1 else None,
                        "V2_modele": titre[2] if len(titre) > 2 else None,
                        "V3_annee": _clean_int(titre[0]) if len(titre) > 0 else None,
                        "V4_prix": _clean_number(prix[0].text) if prix else None,
                        "V5_kilometrage": _clean_number(km[0].text) if km else None,
                        "V6_boite_vitesse": boite[0].text.strip() if boite else None,
                        "V7_region": region[0].text.strip() if region else None,
                        "page": i,
                    }
                    data.append(dic)
                except Exception:
                    pass

            df = pd.DataFrame(data)
            df_final = pd.concat([df_final, df], axis=0).reset_index(drop=True)

            if progress_callback:
                progress_callback(i, len(containers))

            time.sleep(0.3)

    finally:
        driver.quit()

    if not df_final.empty:
        # Suppression des éventuels doublons et des lignes sans prix / marque
        df_final = df_final.drop_duplicates().reset_index(drop=True)
        df_final = df_final.dropna(subset=["V1_marque", "V4_prix"]).reset_index(drop=True)

    return df_final


if __name__ == "__main__":
    # Test rapide sur 1 page
    df_test = scrape_gaaraas(max_pages=1)
    print(df_test.head())
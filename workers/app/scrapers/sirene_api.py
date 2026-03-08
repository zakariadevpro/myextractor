import logging

import httpx

from app.scrapers.base import BaseScraper, ScrapedLead
from app.scrapers.proxy_pool import proxy_pool
from app.scrapers.resilience import jitter_sleep, pick_user_agent, run_with_retries

logger = logging.getLogger(__name__)

# API Sirene - recherche.entreprises.api.gouv.fr (gratuit, pas de clé API)
# Documentation: https://recherche-entreprises.api.gouv.fr/docs/
BASE_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Mapping code département → région
DEPT_TO_REGION = {
    "01": "Auvergne-Rhône-Alpes",
    "03": "Auvergne-Rhône-Alpes",
    "07": "Auvergne-Rhône-Alpes",
    "15": "Auvergne-Rhône-Alpes",
    "26": "Auvergne-Rhône-Alpes",
    "38": "Auvergne-Rhône-Alpes",
    "42": "Auvergne-Rhône-Alpes",
    "43": "Auvergne-Rhône-Alpes",
    "63": "Auvergne-Rhône-Alpes",
    "69": "Auvergne-Rhône-Alpes",
    "73": "Auvergne-Rhône-Alpes",
    "74": "Auvergne-Rhône-Alpes",
    "21": "Bourgogne-Franche-Comté",
    "25": "Bourgogne-Franche-Comté",
    "39": "Bourgogne-Franche-Comté",
    "58": "Bourgogne-Franche-Comté",
    "70": "Bourgogne-Franche-Comté",
    "71": "Bourgogne-Franche-Comté",
    "89": "Bourgogne-Franche-Comté",
    "90": "Bourgogne-Franche-Comté",
    "22": "Bretagne",
    "29": "Bretagne",
    "35": "Bretagne",
    "56": "Bretagne",
    "18": "Centre-Val de Loire",
    "28": "Centre-Val de Loire",
    "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire",
    "41": "Centre-Val de Loire",
    "45": "Centre-Val de Loire",
    "08": "Grand Est",
    "10": "Grand Est",
    "51": "Grand Est",
    "52": "Grand Est",
    "54": "Grand Est",
    "55": "Grand Est",
    "57": "Grand Est",
    "67": "Grand Est",
    "68": "Grand Est",
    "88": "Grand Est",
    "02": "Hauts-de-France",
    "59": "Hauts-de-France",
    "60": "Hauts-de-France",
    "62": "Hauts-de-France",
    "80": "Hauts-de-France",
    "75": "Île-de-France",
    "77": "Île-de-France",
    "78": "Île-de-France",
    "91": "Île-de-France",
    "92": "Île-de-France",
    "93": "Île-de-France",
    "94": "Île-de-France",
    "95": "Île-de-France",
    "14": "Normandie",
    "27": "Normandie",
    "50": "Normandie",
    "61": "Normandie",
    "76": "Normandie",
    "16": "Nouvelle-Aquitaine",
    "17": "Nouvelle-Aquitaine",
    "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine",
    "24": "Nouvelle-Aquitaine",
    "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine",
    "47": "Nouvelle-Aquitaine",
    "64": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine",
    "86": "Nouvelle-Aquitaine",
    "87": "Nouvelle-Aquitaine",
    "09": "Occitanie",
    "11": "Occitanie",
    "12": "Occitanie",
    "30": "Occitanie",
    "31": "Occitanie",
    "32": "Occitanie",
    "34": "Occitanie",
    "46": "Occitanie",
    "48": "Occitanie",
    "65": "Occitanie",
    "66": "Occitanie",
    "81": "Occitanie",
    "82": "Occitanie",
    "44": "Pays de la Loire",
    "49": "Pays de la Loire",
    "53": "Pays de la Loire",
    "72": "Pays de la Loire",
    "85": "Pays de la Loire",
    "04": "Provence-Alpes-Côte d'Azur",
    "05": "Provence-Alpes-Côte d'Azur",
    "06": "Provence-Alpes-Côte d'Azur",
    "13": "Provence-Alpes-Côte d'Azur",
    "83": "Provence-Alpes-Côte d'Azur",
    "84": "Provence-Alpes-Côte d'Azur",
    "2A": "Corse",
    "2B": "Corse",
}


class SireneApiScraper(BaseScraper):
    """Scraper using the free French government Sirene API.

    This API does not require authentication and provides official
    company registry data (SIREN, SIRET, NAF codes, addresses).
    Rate limit: ~7 requests/second.
    """

    source_name = "sirene_api"

    def __init__(self):
        self._default_headers = {
            "User-Agent": pick_user_agent(),
            "Accept": "application/json",
        }

    async def search(
        self,
        keywords: list[str],
        city: str | None = None,
        radius_km: int | None = None,
        max_results: int = 100,
    ) -> list[ScrapedLead]:
        leads: list[ScrapedLead] = []

        query_parts = list(keywords)
        if city:
            query_parts.append(city)
        query = " ".join(query_parts)

        per_page = min(max_results, 25)  # API max is 25 per page
        page = 1
        max_pages = (max_results // per_page) + 1

        while len(leads) < max_results and page <= max_pages:
            params = {
                "q": query,
                "per_page": per_page,
                "page": page,
                "mtm_campaign": "winaity",
            }

            try:
                data = await run_with_retries(
                    f"sirene_api.page_{page}",
                    lambda p=params: self._fetch_page(p),
                )
                # Small delay to keep API usage smooth and avoid burst throttling.
                await jitter_sleep(0.15, 0.45)
            except Exception as e:
                logger.error(f"Sirene API request failed (page {page}): {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for company in results:
                if len(leads) >= max_results:
                    break

                lead = self._parse_company(company)
                if lead:
                    leads.append(lead)

            total_results = data.get("total_results", 0)
            if page * per_page >= total_results:
                break

            page += 1

        logger.info(f"Sirene API: found {len(leads)} companies for '{query}'")
        return leads

    async def _fetch_page(self, params: dict) -> dict:
        proxy_url = proxy_pool.next_proxy_url()
        async with httpx.AsyncClient(
            timeout=30.0,
            headers=self._default_headers,
            proxy=proxy_url,
        ) as client:
            response = await client.get(BASE_URL, params=params)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"Retryable Sirene status code: {response.status_code}"
                )
            response.raise_for_status()
            return response.json()

    def _parse_company(self, company: dict) -> ScrapedLead | None:
        """Parse a company from Sirene API response into a ScrapedLead."""
        try:
            nom = company.get("nom_complet") or company.get("nom_raison_sociale", "")
            if not nom:
                return None

            lead = ScrapedLead(company_name=nom.strip())

            # SIREN
            siren = company.get("siren", "")
            if siren:
                lead.siren = str(siren)

            # NAF code and sector
            naf = company.get("activite_principale", "")
            if naf:
                lead.naf_code = naf

            # Sector label from NAF
            libelle_naf = company.get("libelle_activite_principale", "")
            if libelle_naf:
                lead.sector = libelle_naf

            # Siege (headquarters) address
            siege = company.get("siege", {})
            if siege:
                # Build address
                parts = []
                numero = siege.get("numero_voie", "")
                type_voie = siege.get("type_voie", "")
                libelle_voie = siege.get("libelle_voie", "")
                if numero:
                    parts.append(str(numero))
                if type_voie:
                    parts.append(type_voie)
                if libelle_voie:
                    parts.append(libelle_voie)
                if parts:
                    lead.address = " ".join(parts)

                # Postal code
                code_postal = siege.get("code_postal", "")
                if code_postal:
                    lead.postal_code = str(code_postal)
                    dept = str(code_postal)[:2]
                    lead.department = dept
                    lead.region = DEPT_TO_REGION.get(dept, "")

                # City
                commune = siege.get("libelle_commune", "")
                if commune:
                    lead.city = commune

            # Source URL (link to annuaire-entreprises.data.gouv.fr)
            if lead.siren:
                lead.source_url = (
                    f"https://annuaire-entreprises.data.gouv.fr/entreprise/{lead.siren}"
                )

            return lead

        except Exception as e:
            logger.debug(f"Failed to parse Sirene company: {e}")
            return None

    async def close(self):
        return None

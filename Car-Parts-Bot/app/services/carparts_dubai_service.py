# """
# Integration client for CarPartsDubai stock lookup endpoint.
# Fetches live stock information using part numbers and normalizes it
# to match our internal part representation.
# """
# from __future__ import annotations

# from dataclasses import dataclass
# from typing import Any, Iterable, List, Optional

# import requests
# from flask import current_app


# @dataclass(slots=True)
# class ExternalPart:
#     """Normalized view of a part returned from CarPartsDubai."""

#     part_number: Optional[str]
#     name: Optional[str]
#     brand: Optional[str]
#     price: Optional[float]
#     quantity_min: Optional[int]
#     raw: dict[str, Any]

#     def to_dict(self) -> dict[str, Any]:
#         """Convert to API-friendly dict."""
#         return {
#             "id": None,
#             "part_number": self.part_number,
#             "name": self.name,
#             "brand": self.brand,
#             "price": self.price,
#             "quantity_min": self.quantity_min,
#             "vehicle": None,
#             "source": "carpartsdubai",
#             "raw": self.raw,
#         }


# class CarPartsDubaiService:
#     """
#     Client for https://carpartsdubai.com/stock-details endpoint.
#     """

#     DEFAULT_BASE_URL = "https://carpartsdubai.com/stock-details"

#     def __init__(self) -> None:
#         self._session = requests.Session()

#     def find_by_part_number(self, part_number: str) -> list[dict[str, Any]]:
#         """
#         Lookup part(s) by part number via the external endpoint.
#         Returns a list of normalized dicts compatible with our Part serializer.
#         """
#         part_number = (part_number or "").strip()
#         if not part_number:
#             return []

#         raw_payload = self._fetch_payload(part_number)
#         if not raw_payload:
#             return []

#         external_parts = self._normalize_payload(raw_payload, fallback_number=part_number)
#         return [part.to_dict() for part in external_parts]

#     # --------------------------------------------------------------------- #
#     # Internal helpers
#     # --------------------------------------------------------------------- #
#     def _fetch_payload(self, part_number: str) -> Any | None:
#         base_url = current_app.config.get(
#             "CARPARTSDUBAI_STOCK_URL",
#             self.DEFAULT_BASE_URL,
#         )
#         timeout = current_app.config.get("CARPARTSDUBAI_TIMEOUT", 10)

#         try:
#             response = self._session.get(
#                 base_url,
#                 params={"part_number": part_number},
#                 headers={"Accept": "application/json"},
#                 timeout=timeout,
#             )
#         except requests.RequestException as exc:
#             current_app.logger.warning("CarPartsDubai request failed: %s", exc)
#             return None

#         if response.status_code == 404:
#             return None

#         try:
#             response.raise_for_status()
#             data = response.json()
#         except requests.RequestException as exc:
#             current_app.logger.warning("CarPartsDubai HTTP error: %s", exc)
#             return None
#         except ValueError:
#             current_app.logger.warning("CarPartsDubai returned non-JSON payload")
#             return None

#         if isinstance(data, dict) and data.get("error"):
#             return None

#         return data

#     def _normalize_payload(
#         self,
#         payload: Any,
#         *,
#         fallback_number: str | None = None,
#     ) -> List[ExternalPart]:
#         """
#         Convert payload to a list of ExternalPart objects.
#         Accepts several possible shapes as the remote schema is not fixed.
#         """
#         items: Iterable[Any] = []

#         if isinstance(payload, list):
#             items = payload
#         elif isinstance(payload, dict):
#             candidate_keys = ("stocks", "results", "items", "data", "stock")
#             for key in candidate_keys:
#                 value = payload.get(key) if isinstance(payload, dict) else None
#                 if isinstance(value, list) and value:
#                     items = value
#                     break
#             else:
#                 items = [payload]
#         else:
#             return []

#         normalized: list[ExternalPart] = []
#         for item in items:
#             if not isinstance(item, dict):
#                 continue
#             part = ExternalPart(
#                 part_number=self._first_non_empty(
#                     item,
#                     ("part_number", "PartNumber", "number", "sku"),
#                     fallback=fallback_number,
#                 ),
#                 name=self._first_non_empty(
#                     item,
#                     ("name", "part_name", "description", "PartName"),
#                 ),
#                 brand=self._first_non_empty(
#                     item,
#                     ("brand", "manufacturer", "make", "Brand"),
#                 ),
#                 price=self._coerce_price(
#                     self._first_non_empty(
#                         item,
#                         ("price", "cost", "net_price", "Price"),
#                     )
#                 ),
#                 quantity_min=self._coerce_int(
#                     self._first_non_empty(
#                         item,
#                         ("quantity", "qty", "quantity_min", "stock", "Quantity"),
#                     )
#                 ),
#                 raw=item,
#             )
#             normalized.append(part)

#         return normalized

#     @staticmethod
#     def _first_non_empty(
#         source: dict[str, Any],
#         keys: Iterable[str],
#         *,
#         fallback: Any | None = None,
#     ) -> Any | None:
#         for key in keys:
#             if key in source:
#                 value = source[key]
#                 if value not in (None, "", "N/A"):
#                     return value
#         return fallback

#     @staticmethod
#     def _coerce_price(value: Any) -> Optional[float]:
#         if value in (None, "", "N/A"):
#             return None
#         if isinstance(value, (int, float)):
#             return float(value)
#         try:
#             cleaned = (
#                 str(value)
#                 .strip()
#                 .replace(",", "")
#                 .replace("AED", "")
#                 .replace("د.إ", "")
#             )
#             if cleaned.endswith("د"):
#                 cleaned = cleaned[:-1]
#             return float(cleaned)
#         except (ValueError, TypeError):
#             return None

#     @staticmethod
#     def _coerce_int(value: Any) -> Optional[int]:
#         if value in (None, "", "N/A"):
#             return None
#         if isinstance(value, int):
#             return value
#         try:
#             return int(float(str(value).strip().replace(",", "")))
#         except (ValueError, TypeError):
#             return None





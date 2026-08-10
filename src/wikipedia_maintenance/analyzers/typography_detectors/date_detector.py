"""Détection et formatage des dates."""

import re
from calendar import monthrange
from typing import List, Optional
from dataclasses import dataclass

from ..base import Issue
from ..typography_patterns import DATE_NUMERIC_SLASH_RE, DATE_NUMERIC_DASH_RE
from ..typography_data import FRENCH_MONTHS


@dataclass
class DateDetector:
    """Détecte les dates brutes à formater avec {{date}}."""

    issues: List[Issue]

    def _build_date_template(self, day_str: str, month_token: str, year_str: str, month_is_name: bool) -> Optional[str]:
        """Construit un modèle {{date|jour|mois|année}} valide."""
        try:
            day = int(day_str)
            year = int(year_str)
        except ValueError:
            return None
        if not (1 <= day <= 31 and 1000 <= year <= 2100):
            return None

        if month_is_name:
            month_name = month_token.lower()
            if month_name not in FRENCH_MONTHS:
                return None
            month_num = FRENCH_MONTHS.index(month_name) + 1
        else:
            try:
                month_num = int(month_token)
            except ValueError:
                return None
            if not (1 <= month_num <= 12):
                return None
            # FRENCH_MONTHS est une liste 0-indexée : janvier=index 0, donc month_num - 1.
            month_name = FRENCH_MONTHS[month_num - 1]

        # Validation calendaire réelle (rejette 31 février, 30 février, etc.)
        try:
            _, days_in_month = monthrange(year, month_num)
            if day > days_in_month:
                return None
        except ValueError:
            return None

        return f"{{{{date|{day}|{month_name}|{year}}}}}"

    def detect_bare_dates(self, original: str, masked: str) -> None:
        """Détecte les dates brutes à formater avec {{date}}."""
        for m in DATE_NUMERIC_SLASH_RE.finditer(masked):
            before = original[max(0, m.start()-20):m.start()]
            if '{{' in before or '<ref' in before:
                continue
            template = self._build_date_template(m.group(1), m.group(2), m.group(3), month_is_name=False)
            if template is None:
                continue
            original_text = original[m.start():m.end()]
            self.issues.append(Issue(
                issue_type="bare_date",
                description=f"Date brute : {original_text} (utiliser {{{{date}}}})",
                position=m.start(),
                original_text=original_text,
                suggested_text=template,
                severity="medium"
            ))

        for m in DATE_NUMERIC_DASH_RE.finditer(masked):
            before = original[max(0, m.start()-20):m.start()]
            if '{{' in before or '<ref' in before:
                continue
            template = self._build_date_template(m.group(1), m.group(2), m.group(3), month_is_name=False)
            if template is None:
                continue
            original_text = original[m.start():m.end()]
            self.issues.append(Issue(
                issue_type="bare_date",
                description=f"Date brute : {original_text} (utiliser {{{{date}}}})",
                position=m.start(),
                original_text=original_text,
                suggested_text=template,
                severity="medium"
            ))
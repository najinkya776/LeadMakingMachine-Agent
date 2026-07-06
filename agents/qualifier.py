"""Agent 3: Lead Qualifier - Filter and deduplicate leads."""

import re
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime

from anthropic import Anthropic
from models import Lead, LeadStatus, LeadType
from config.settings import ICP


class QualifierAgent:
    """Agent for qualifying and filtering leads based on ICP."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the qualifier agent."""
        self.anthropic = Anthropic(api_key=api_key or None)
        self.icp = ICP

    def run(self, leads: List[Lead]) -> List[Lead]:
        """
        Qualify leads based on Ideal Customer Profile.

        Args:
            leads: List of raw Lead objects

        Returns:
            List of qualified Lead objects with status updated
        """
        print(f"[Qualifier] Starting qualification for {len(leads)} leads")

        # Step 1: Deduplicate
        deduped_leads = self._deduplicate(leads)
        print(f"[Qualifier] After dedup: {len(deduped_leads)} leads")

        # Step 2: Filter by ICP
        qualified_leads = []
        for lead in deduped_leads:
            matches = self._matches_icp(lead)
            if matches:
                lead.status = LeadStatus.QUALIFIED
                qualified_leads.append(lead)
            else:
                lead.status = LeadStatus.FAILED
                # Debug why rejected
                reasons = []
                if lead.category:
                    for excl in self.icp.get("exclude_industries", []):
                        if excl.lower() in lead.category.lower():
                            reasons.append(f"excluded category: {excl}")
                min_reviews = self.icp.get("min_reviews", 0)
                if lead.review_count is not None and lead.review_count < min_reviews:
                    reasons.append(f"low reviews: {lead.review_count} < {min_reviews}")
                min_rating = self.icp.get("min_rating", 0)
                if lead.google_rating is not None and lead.google_rating < min_rating:
                    reasons.append(f"low rating: {lead.google_rating} < {min_rating}")
                locations = [loc.lower() for loc in self.icp.get("locations", [])]
                if lead.address:
                    address_lower = lead.address.lower()
                    if not any(loc in address_lower for loc in locations):
                        reasons.append(f"address mismatch: '{lead.address}'")
                print(f"[Qualifier] Rejected: {lead.business_name} - {', '.join(reasons) if reasons else 'ICP'}")

        print(f"[Qualifier] Qualified: {len(qualified_leads)} leads")
        return qualified_leads

    def _deduplicate(self, leads: List[Lead]) -> List[Lead]:
        """Remove duplicate leads based on phone, address, or fuzzy name match."""
        seen_phones: Set[str] = set()
        seen_addresses: Set[str] = set()
        seen_names: Set[str] = set()

        deduped = []

        for lead in leads:
            # Normalize data for comparison
            phone_normalized = self._normalize_phone(lead.phone) if lead.phone else None
            address_normalized = self._normalize_address(lead.address) if lead.address else None
            name_normalized = self._normalize_name(lead.business_name) if lead.business_name else None

            # Check for duplicates
            is_duplicate = False

            if phone_normalized and phone_normalized in seen_phones:
                is_duplicate = True
            elif address_normalized and address_normalized in seen_addresses:
                is_duplicate = True
            elif name_normalized:
                # Fuzzy match on name
                for seen_name in seen_names:
                    if self._fuzzy_match(name_normalized, seen_name) > 0.85:
                        is_duplicate = True
                        break

            if not is_duplicate:
                deduped.append(lead)

                if phone_normalized:
                    seen_phones.add(phone_normalized)
                if address_normalized:
                    seen_addresses.add(address_normalized)
                if name_normalized:
                    seen_names.add(name_normalized)

        return deduped

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison."""
        # Remove all non-digits
        digits = re.sub(r"[^\d]", "", phone)
        # Keep only last 10 digits (for Indian numbers)
        if len(digits) > 10:
            digits = digits[-10:]
        return digits

    def _normalize_address(self, address: str) -> str:
        """Normalize address for comparison."""
        if not address:
            return ""

        # Lowercase, remove extra spaces, common abbreviations
        normalized = address.lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.replace(", ", " ")
        normalized = normalized.replace(",", " ")

        # Common replacements
        replacements = {
            "road": "rd",
            "street": "st",
            "building": "bldg",
            "shop": "",
            "plot": "",
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized.strip()

    def _normalize_name(self, name: str) -> str:
        """Normalize business name for fuzzy matching."""
        if not name:
            return ""

        # Lowercase, remove special chars
        normalized = name.lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    def _fuzzy_match(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings."""
        # Simple Jaccard similarity on words
        words1 = set(str1.split())
        words2 = set(str2.split())

        if not words1 or not words2:
            return 0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def _matches_icp(self, lead: Lead) -> bool:
        """Check if lead matches the Ideal Customer Profile."""
        # Check exclusions first
        if lead.category:
            for excluded in self.icp.get("exclude_industries", []):
                if excluded.lower() in lead.category.lower():
                    return False

        # Check minimum reviews
        min_reviews = self.icp.get("min_reviews", 0)
        if lead.review_count is not None and lead.review_count < min_reviews:
            return False

        # Check minimum rating
        min_rating = self.icp.get("min_rating", 0)
        if lead.google_rating is not None and lead.google_rating < min_rating:
            return False

        # Check location
        locations = [loc.lower() for loc in self.icp.get("locations", [])]
        if lead.address:
            address_lower = lead.address.lower()
            if not any(loc in address_lower for loc in locations):
                return False

        return True

    def run_with_ai_scoring(self, leads: List[Lead]) -> List[Lead]:
        """
        Use AI to score lead quality and reachability.

        Args:
            leads: List of Lead objects

        Returns:
            Leads with updated reachability scores
        """
        print(f"[Qualifier] Running AI-powered scoring for {len(leads)} leads")

        for lead in leads:
            try:
                prompt = f"""Score this lead's quality and reachability (0-100).
                Consider:
                - Has working phone number
                - Has email address
                - Has website or strong social media
                - Good Google reviews
                - Active business (hours listed)
                - Clear business category

                Business: {lead.business_name}
                Category: {lead.category or 'Unknown'}
                Address: {lead.address or 'Unknown'}
                Phone: {lead.phone or 'None'}
                Email: {lead.email or 'None'}
                Website: {lead.website_url or 'None'}
                Google Rating: {lead.google_rating or 'N/A'}
                Reviews: {lead.review_count or 'N/A'}

                Return just the numeric score (0-100)."""

                message = self.anthropic.messages.create(
                    model="haiku-4",
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}]
                )

                response = message.content[0].text.strip()
                score = int(re.search(r"\d+", response).group())
                lead.reachability_score = min(100, max(0, score))

            except Exception as e:
                print(f"[Qualifier] AI scoring failed for {lead.business_name}: {e}")
                # Keep existing score

        return leads

    def classify_lead_type(self, lead: Lead) -> LeadType:
        """Classify lead type based on digital presence."""
        if not lead.website_url:
            if lead.social_handles and (lead.social_handles.facebook or lead.social_handles.instagram):
                return LeadType.SOCIAL_ONLY
            return LeadType.NO_WEBSITE

        return LeadType.HAS_WEBSITE


def qualify_leads(leads: List[Lead]) -> List[Lead]:
    """Convenience function to qualify leads."""
    agent = QualifierAgent()
    return agent.run(leads)
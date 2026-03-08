from winxtract.core.models import LeadData


def score_lead(lead: LeadData) -> int:
    score = 0
    if lead.name:
        score += 10
    if lead.city:
        score += 10
    if lead.emails:
        score += 40
    if lead.phones:
        score += 25
    if lead.website:
        score += 10
    if lead.description and len(lead.description) > 80:
        score += 5
    return min(score, 100)

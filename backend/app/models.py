from typing import List, Dict, Optional
from pydantic import BaseModel

class ProjectScope(BaseModel):
    projectType: str
    features: List[str]
    integrations: List[str]
    platforms: List[str]
    security: str
    compliance: Optional[str]
    assumptions: List[str]

class Estimate(BaseModel):
    roles: List[Dict]
    phases: List[Dict]
    totalHours: int
    totalCost: float
    confidence: str
    variance: float

class HubSpotRecord(BaseModel):
    dealId: str
    contactId: str
    stage: str

# Admin rate card payloads
class RateCardIn(BaseModel):
    rates: Dict[str, float]

class RateCardOut(BaseModel):
    rates: Dict[str, float]
import json
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re

# Data Models
@dataclass
class ProjectScope:
    projectType: str
    features: List[str]
    integrations: List[str]
    platforms: List[str]
    security: str
    compliance: str
    assumptions: List[str]

@dataclass
class Estimate:
    roles: List[Dict]
    phases: List[Dict]
    totalHours: int
    totalCost: float
    confidence: str
    variance: float

@dataclass
class HubSpotRecord:
    dealId: str
    contactId: str
    stage: str

class MultiAgentOrchestrationSystem:
    def __init__(self):
        self.project_templates = self._load_templates()
        self.rate_card = self._load_rate_card()
        
    def _load_templates(self):
        return {
            "wordpress": {
                "base_hours": 80,
                "features": {
                    "booking": 40,
                    "blog": 20,
                    "reviews": 25,
                    "ecommerce": 60
                }
            },
            "web_app": {
                "base_hours": 120,
                "features": {
                    "auth": 40,
                    "crud": 60,
                    "reports": 50,
                    "api": 45
                }
            },
            "hubspot": {
                "base_hours": 100,
                "features": {
                    "crm_setup": 40,
                    "portal": 80,
                    "integration": 60
                }
            },
            "cloud": {
                "base_hours": 40,
                "features": {
                    "ci_cd": 30,
                    "monitoring": 25,
                    "backup": 20
                }
            }
        }
    
    def _load_rate_card(self):
        return {
            "Frontend Dev": 85,
            "Backend Dev": 95,
            "DevOps Engineer": 105,
            "Project Manager": 90,
            "QA Engineer": 75,
            "UI/UX Designer": 85
        }
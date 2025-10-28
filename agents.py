from typing import Dict, List
from datetime import datetime
from models import ProjectScope, Estimate, HubSpotRecord


class IntentExtractorAgent:
    def extract_intent(self, client_input: str) -> Dict:
        """Parse client input and detect project type"""
        input_lower = client_input.lower()
        
        # Detect project type
        project_type = self._detect_project_type(input_lower)
        
        # Extract features
        features = self._extract_features(input_lower)
        
        # Identify missing information
        missing_info = self._identify_missing_info(project_type, features, input_lower)
        
        return {
            "projectType": project_type,
            "detectedFeatures": features,
            "missingFields": missing_info,
            "confidence": self._calculate_confidence(project_type, features),
            "summary": self._generate_summary(project_type, features)
        }
    
    def _detect_project_type(self, text: str) -> str:
        if any(word in text for word in ["wordpress", "wp", "cms"]):
            return "wordpress"
        elif any(word in text for word in ["hubspot", "crm", "portal"]):
            return "hubspot"
        elif any(word in text for word in [".net", "react", "web app", "application"]):
            return "web_app"
        elif any(word in text for word in ["aws", "azure", "cloud", "hosting", "ci/cd"]):
            return "cloud"
        else:
            return "unknown"
    
    def _extract_features(self, text: str) -> List[str]:
        features = []
        feature_keywords = {
            "booking": ["appointment", "booking", "schedule"],
            "blog": ["blog", "articles", "posts"],
            "reviews": ["review", "rating", "testimonial"],
            "ecommerce": ["shop", "store", "payment", "cart"],
            "auth": ["login", "register", "authentication"],
            "api": ["api", "integration", "connect"]
        }
        
        for feature, keywords in feature_keywords.items():
            if any(keyword in text for keyword in keywords):
                features.append(feature)
        
        return features
    
    def _identify_missing_info(self, project_type: str, features: List[str], text: str) -> List[str]:
        missing = []
        
        if project_type == "wordpress":
            if "design" not in text:
                missing.append("design_preferences")
            if "content" not in text:
                missing.append("content_migration")
            if "plugins" not in text:
                missing.append("specific_plugins")
                
        elif project_type == "web_app":
            if "users" not in text:
                missing.append("target_users")
            if "data" not in text:
                missing.append("data_volume")
            if "integrations" not in text:
                missing.append("external_integrations")
                
        return missing
    
    def _calculate_confidence(self, project_type: str, features: list) -> str:
        """Basic heuristic for intent confidence."""
        if project_type == "unknown":
            return "low"
        if len(features) >= 3:
            return "high"
        if len(features) == 2:
            return "medium"
        return "medium-low"

    def _generate_summary(self, project_type: str, features: list) -> str:
        """Generate simple summary string."""
        feature_list = ", ".join(features) if features else "no specific features"
        return f"Detected project type: {project_type}. Features mentioned: {feature_list}."


class QuestionnaireAgent:
    def generate_questions(self, intent_data: Dict) -> Dict:
        project_type = intent_data["projectType"]
        missing_fields = intent_data["missingFields"]
        
        questions = self._get_base_questions(project_type)
        specific_questions = self._get_specific_questions(missing_fields)
        
        all_questions = questions + specific_questions
        # Limit to 3-7 questions
        final_questions = all_questions[:7]
        
        return {
            "questions": final_questions,
            "expectedFormat": "json",
            "requiredFields": self._get_required_fields(project_type)
        }
    
    def _get_base_questions(self, project_type: str) -> List[str]:
        base_questions = {
            "wordpress": [
                "Do you have existing brand guidelines or design preferences?",
                "Will you need content migration from an existing website?",
                "What specific functionality do you need beyond basic pages?",
                "Do you have preferred hosting or domain setup?",
                "What's your expected timeline for launch?"
            ],
            "web_app": [
                "Who are the primary users of this application?",
                "What's the expected number of concurrent users?",
                "Do you need mobile responsiveness or native mobile apps?",
                "What security requirements do you have?",
                "Are there existing systems to integrate with?"
            ]
        }
        return base_questions.get(project_type, [])
    
    def _get_specific_questions(self, missing_fields: list) -> list:
        """Return field-specific clarification questions."""
        questions = []
        mapping = {
            "projectType": "What kind of project is this (e.g., web app, WordPress site, HubSpot portal)?",
            "features": "Which key features are required (e.g., booking, e-commerce, CRM)?",
            "integrations": "Are there integrations with other systems or APIs?",
            "platforms": "Which platforms should this run on (e.g., web, iOS, Android)?",
            "security": "Do you have specific security or authentication needs?",
            "compliance": "Are there compliance standards to meet (HIPAA, GDPR, etc.)?",
            "assumptions": "Any assumptions or constraints we should be aware of?"
        }
        for field in missing_fields:
            if field in mapping:
                questions.append(mapping[field])
        return questions

    def _get_required_fields(self, project_type: str) -> list:
        """Return required fields for a given project type."""
        mapping = {
            "wordpress": ["design_preferences", "content_migration", "specific_plugins"],
            "web_app": ["target_users", "data_volume", "external_integrations"],
            "hubspot": ["crm_setup_details", "portal_requirements", "integration_needs"],
            "cloud": ["ci_cd_setup", "monitoring_requirements", "backup_strategy"]
        }
        return mapping.get(project_type, [])


class ScopeBuilderAgent:
    def build_scope(self, intent_data: Dict, questionnaire_answers: Dict) -> ProjectScope:
        project_type = intent_data["projectType"]
        
        return ProjectScope(
            projectType=project_type,
            features=self._compile_features(intent_data, questionnaire_answers),
            integrations=self._identify_integrations(questionnaire_answers),
            platforms=self._determine_platforms(project_type, questionnaire_answers),
            security=self._assess_security_needs(project_type, questionnaire_answers),
            compliance=self._identify_compliance(questionnaire_answers),
            assumptions=self._generate_assumptions(project_type, questionnaire_answers)
        )
    
    def _compile_features(self, intent_data: Dict, answers: Dict) -> List[str]:
        base_features = intent_data["detectedFeatures"]
        # Add features from questionnaire answers
        if "additional_features" in answers:
            base_features.extend(answers["additional_features"])
        return list(set(base_features))
    
    def _identify_integrations(self, answers: dict) -> list:
        """Determine integrations from questionnaire answers."""
        return answers.get("integrations", [])

    def _determine_platforms(self, project_type: str, answers: dict) -> list:
        """Decide which platforms the project should support."""
        platforms = []
        if "mobile" in answers.get("design_preferences", "").lower() or "responsive" in answers.get("design_preferences", "").lower():
            platforms.append("Web (Responsive)")
        platforms.extend(answers.get("platforms", []))
        return platforms if platforms else ["Web"]

    def _assess_security_needs(self, project_type: str, answers: dict) -> str:
        """Assess security level based on answers."""
        if project_type == "web_app":
            return "standard"
        return "basic"

    def _identify_compliance(self, answers: dict) -> str:
        """Identify compliance requirements from answers."""
        return answers.get("compliance", "")

    def _generate_assumptions(self, project_type: str, answers: dict) -> list:
        """Generate assumptions for the project."""
        return answers.get("assumptions", ["No assumptions specified."])


class EstimatorAgent:
    def __init__(self, rate_card: Dict):
        self.rate_card = rate_card
        self.project_templates = self._load_project_templates()
    
    def _load_project_templates(self):
        """Load project estimation templates"""
        return {
            "wordpress": {
                "base_hours": 80,
                "team_composition": {
                    "Project Manager": 0.15,  # 15% of total hours
                    "WordPress Developer": 0.60,
                    "UI/UX Designer": 0.25
                },
                "features": {
                    "booking": {"hours": 40, "complexity": "medium"},
                    "blog": {"hours": 20, "complexity": "low"},
                    "reviews": {"hours": 25, "complexity": "medium"},
                    "ecommerce": {"hours": 60, "complexity": "high"},
                    "contact_forms": {"hours": 15, "complexity": "low"}
                }
            },
            "web_app": {
                "base_hours": 120,
                "team_composition": {
                    "Project Manager": 0.12,
                    "Frontend Dev": 0.35,
                    "Backend Dev": 0.40,
                    "QA Engineer": 0.13
                },
                "features": {
                    "auth": {"hours": 40, "complexity": "medium"},
                    "crud": {"hours": 60, "complexity": "medium"},
                    "reports": {"hours": 50, "complexity": "high"},
                    "api": {"hours": 45, "complexity": "medium"}
                }
            },
            "hubspot": {
                "base_hours": 100,
                "team_composition": {
                    "Project Manager": 0.10,
                    "HubSpot Developer": 0.70,
                    "QA Engineer": 0.20
                },
                "features": {
                    "crm_setup": {"hours": 40, "complexity": "medium"},
                    "portal": {"hours": 80, "complexity": "high"},
                    "integration": {"hours": 60, "complexity": "high"}
                }
            },
            "cloud": {
                "base_hours": 40,
                "team_composition": {
                    "Project Manager": 0.10,
                    "DevOps Engineer": 0.70,
                    "Cloud Architect": 0.20
                },
                "features": {
                    "ci_cd": {"hours": 30, "complexity": "medium"},
                    "monitoring": {"hours": 25, "complexity": "medium"},
                    "backup": {"hours": 20, "complexity": "low"}
                }
            }
        }
    
    def estimate_project(self, scope: ProjectScope, knowledge_data: Dict) -> Estimate:
        """Generate project estimate using rate card and templates"""
        # Calculate base hours
        base_hours = self._calculate_base_hours(scope)
        
        # Calculate feature hours
        feature_hours = self._calculate_feature_hours(scope.features, scope.projectType)
        
        # Calculate integration hours
        integration_hours = self._calculate_integration_hours(scope.integrations)
        
        # Calculate total hours with complexity factors
        total_raw_hours = base_hours + feature_hours + integration_hours
        total_hours = self._apply_complexity_factors(total_raw_hours, scope)
        
        # Determine team composition and costs
        roles = self._determine_team_composition(total_hours, scope)
        phases = self._calculate_phases(total_hours, scope)
        total_cost = self._calculate_total_cost(roles)
        
        # Calculate confidence and variance
        confidence, variance = self._calculate_confidence(scope, knowledge_data, total_hours)
        
        return Estimate(
            roles=roles,
            phases=phases,
            totalHours=round(total_hours),
            totalCost=round(total_cost, -2),  # Round to nearest $100
            confidence=confidence,
            variance=variance
        )
    
    def _calculate_integration_hours(self, integrations: list) -> int:
        """Estimate hours required for integrations"""
        if not integrations:
            return 0
        # Simple heuristic: 10 hours per integration
        return len(integrations) * 10

    
    def _calculate_base_hours(self, scope: ProjectScope) -> int:
        """Calculate base hours for project type"""
        template = self.project_templates.get(scope.projectType, {})
        return template.get("base_hours", 100)
    
    def _calculate_feature_hours(self, features: List[str], project_type: str) -> int:
        """Calculate additional hours for features"""
        template = self.project_templates.get(project_type, {})
        feature_templates = template.get("features", {})
        
        total_feature_hours = 0
        for feature in features:
            feature_config = feature_templates.get(feature, {})
            total_feature_hours += feature_config.get("hours", 0)
        
        return total_feature_hours
    
    def _determine_team_composition(self, total_hours: float, scope: ProjectScope) -> List[Dict]:
        """Determine team composition based on project type"""
        template = self.project_templates.get(scope.projectType, {})
        team_composition = template.get("team_composition", {})
        
        roles = []
        for role, percentage in team_composition.items():
            role_hours = total_hours * percentage
            rate = self.rate_card.get(role, 85)  # Default rate if role not found
            cost = role_hours * rate
            
            roles.append({
                "name": role,
                "hours": round(role_hours),
                "rate": rate,
                "cost": round(cost)
            })
        
        return roles
    
    def _calculate_total_cost(self, roles: List[Dict]) -> float:
        """Calculate total project cost from roles"""
        return sum(role["cost"] for role in roles)
    
    def _apply_complexity_factors(self, hours: float, scope: ProjectScope) -> float:
        """Apply complexity multipliers"""
        complexity_multiplier = 1.0
        
        # Integration complexity
        if scope.integrations:
            complexity_multiplier += len(scope.integrations) * 0.1
        
        # Security complexity
        if scope.security and scope.security != "basic":
            complexity_multiplier += 0.2
        
        # Compliance complexity
        if scope.compliance:
            complexity_multiplier += 0.3
        
        # Project management buffer
        complexity_multiplier += 0.15
        
        return hours * complexity_multiplier
    
    def _calculate_phases(self, total_hours: float, scope: ProjectScope) -> List[Dict]:
        """Break down hours by project phases"""
        phase_distributions = {
            "wordpress": {
                "Discovery & Planning": 0.10,
                "Design": 0.25,
                "Development": 0.45,
                "Testing": 0.15,
                "Deployment": 0.05
            },
            "web_app": {
                "Discovery & Planning": 0.15,
                "Design": 0.20,
                "Development": 0.40,
                "Testing": 0.20,
                "Deployment": 0.05
            },
            "hubspot": {
                "Discovery & Planning": 0.15,
                "Configuration": 0.35,
                "Development": 0.30,
                "Testing": 0.15,
                "Training": 0.05
            },
            "cloud": {
                "Planning": 0.20,
                "Implementation": 0.50,
                "Testing": 0.20,
                "Documentation": 0.10
            }
        }
        
        distribution = phase_distributions.get(scope.projectType, phase_distributions["web_app"])
        phases = []
        
        for phase_name, percentage in distribution.items():
            phase_hours = total_hours * percentage
            # Use average rate for phase costing
            avg_rate = sum(self.rate_card.values()) / len(self.rate_card)
            phase_cost = phase_hours * avg_rate
            
            phases.append({
                "phase": phase_name,
                "hours": round(phase_hours),
                "cost": round(phase_cost)
            })
        
        return phases
    
    def _calculate_confidence(self, scope: ProjectScope, knowledge_data: Dict, total_hours: float) -> tuple:
        """Calculate estimate confidence level"""
        confidence_factors = {
            "feature_clarity": 0.8 if scope.features else 0.3,
            "requirements_completeness": 0.7,
            "historical_data": knowledge_data.get("similarity_score", 0.5),
            "complexity": 0.6 if len(scope.integrations) > 2 else 0.8
        }
        
        avg_confidence = sum(confidence_factors.values()) / len(confidence_factors)
        
        if avg_confidence >= 0.8:
            confidence_level = "P90"
            variance = 0.10
        elif avg_confidence >= 0.7:
            confidence_level = "P80"
            variance = 0.15
        elif avg_confidence >= 0.6:
            confidence_level = "P70"
            variance = 0.20
        else:
            confidence_level = "P50"
            variance = 0.30
        
        return confidence_level, variance

class SOWGeneratorAgent:
    def generate_sow(self, scope: ProjectScope, estimate: Estimate, client_info: Dict) -> str:
        sow_template = f"""
# STATEMENT OF WORK

## Project Overview
**Client:** {client_info.get('company_name', 'Client')}
**Project Type:** {scope.projectType.title()}
**Date:** {datetime.now().strftime('%Y-%m-%d')}

## Objectives
{self._generate_objectives(scope)}

## Scope of Work
### Included Features
{self._format_features(scope.features)}

### Technical Stack
{self._format_platforms(scope.platforms)}

### Integrations
{self._format_integrations(scope.integrations)}

## Deliverables
{self._generate_deliverables(scope)}

## Timeline and Cost Summary
{self._generate_timeline_cost(estimate)}

## Assumptions
{self._format_assumptions(scope.assumptions)}

## Payment Schedule
{self._generate_payment_schedule(estimate.totalCost)}

## Acceptance Criteria
{self._generate_acceptance_criteria(scope)}
"""
        return sow_template
    
    def _generate_objectives(self, scope) -> str:
        return f"- Deliver a {scope.projectType} project with the requested features: {', '.join(scope.features)}."

    def _format_features(self, features: list) -> str:
        return "\n".join([f"- {f}" for f in features])

    def _format_platforms(self, platforms: list) -> str:
        return "\n".join([f"- {p}" for p in platforms])

    def _format_integrations(self, integrations: list) -> str:
        return "\n".join([f"- {i}" for i in integrations]) if integrations else "None"

    def _generate_deliverables(self, scope) -> str:
        return "- Fully functional project according to scope\n- Documentation and user training"

    def _generate_timeline_cost(self, estimate) -> str:
        return f"Total Hours: {estimate.totalHours}\nTotal Cost: ${estimate.totalCost}\nConfidence: {estimate.confidence}"

    def _format_assumptions(self, assumptions: list) -> str:
        return "\n".join([f"- {a}" for a in assumptions])

    def _generate_payment_schedule(self, total_cost: float) -> str:
        return f"- 50% upfront: ${round(total_cost * 0.5, 2)}\n- 50% on completion: ${round(total_cost * 0.5, 2)}"

    def _generate_acceptance_criteria(self, scope) -> str:
        return "- All features implemented and tested\n- Client approval of deliverables"


class HubSpotIntegrationAgent:
    def sync_to_crm(self, project_data: Dict, client_info: Dict) -> HubSpotRecord:
        contact_id = self._create_or_update_contact(client_info)
        deal_id = self._create_or_update_deal(contact_id, project_data)
        self._attach_documents(deal_id, project_data)
        return HubSpotRecord(
            dealId=deal_id,
            contactId=contact_id,
            stage="Quote Sent"
        )

    def _create_or_update_contact(self, client_info: Dict) -> str:
        # Simulate creating/updating a contact in HubSpot
        return client_info.get("contact_email", "contact_123@example.com")

    def _create_or_update_deal(self, contact_id: str, project_data: Dict) -> str:
        # Simulate creating/updating a deal in HubSpot
        return f"deal_{contact_id.split('@')[0]}_001"

    def _attach_documents(self, deal_id: str, project_data: Dict):
        # Simulate attaching documents to the deal
        pass


class ReviewerAgent:
    def validate_proposal(self, scope: ProjectScope, estimate: Estimate) -> Dict:
        issues = []
        
        # Check confidence level
        if estimate.confidence in ["P50", "P60"]:
            issues.append("Low confidence estimate - requires PM review")
        
        # Check for scope ambiguities
        if any("TBD" in feature for feature in scope.features):
            issues.append("Undefined features in scope")
        
        # Check pricing anomalies
        if self._has_pricing_anomaly(estimate):
            issues.append("Pricing anomaly detected")
        
        return {
            "approved": len(issues) == 0,
            "issues": issues,
            "requires_human_review": len(issues) > 0
        }
    
    def _has_pricing_anomaly(self, estimate) -> bool:
        """Detect abnormal cost per hour deviations"""
        avg_rate = sum(role["rate"] for role in estimate.roles) / len(estimate.roles)
        for role in estimate.roles:
            role_rate = role["cost"] / max(role["hours"], 1)
            if abs(role_rate - avg_rate) / avg_rate > 0.5:  # more than 50% deviation
                return True
        return False

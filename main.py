from agents import IntentExtractorAgent, QuestionnaireAgent, ScopeBuilderAgent, EstimatorAgent, SOWGeneratorAgent, HubSpotIntegrationAgent, ReviewerAgent
from typing import Dict
import json
import base64

class DevelopmentProposalOrchestrator:
    def __init__(self):
         # First, define the rate card
        self.rate_card = self._initialize_rate_card()

        self.agents = {
            "intent_extractor": IntentExtractorAgent(),
            "questionnaire": QuestionnaireAgent(),
            "scope_builder": ScopeBuilderAgent(),
            "estimator": EstimatorAgent(self.rate_card),
            "sow_generator": SOWGeneratorAgent(),
            "hubspot": HubSpotIntegrationAgent(),
            "reviewer": ReviewerAgent()
        }        
    
    def _initialize_rate_card(self) -> Dict:
        """Initialize the company rate card with current rates"""
        return {
            "Frontend Dev": 85,
            "Backend Dev": 95,
            "Full Stack Dev": 90,
            "DevOps Engineer": 105,
            "Project Manager": 90,
            "QA Engineer": 75,
            "UI/UX Designer": 85,
            "WordPress Developer": 80,
            "HubSpot Developer": 95,
            "Cloud Architect": 110
        }
    
    def process_client_input(self, client_input: str, client_info: Dict = None) -> Dict:
        """Main workflow execution"""
        
        # Step 1: Extract intent
        print("🔍 Extracting project intent...")
        intent_data = self.agents["intent_extractor"].extract_intent(client_input)
        
        # Step 2: Generate questions if needed
        if intent_data["missingFields"]:
            print("❓ Clarifying information required:")
            questions = self.agents["questionnaire"].generate_questions(intent_data)
            answers = {}

            for idx, question in enumerate(questions["questions"], 1):
                user_input = input(f"{idx}. {question} ")
                # Map answer to the missing field
                field = intent_data["missingFields"][idx-1] if idx-1 < len(intent_data["missingFields"]) else f"field_{idx}"
                answers[field] = user_input.strip()

            # Update intent_data with answers
            intent_data["providedAnswers"] = answers

        
        # Step 3: Build scope
        print("📋 Building project scope...")
        scope = self.agents["scope_builder"].build_scope(intent_data, intent_data.get("providedAnswers", {}))

        # Step 4: Estimate project
        print("💰 Calculating estimate...")
        estimate = self.agents["estimator"].estimate_project(scope, {})
        
        # Step 5: Generate SOW
        print("📄 Generating Statement of Work...")
        sow_document = self.agents["sow_generator"].generate_sow(scope, estimate, client_info or {})
        
        # Step 6: Review proposal
        print("🔍 Reviewing proposal...")
        review_result = self.agents["reviewer"].validate_proposal(scope, estimate)
        
        if not review_result["approved"]:
            return {
                "status": "requires_review",
                "review_issues": review_result["issues"],
                "scope": scope.__dict__,
                "estimate": estimate.__dict__,
                "sow_draft": sow_document
            }
        
        # Step 7: Sync to HubSpot
        print("🔄 Syncing to HubSpot CRM...")
        hubspot_record = self.agents["hubspot"].sync_to_crm({
            "scope": scope.__dict__,
            "estimate": estimate.__dict__,
            "sow": sow_document
        }, client_info or {})
        
        # Final output
        return {
            "status": "completed",
            "summary": intent_data["summary"],
            "scope": scope.__dict__,
            "estimate": estimate.__dict__,
            "sowDocument": base64.b64encode(sow_document.encode()).decode(),
            "mockupLinks": [],
            "hubspotRecord": hubspot_record.__dict__,
            "confidence": estimate.confidence
        }

def complete_example():
    """Demonstrate the fixed rate card implementation"""
    
    # Initialize the orchestrator with proper rate card
    orchestrator = DevelopmentProposalOrchestrator()
    
    # Show the rate card is properly loaded
    print("💰 Loaded Rate Card:")
    for role, rate in orchestrator.rate_card.items():
        print(f"  - {role}: ${rate}/hour")
    
    # Test with sample project
    client_input = "We need a WordPress site for a dental clinic, with appointment booking, reviews, and a blog. Host on AWS."
    
    result = orchestrator.process_client_input(client_input, {
        "company_name": "Smile Dental Clinic",
        "contact_email": "office@smiledental.com"
    })
    
    # Display the estimate with proper rates
    if "estimate" in result:
        print("\n📊 Project Estimate:")
        estimate = result["estimate"]
        print(f"Total Hours: {estimate['totalHours']}")
        print(f"Total Cost: ${estimate['totalCost']:,.2f}")
        print(f"Confidence: {estimate['confidence']}")
        print(f"Variance: ±{estimate['variance']*100}%")
        
        print("\n👥 Team Composition:")
        for role in estimate["roles"]:
            print(f"  - {role['name']}: {role['hours']} hours × ${role['rate']}/hr = ${role['cost']:,.2f}")

# Run the fixed example
if __name__ == "__main__":
    complete_example()
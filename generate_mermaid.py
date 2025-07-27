
import json

def generate_mermaid_flow(toc_mapping):
    lines = ["flowchart TB"]
    lines.append(f'A[\"{toc_mapping.get("pre_categorization", "")}\"] --> B{{Decision: Eccentric?}}')
    lines.append(f'B -->|No| C[\"{toc_mapping.get("semantic_mapping", "")}\"]')
    lines.append(f'C --> D[\"{toc_mapping.get("cultural_adaptation", "")}\"]')
    lines.append(f'D --> E[\"{toc_mapping.get("iterative_refinement", "")}\"]')
    lines.append(f'E --> F[\"Final Quality Assurance\"]')
    lines.append(f'F --> G[\"Output Generation\"]')
    lines.append(f'B -->|Yes| H[\"{toc_mapping.get("chunking", "")}\"]')
    lines.append(f'H --> I[\"{toc_mapping.get("neologism_management", "")}\"]')
    lines.append(f'I --> J[\"{toc_mapping.get("self_reflection", "")}\"]')
    lines.append(f'J --> K[\"{toc_mapping.get("multi_agent", "")}\"]')
    lines.append(f'K --> L[\"{toc_mapping.get("tailored_evaluation", "")}\"]')
    lines.append(f'L --> M[\"{toc_mapping.get("prompt_template_mgmt", "")}\"]')
    lines.append(f'M --> N[\"{toc_mapping.get("integration_guidance", "")}\"]')
    lines.append(f'N --> O[\"Assembly of Chunks\"]')
    lines.append(f'O --> P[\"Final Quality Assurance\"]')
    lines.append(f'P --> G[\"Output Generation\"]')
    return "\n".join(lines)

if __name__ == "__main__":
    toc_mapping = {
        "pre_categorization": "1.3.1 Pre-Categorization of Text",
        "semantic_mapping": "2.3 Deep Semantic Mapping & Conceptual Equivalence",
        "cultural_adaptation": "2.4 Cultural & Contextual Adaptation Strategies",
        "iterative_refinement": "4.5 Iterative Refinement Capability",
        "chunking": "8.1 Document-Level Chunking & Context Metadata",
        "neologism_management": "8.2 Dynamic Neologism & Inventive Language Management",
        "self_reflection": "8.3 Self-Reflection & Iterative Refinement for Creative Segments",
        "multi_agent": "8.4 Multi-Agent Role-Based Collaboration",
        "tailored_evaluation": "8.5 Tailored Evaluation Metrics & Feedback Loop",
        "prompt_template_mgmt": "8.6 Prompt Template Management (Internal)",
        "integration_guidance": "8.7 Integration Guidance & Internal Implementation"
    }
    mermaid = generate_mermaid_flow(toc_mapping)
    print(mermaid)

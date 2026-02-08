"""
Extraction Tests (Phase 4 Deferred Item #17)

Generates synthetic content with complex formatting to test extraction robustness.
Focuses on structures that often break simple regex/text extraction:
- Markdown tables
- LaTeX mathematical formulas
- Embedded images (simulated)
- Complex list nesting
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class ExtractionTestConfig:
    """Configuration for complex extraction tests."""
    include_tables: bool = True
    include_latex: bool = True
    include_image_placeholders: bool = True
    nested_list_depth: int = 3


class ExtractionContentGenerator:
    """
    Generates content designed to stress-test the extraction pipeline.
    """
    
    def __init__(self, config: ExtractionTestConfig | None = None):
        self.config = config or ExtractionTestConfig()
    
    def generate_complex_document(self, topic: str = "Advanced Biology") -> str:
        """Generate a document with multiple complex elements."""
        sections = [f"# {topic} - Extraction Stress Test\n"]
        
        if self.config.include_tables:
            sections.append(self._generate_table_section())
            
        if self.config.include_latex:
            sections.append(self._generate_latex_section())
            
        if self.config.include_image_placeholders:
            sections.append(self._generate_image_section())
            
        return "\n\n".join(sections)
    
    def _generate_table_section(self) -> str:
        """Generate complex markdown tables."""
        return """
## Comparative Analysis (Table Test)

| Characteristic | Mitosis | Meiosis |
| :--- | :---: | ---: |
| Divisions | 1 | 2 |
| Daughter Cells | 2 | 4 |
| Genetic Comp. | Identical | Different |
| Role | Growth/Repair | Reproduction |

**Extraction Challenge:** Ensure table rows are not merged into single lines.
"""

    def _generate_latex_section(self) -> str:
        """Generate LaTeX formulas."""
        return r"""
## Mathematical Models (LaTeX Test)

The rate of population growth is modeled by:

$$ \frac{dN}{dt} = rN \left( 1 - \frac{N}{K} \right) $$

where:
- $N$ is population size
- $r$ is growth rate
- $K$ is carrying capacity

**Extraction Challenge:** Ensure LaTeX delimiters ($ and $$) are preserved or handled correctly.
"""

    def _generate_image_section(self) -> str:
        """Generate image placeholders."""
        return """
## Visual Data (Image Test)

![Figure 1: Cell Cycle Diagram](/images/cell_cycle.png)
*Figure 1: Phases of the cell cycle including G1, S, G2, and M phases.*

![Figure 2: DNA Replication](/images/dna_rep.jpg)
*Figure 2: Representation of the replication fork.*

**Extraction Challenge:** Ensure alt text and captions are associated with the correct context.
"""


def generate_extraction_test_suite(
    topics: list[str],
    include_all_features: bool = True,
) -> dict[str, str]:
    """
    Generate a suite of test documents for extraction validation.
    
    Returns:
        Dictionary mapping test names to markdown content.
    """
    config = ExtractionTestConfig(
        include_tables=include_all_features,
        include_latex=include_all_features,
        include_image_placeholders=include_all_features,
    )
    generator = ExtractionContentGenerator(config)
    
    suite = {}
    for topic in topics:
        suite[f"extraction_test_{topic.lower().replace(' ', '_')}"] = \
            generator.generate_complex_document(topic)
            
    return suite

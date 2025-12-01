"""
Kurioto Education Module

Provides educational tutoring capabilities with Socratic methodology,
grounded in parent-provided materials using Gemini File Search.
"""

from kurioto.education.material_manager import EducationalMaterialManager
from kurioto.education.parent_dashboard import EducationDashboard

__all__ = [
    "EducationalMaterialManager",
    "EducationDashboard",
]

from src.core.agent import ResearchAgent
from src.branches.models import BranchList
from src.branches.task import get_branches_specific_instructions


class BranchesResearchAgent(ResearchAgent):

    @property
    def research_type(self) -> str:
        return "branches"

    @property
    def goal(self) -> str:
        return f'מצא את כל הסניפים של רשת "{self._subject}" בישראל — שמות, כתובות, ערים — ממקורות אינטרנט.'

    @property
    def output_model_schema(self):
        return BranchList

    def build_task(self) -> str:
        return self._build_task(get_branches_specific_instructions(self._subject))

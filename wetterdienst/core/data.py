from abc import abstractmethod
from typing import Dict


class WDDataCore:
    @staticmethod
    @abstractmethod
    def _create_humanized_column_names_mapping(**kwargs) -> Dict[str, str]:
        pass

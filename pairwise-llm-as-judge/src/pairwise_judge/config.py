import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    system_a_name: str
    system_b_name: str
    system_a_model: str
    system_b_model: str
    judge_model: str
    dataset_name: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            system_a_name=os.environ.get("SYSTEM_A_NAME", "system-a"),
            system_b_name=os.environ.get("SYSTEM_B_NAME", "system-b"),
            system_a_model=os.environ.get("SYSTEM_A_MODEL", "gpt-4o-mini"),
            system_b_model=os.environ.get("SYSTEM_B_MODEL", "gpt-4.1-mini"),
            judge_model=os.environ.get("JUDGE_MODEL", "gpt-4.1"),
            dataset_name=os.environ.get("DATASET_NAME", "pairwise-demo"),
        )

"""Idempotently create a small demo dataset on Langfuse.

Each item's input is a question; we don't set expected_output because pairwise
LLM-as-a-judge is reference-free (the "ground truth" is the judge's preference).
"""

from langfuse import get_client

from .config import Config

DEMO_QUESTIONS: list[str] = [
    "Why does adding salt to water raise its boiling point?",
    "What is the difference between supervised and self-supervised learning?",
    "Explain the CAP theorem with a concrete example.",
    "How does a database B-tree index speed up range queries?",
    "What is the bias-variance tradeoff in machine learning?",
    "Briefly: what is the role of a Kalman filter in robotics?",
    "Why are GPUs faster than CPUs for matrix multiplication?",
    "What is eventual consistency and when is it acceptable?",
]


def seed(cfg: Config | None = None) -> str:
    """Create the dataset (if missing) and items. Returns the dataset name."""
    cfg = cfg or Config.from_env()
    langfuse = get_client()

    # create_dataset is idempotent on `name` server-side.
    langfuse.create_dataset(
        name=cfg.dataset_name,
        description="Demo dataset for pairwise LLM-as-a-judge (arxiv:2411.15594).",
        metadata={"purpose": "pairwise-judge-demo"},
    )

    # create_dataset_item does NOT dedupe by content, so we only add items if
    # the dataset is currently empty. This makes the seed script safe to re-run.
    existing = langfuse.get_dataset(cfg.dataset_name)
    if len(existing.items) > 0:
        print(f"Dataset '{cfg.dataset_name}' already has {len(existing.items)} items; skipping seed.")
        return cfg.dataset_name

    for q in DEMO_QUESTIONS:
        langfuse.create_dataset_item(
            dataset_name=cfg.dataset_name,
            input={"question": q},
        )
    langfuse.flush()
    print(f"Seeded dataset '{cfg.dataset_name}' with {len(DEMO_QUESTIONS)} items.")
    return cfg.dataset_name


if __name__ == "__main__":
    seed()

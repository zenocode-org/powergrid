# Werewolf — Abandoned Experiment

> **Status: Abandoned.** This directory documents a planned approach to social deduction synthetic data generation that was not implemented. It was superseded by the power grid dispatch task. The notes below are preserved for reference.
> I was thinking about this because I tackled a similar project for Mistral AI Hackathon: https://github.com/antoineFrau/media-guard.

---

## Motivation

The core idea was to use a social board game as a vehicle for evaluating two tightly related LLM capabilities:

1. **Manipulation** — can the model play a convincing Werewolf and avoid detection through language alone?
2. **Detection** — can the model, as a Villager, reason from a game transcript and correctly identify the Werewolf?

Both tasks involve multi-step reasoning over natural language, theory of mind, and consistency tracking. They are non-trivial for frontier models.

---

## Verification

The main complexity lies in output verification. Werewolf is a multi-turn social game driven by interactions; a single vote or move does not reflect the full game. In principle:

- **Detection**: Check whether the model’s vote targets a Werewolf. Ground truth roles are known from the dataset, so verification is deterministic.
- **Manipulation**: Check whether the model survives the village vote — i.e. the village eliminates someone else. This can be simulated with a heuristic vote model based on accusation patterns.

I also considered using an LLM to generate valid game states as dataset entries. But reducing either task to one move misses the cumulative effect of earlier statements, alliances, and consistency across rounds.

---

## Kaggle Dataset

The second approach was to source game transcripts from the [Kaggle Werewolf Game Arena dataset](https://www.kaggle.com/datasets/kaggle/werewolf-dataset/data) (31k+ LLM-vs-LLM games), which yields richer and more naturalistic transcripts than synthetic generation. The notebook in this directory (`notebook01592e0f28.ipynb`) was used to try detecting manipulation on that dataset.

---

## Why Abandoned

The Kaggle approach is conceptually stronger but introduced a dependency on an external dataset with its own format, licensing, and parsing complexity that was out of scope. The power grid dispatch task offered a cleaner pipeline (fully programmatic, no external data) with equally interesting failure modes.

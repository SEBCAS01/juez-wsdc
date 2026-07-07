---
language:
- en
license: mit
base_model: microsoft/deberta-v3-base
pipeline_tag: text-classification
library_name: transformers
tags:
- text-classification
- multi-label-classification
- deberta
- argumentation
- toulmin
- pytorch
inference:
  parameters:
    function_to_apply: sigmoid
widget:
- text: "Therefore, I conclude that the hypothesis is correct."
  example_title: "Example 1"
- text: "The experiment showed a 95% success rate in controlled conditions."
  example_title: "Example 2"
- text: "This assumes that all variables remain constant."
  example_title: "Example 3"
---

# TRACE-DeBERTa-v3-base

A fine-tuned DeBERTa-v3-base model that **labels each sentence with Constructive Elements** of reasoning, used as a component of the **TRACE** framework.

> **TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation**

This model is **a multi-label sentence classifier**, not a scoring model. It assigns one or more Constructive Element tags to each input sentence; the downstream TRACE pipeline aggregates these labels into a reasoning quality score.

- **Developed by:** Korea Institute of Science and Technology Information (KISTI)
- **Model type:** Multi-label text classification (sentence-level)
- **Base model:** `microsoft/deberta-v3-base`
- **Language:** English

## Role in the TRACE Pipeline

TRACE evaluates Chain-of-Thought (CoT) reasoning of LLMs in two stages:

1. **Sentence labeling (this model).** Reasoning text is split into sentences with spaCy, and each sentence is multi-labeled with Constructive Elements.
2. **Score extraction (rule-based).** A separate rule-based component computes State Validity and Transition Coherence from the resulting label sequence to produce the final TRACE score.

This model is responsible only for step 1.

## Labels

The model outputs 8 independent confidence scores (sigmoid). A label is assigned when its score is ≥ 0.5.

Based on Toulmin's argumentation model:

- **Claim** — a conclusion, assertion, or answer being argued for
- **Data/Evidence** — concrete facts, observations, or given information
- **Warrant** — reasoning that connects evidence to the claim
- **Backing** — support for the warrant (definitions, theorems, principles)
- **Qualifier** — expressions of certainty or uncertainty
- **Rebuttal** — counterarguments, exceptions, or alternative considerations

Extended with Flavell's metacognition theory:

- **Monitoring** — self-checking, tracking progress, noticing errors
- **Evaluation** — judging the quality or correctness of reasoning

## Usage

### Quick start

```python
from transformers import pipeline

clf = pipeline(
    "text-classification",
    model="hyyangkisti/TRACE-DeBERTa-v3-base",
    top_k=None,  # return all label scores
)

clf("Therefore, I conclude that the hypothesis is correct.")
# [[{'label': 'Claim', 'score': 0.95}, {'label': 'Qualifier', 'score': 0.82}, ...]]
```

## Inputs and Outputs

- **Input:** a single English sentence (max 512 tokens, DeBERTa limit).
- **Output:** 8-dimensional vector of independent sigmoid probabilities, one per label.

## Training Data

The model was fine-tuned on approximately 100K reasoning sentences with multi-label annotations grounded in Toulmin's argumentation model and Flavell's metacognition theory. Sentences were segmented via spaCy.

## Acknowledgment

This work has been supported by the Korea Institute of Science and Technology Information (grant K26L2M3C7).

## Citation

```bibtex
@misc{kim2026tracetoulminbasedreasoningassessment,
      title={TRACE: Toulmin-based Reasoning Assessment through Constructive Elements for LLM CoT Evaluation}, 
      author={Yundong Kim and Heyoung Yang},
      year={2026},
      eprint={2605.29656},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2605.29656}, 
}
```

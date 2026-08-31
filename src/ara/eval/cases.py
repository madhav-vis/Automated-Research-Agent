"""Gold-standard test cases for retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

from ara.models import SearchIntentProfile


@dataclass
class ExpectedPaper:
    """A paper the eval expects to find, matched by DOI, arXiv ID, or title substring."""
    title_contains: str
    dois: list[str] = field(default_factory=list)
    arxiv_ids: list[str] = field(default_factory=list)


@dataclass
class GoldCase:
    """A query paired with papers that must appear in results.

    query: specific query for Tier 1 (direct tool call).
    agent_query: vague/natural query for Tier 2 (agent reasoning). Falls back to query if empty.
    intent_profile: simulates the narrowing dialogue output for Tier 2.
    """
    name: str
    query: str
    agent_query: str = ""
    intent_profile: SearchIntentProfile | None = None
    expected_papers: list[ExpectedPaper] = field(default_factory=list)
    min_recall: float = 1.0


GOLD_SET: list[GoldCase] = [
    GoldCase(
        name="attention_transformers",
        query="attention is all you need transformer",
        agent_query="attention transformers",
        intent_profile=SearchIntentProfile(
            original_query="attention transformers",
            identified_topic="Transformer Architecture and Self-Attention",
            domain="Natural Language Processing",
            methods=["self-attention", "transformer"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Attention Is All You Need",
                dois=["10.48550/arXiv.1706.03762", "10.65215/2q58a426"],
                arxiv_ids=["1706.03762"],
            ),
        ],
    ),
    GoldCase(
        name="deep_learning_imagenet",
        query="ImageNet classification deep convolutional neural networks",
        agent_query="deep learning",
        intent_profile=SearchIntentProfile(
            original_query="deep learning",
            identified_topic="Deep Learning for Image Classification",
            domain="Computer Vision",
            methods=["convolutional neural networks", "image classification"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="ImageNet classification with deep convolutional neural networks",
                dois=["10.1145/3065386"],
            ),
        ],
    ),
    GoldCase(
        name="bitcoin",
        query="Bitcoin peer-to-peer electronic cash",
        agent_query="Bitcoin",
        intent_profile=SearchIntentProfile(
            original_query="Bitcoin",
            identified_topic="Bitcoin and Cryptocurrency",
            domain="Cryptography",
            application="Peer-to-peer electronic cash",
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Bitcoin: A Peer-to-Peer Electronic Cash System",
                dois=["10.2139/ssrn.3440802"],
            ),
        ],
    ),
    GoldCase(
        name="resnet",
        query="deep residual learning image recognition",
        agent_query="residual networks computer vision",
        intent_profile=SearchIntentProfile(
            original_query="residual networks computer vision",
            identified_topic="Deep Residual Networks",
            domain="Computer Vision",
            methods=["residual learning", "deep neural networks"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Deep Residual Learning for Image Recognition",
                dois=["10.1109/cvpr.2016.90", "10.48550/arxiv.1512.03385"],
            ),
        ],
    ),
    GoldCase(
        name="attn",
        query="pre-target activity visual cortex spatial feature attention",
        agent_query="brain activity before visual attention tasks",
        intent_profile=SearchIntentProfile(
            original_query="brain activity before visual attention tasks",
            identified_topic="Pre-Target Neural Activity in Visual Attention",
            domain="Cognitive Neuroscience",
            application="Visual attention",
            methods=["spatial attention", "feature attention", "pre-target activity"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Pre-target activity in visual cortex predicts behavioral performance on spatial and feature attention tasks",
                dois=["10.1016/j.brainres.2005.09.068"],
            ),
        ],
    ),
    GoldCase(
        name="adam_optimizer",
        query="Adam method stochastic optimization",
        agent_query="best optimizer for training neural networks",
        intent_profile=SearchIntentProfile(
            original_query="best optimizer for training neural networks",
            identified_topic="Adaptive Optimization Methods for Deep Learning",
            domain="Machine Learning",
            methods=["stochastic optimization", "adaptive learning rate"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Adam: A Method for Stochastic Optimization",
                dois=["10.48550/arxiv.1412.6980"],
                arxiv_ids=["1412.6980"],
            ),
        ],
    ),
    GoldCase(
        name="lstm",
        query="long short-term memory recurrent neural network",
        agent_query="sequence modeling recurrent networks",
        intent_profile=SearchIntentProfile(
            original_query="sequence modeling recurrent networks",
            identified_topic="Long Short-Term Memory Networks",
            domain="Machine Learning",
            methods=["long short-term memory", "recurrent neural networks"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Long Short-Term Memory",
                dois=["10.1162/neco.1997.9.8.1735"],
            ),
        ],
    ),
    GoldCase(
        name="BCI",
        query="motor cortex BCI cursor control",
        agent_query="brain computer interface cursor",
        intent_profile=SearchIntentProfile(
            original_query="brain computer interface cursor",
            identified_topic="Brain-Computer Interface Cursor Control",
            domain="Neuroscience",
            application="Brain-computer interfaces",
            methods=["motor cortex", "cursor control"],
            recency="2y",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Speech motor cortex enables BCI cursor control and click",
                dois=["10.1088/1741-2552/add0e5"],
            ),
        ],
    ),
    GoldCase(
        name="bert",
        query="BERT pre-training deep bidirectional transformers language",
        agent_query="language model pretraining NLP",
        intent_profile=SearchIntentProfile(
            original_query="language model pretraining NLP",
            identified_topic="BERT and Bidirectional Language Model Pre-Training",
            domain="Natural Language Processing",
            methods=["bidirectional transformers", "pre-training", "masked language modeling"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="BERT: Pre-training of Deep Bidirectional Transformers",
                arxiv_ids=["1810.04805"],
            ),
        ],
    ),
    GoldCase(
        name="alphafold",
        query="AlphaFold protein structure prediction",
        agent_query="AI protein folding",
        intent_profile=SearchIntentProfile(
            original_query="AI protein folding",
            identified_topic="AI-Based Protein Structure Prediction",
            domain="Computational Biology",
            application="Protein structure prediction",
            methods=["deep learning", "protein folding"],
            recency="foundational",
        ),
        expected_papers=[
            ExpectedPaper(
                title_contains="Highly accurate protein structure prediction with AlphaFold",
                dois=["10.1038/s41586-021-03819-2"],
            ),
        ],
    ),
]

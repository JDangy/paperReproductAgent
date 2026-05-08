from __future__ import annotations

from app.benchmark.schema import MetricSpec


METRIC_ALIASES: dict[str, list[str]] = {
    "auc@5": ["AUC@5", "pose_auc_5", "auc_5", "AUC 5"],
    "auc@10": ["AUC@10", "pose_auc_10", "auc_10", "AUC 10"],
    "auc@20": ["AUC@20", "pose_auc_20", "auc_20", "AUC 20"],
    "precision": ["Prec", "precision", "P"],
    "matching_score": ["MScore", "matching score", "matching_score"],
    "fps": ["FPS", "frames/s", "throughput"],
    "latency_ms": ["latency", "ms/img", "time"],
    "wer": ["WER", "word error rate"],
    "cer": ["CER", "character error rate"],
    "bleu": ["BLEU"],
    "accuracy": ["accuracy", "acc", "top-1", "top1"],
    "top5_accuracy": ["top-5", "top5", "top-5 accuracy"],
    "f1": ["F1", "micro-F1", "span-F1"],
    "precision_nlp": ["precision"],
    "recall": ["recall"],
}


def metric_specs_for_family(task_family: str) -> list[MetricSpec]:
    if task_family == "local_feature_matching":
        return [
            MetricSpec(name="AUC@5", canonical_name="auc@5", direction="higher_is_better", unit="%"),
            MetricSpec(name="AUC@10", canonical_name="auc@10", direction="higher_is_better", unit="%"),
            MetricSpec(name="AUC@20", canonical_name="auc@20", direction="higher_is_better", unit="%"),
            MetricSpec(name="Precision", canonical_name="precision", direction="higher_is_better", unit="%"),
            MetricSpec(name="MatchingScore", canonical_name="matching_score", direction="higher_is_better", unit="%"),
            MetricSpec(name="FPS", canonical_name="fps", direction="higher_is_better"),
            MetricSpec(name="Latency", canonical_name="latency_ms", direction="lower_is_better", unit="ms"),
        ]
    if task_family == "zero_shot_classification":
        return [
            MetricSpec(name="Top-1 Accuracy", canonical_name="accuracy", direction="higher_is_better", unit="%"),
            MetricSpec(name="Top-5 Accuracy", canonical_name="top5_accuracy", direction="higher_is_better", unit="%"),
        ]
    if task_family == "asr":
        return [
            MetricSpec(name="WER", canonical_name="wer", direction="lower_is_better", unit="%"),
            MetricSpec(name="CER", canonical_name="cer", direction="lower_is_better", unit="%"),
            MetricSpec(name="BLEU", canonical_name="bleu", direction="higher_is_better"),
        ]
    if task_family == "sequence_labeling":
        return [
            MetricSpec(name="F1", canonical_name="f1", direction="higher_is_better", unit="%"),
            MetricSpec(name="Precision", canonical_name="precision_nlp", direction="higher_is_better", unit="%"),
            MetricSpec(name="Recall", canonical_name="recall", direction="higher_is_better", unit="%"),
        ]
    return []


def classify_task_family(*, task: str | None, datasets: list[str], metrics: list[str], keywords: list[str], repo_text: str, scripts: list[str]) -> str:
    haystack = " ".join([
        task or "",
        " ".join(datasets),
        " ".join(metrics),
        " ".join(keywords),
        repo_text[:20000],
        " ".join(scripts),
    ]).lower()

    scores = {
        "local_feature_matching": _score_terms(haystack, [
            "feature matching", "local feature", "keypoint", "homography", "pose estimation",
            "megadepth", "scannet", "hpatches", "auc@5", "matching score", "match_pairs",
        ]),
        "zero_shot_classification": _score_terms(haystack, [
            "clip", "zero-shot", "zero shot", "image-text", "imagenet", "cifar", "top-1", "top-5",
        ]),
        "asr": _score_terms(haystack, [
            "speech recognition", "automatic speech", "transcribe", "asr", "wer", "cer", "librispeech", "whisper",
        ]),
        "sequence_labeling": _score_terms(haystack, [
            "sequence labeling", "named entity", "ner", "conll", "span-f1", "flair", "tagger",
        ]),
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score > 0 else "unknown"


def _score_terms(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)

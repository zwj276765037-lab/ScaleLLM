"""Original streaming FP32 LM head, extracted without numerical changes."""
from typing import Sequence, Callable
import numpy as np
from .scalellm_runtime import RuntimeContractError


def streaming_lm_head(
    hidden: np.ndarray,
    target_token_ids: Sequence[int],
    vocabulary_size: int,
    weight_loader: Callable[[int, int], np.ndarray],
    chunk_rows: int,
    top_k: int = 5,
) -> dict:
    """Compute exact float32 logits statistics without materializing full logits."""
    values = np.asarray(hidden, dtype=np.float32)
    targets = np.asarray(target_token_ids, dtype=np.int64)
    if values.ndim != 2 or values.shape[1] <= 0:
        raise ValueError("LM-head hidden input must be a nonempty matrix")
    if (type(vocabulary_size) is not int or vocabulary_size <= 0 or
            type(chunk_rows) is not int or chunk_rows <= 0):
        raise ValueError("LM-head vocabulary/chunk sizes must be positive integers")
    if targets.shape != (values.shape[0],) or np.any(targets < 0) or np.any(
        targets >= vocabulary_size
    ):
        raise ValueError("LM-head targets must match rows and vocabulary")
    if not 1 <= top_k <= min(chunk_rows, vocabulary_size):
        raise ValueError("invalid LM-head top_k")

    row_count = values.shape[0]
    running_max = np.full(row_count, -np.inf, dtype=np.float64)
    running_sum = np.zeros(row_count, dtype=np.float64)
    target_logits = np.full(row_count, np.nan, dtype=np.float32)
    top_values = np.full((row_count, top_k), -np.inf, dtype=np.float32)
    top_ids = np.full((row_count, top_k), -1, dtype=np.int64)
    rows = np.arange(row_count)

    for start in range(0, vocabulary_size, chunk_rows):
        stop = min(start + chunk_rows, vocabulary_size)
        weights = np.asarray(weight_loader(start, stop), dtype=np.float32)
        expected_shape = (stop - start, values.shape[1])
        if weights.shape != expected_shape or not np.all(np.isfinite(weights)):
            raise RuntimeContractError(
                f"LM-head weight chunk shape/value drifted: "
                f"expected={expected_shape} actual={weights.shape}"
            )
        logits = np.asarray(values @ weights.T, dtype=np.float32)
        block_max = np.max(logits, axis=1).astype(np.float64)
        next_max = np.maximum(running_max, block_max)
        running_sum = (
            running_sum * np.exp(running_max - next_max)
            + np.sum(
                np.exp(logits.astype(np.float64) - next_max[:, None]), axis=1
            )
        )
        running_max = next_max

        target_mask = (targets >= start) & (targets < stop)
        if np.any(target_mask):
            target_rows = rows[target_mask]
            target_logits[target_mask] = logits[
                target_rows, targets[target_mask] - start
            ]

        block_ids = np.arange(start, stop, dtype=np.int64)
        candidate_values = np.concatenate((top_values, logits), axis=1)
        candidate_ids = np.concatenate((
            top_ids,
            np.broadcast_to(block_ids, (row_count, stop - start)),
        ), axis=1)
        order = np.lexsort((candidate_ids, -candidate_values), axis=1)[:, :top_k]
        top_values = np.take_along_axis(candidate_values, order, axis=1)
        top_ids = np.take_along_axis(candidate_ids, order, axis=1)

    if np.any(~np.isfinite(target_logits)):
        raise RuntimeContractError("LM-head target logits were not populated")
    logsumexp = running_max + np.log(running_sum)
    nll = logsumexp - target_logits.astype(np.float64)
    return {
        "rows": row_count,
        "nll_sum": float(np.sum(nll, dtype=np.float64)),
        "mean_nll": float(np.mean(nll, dtype=np.float64)),
        "per_row_nll": nll.tolist(),
        "target_logits": target_logits.astype(np.float64).tolist(),
        "top_token_ids": top_ids.tolist(),
        "top_logits": top_values.astype(np.float64).tolist(),
    }


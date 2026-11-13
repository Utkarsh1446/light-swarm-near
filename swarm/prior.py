"""Small numpy MLP used as a search prior.

Three hidden layers, a few hundred thousand parameters. Trained with Adam on
synthetic (demo features -> ops used) pairs from this repo's generator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from swarm.dsl import OP_NAMES, apply_program, shape


N_FEATURES = 64


def _hist(grid: list[list[int]], bins: int = 10) -> np.ndarray:
    counts = np.zeros(bins, dtype=np.float32)
    for row in grid:
        for value in row:
            counts[value] += 1
    total = max(int(counts.sum()), 1)
    return counts / total


def _center(grid: list[list[int]]) -> tuple[float, float]:
    height, width = shape(grid)
    mass = 0.0
    row_acc = 0.0
    col_acc = 0.0
    for row in range(height):
        for col in range(width):
            if grid[row][col]:
                mass += 1
                row_acc += row
                col_acc += col
    if mass == 0:
        return 0.5, 0.5
    return row_acc / mass / max(height, 1), col_acc / mass / max(width, 1)


def _residual(grid_in: list[list[int]], grid_out: list[list[int]], name: str) -> float:
    produced = apply_program(grid_in, (name,))
    if produced is None or shape(produced) != shape(grid_out):
        return 0.0
    height, width = shape(grid_out)
    same = 0
    for row in range(height):
        for col in range(width):
            if produced[row][col] == grid_out[row][col]:
                same += 1
    return same / float(height * width)


def featurize(demos: list[tuple[list[list[int]], list[list[int]]]]) -> np.ndarray:
    """Fixed 64-d summary of the demonstration pairs."""
    features = np.zeros(N_FEATURES, dtype=np.float32)
    if not demos:
        return features
    grid_in, grid_out = demos[0]
    height_in, width_in = shape(grid_in)
    height_out, width_out = shape(grid_out)
    features[0] = height_in / 12.0
    features[1] = width_in / 12.0
    features[2] = height_out / 12.0
    features[3] = width_out / 12.0
    features[4] = 1.0 if (height_in, width_in) == (height_out, width_out) else 0.0
    features[5:15] = _hist(grid_in)
    features[15:25] = _hist(grid_out)
    features[25] = float(np.abs(features[5:15] - features[15:25]).sum())
    if features[4] == 1.0:
        changed = 0
        total = height_in * width_in
        for row in range(height_in):
            for col in range(width_in):
                if grid_in[row][col] != grid_out[row][col]:
                    changed += 1
        features[26] = changed / float(total)
    else:
        features[26] = 1.0
    in_r, in_c = _center(grid_in)
    out_r, out_c = _center(grid_out)
    features[27] = in_r
    features[28] = in_c
    features[29] = out_r
    features[30] = out_c
    features[31] = abs(in_r - out_r)
    features[32] = abs(in_c - out_c)
    # How close each single op already is. Depth-1 tasks become easy; depth-2
    # tasks stay partial, which is what the prior has to rank.
    for index, name in enumerate(OP_NAMES):
        features[33 + index] = _residual(grid_in, grid_out, name)
    if len(features) != N_FEATURES:
        raise RuntimeError("feature width drifted")
    return features


@dataclass
class TrainReport:
    params: int
    epochs: int
    samples: int
    width: int
    seconds: float
    top1_accuracy: float
    top6_recall: float
    depth2_top6_recall: float
    chance_top1: float


class Prior:
    def __init__(self, width: int, rng: np.random.Generator):
        dims = [N_FEATURES, width, width, width, len(OP_NAMES)]
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        for index in range(len(dims) - 1):
            fan_in = dims[index]
            scale = np.sqrt(2.0 / fan_in) if index < len(dims) - 2 else np.sqrt(1.0 / fan_in)
            self.weights.append(rng.normal(0.0, scale, size=(dims[index], dims[index + 1])).astype(np.float32))
            self.biases.append(np.zeros(dims[index + 1], dtype=np.float32))
        self.width = width

    def n_params(self) -> int:
        return int(sum(item.size for item in self.weights + self.biases))

    def logits(self, features: np.ndarray) -> np.ndarray:
        hidden = features.astype(np.float32, copy=False)
        last = len(self.weights) - 1
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases)):
            hidden = hidden @ weight + bias
            if index != last:
                np.maximum(hidden, 0, out=hidden)
        return hidden

    def train(self, samples: list[tuple[np.ndarray, np.ndarray]], epochs: int, lr: float, seed: int, log_loss: bool = False) -> None:
        if not samples:
            return
        self.epoch_loss = []
        rng = np.random.default_rng(seed)
        order = np.arange(len(samples))
        moment_w = [np.zeros_like(weight) for weight in self.weights]
        moment_b = [np.zeros_like(bias) for bias in self.biases]
        velocity_w = [np.zeros_like(weight) for weight in self.weights]
        velocity_b = [np.zeros_like(bias) for bias in self.biases]
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        step = 0
        batch = 64
        for _ in range(epochs):
            rng.shuffle(order)
            for start in range(0, len(order), batch):
                step += 1
                batch_ids = order[start : start + batch]
                xs = np.stack([samples[int(i)][0] for i in batch_ids]).astype(np.float32)
                ys = np.stack([samples[int(i)][1] for i in batch_ids]).astype(np.float32)
                grads_w, grads_b = _batch_grads(self.weights, self.biases, xs, ys)
                for index in range(len(self.weights)):
                    self.weights[index], moment_w[index], velocity_w[index] = _adam(
                        self.weights[index], grads_w[index], moment_w[index], velocity_w[index], step, lr, beta1, beta2, eps
                    )
                    self.biases[index], moment_b[index], velocity_b[index] = _adam(
                        self.biases[index], grads_b[index], moment_b[index], velocity_b[index], step, lr, beta1, beta2, eps
                    )
            if log_loss:
                self.epoch_loss.append(_mean_bce(self, samples))


def _mean_bce(prior: Prior, samples: list[tuple[np.ndarray, np.ndarray]]) -> float:
    total = 0.0
    for features, target in samples:
        logits = prior.logits(features)
        total += float(np.mean(np.maximum(logits, 0) - logits * target + np.log1p(np.exp(-np.abs(logits)))))
    return total / len(samples)


def _adam(param, grad, moment, velocity, step, lr, beta1, beta2, eps):
    moment = beta1 * moment + (1 - beta1) * grad
    velocity = beta2 * velocity + (1 - beta2) * (grad * grad)
    moment_hat = moment / (1 - beta1**step)
    velocity_hat = velocity / (1 - beta2**step)
    param = param - lr * moment_hat / (np.sqrt(velocity_hat) + eps)
    return param, moment, velocity


def _batch_grads(weights, biases, xs, ys):
    activations = [xs]
    pre = []
    hidden = xs
    last = len(weights) - 1
    for index, (weight, bias) in enumerate(zip(weights, biases)):
        zed = hidden @ weight + bias
        pre.append(zed)
        if index == last:
            hidden = zed
        else:
            hidden = np.maximum(zed, 0)
        activations.append(hidden)
    # BCE-with-logits gradient on the batch mean.
    probs = 1.0 / (1.0 + np.exp(-np.clip(activations[-1], -20, 20)))
    delta = (probs - ys) / xs.shape[0]
    grads_w = [None] * len(weights)
    grads_b = [None] * len(biases)
    for index in range(last, -1, -1):
        incoming = activations[index]
        grads_w[index] = incoming.T @ delta
        grads_b[index] = delta.sum(axis=0)
        if index == 0:
            break
        delta = delta @ weights[index].T
        delta *= (pre[index - 1] > 0).astype(np.float32)
    return grads_w, grads_b


def evaluate(prior: Prior, rows: list[tuple[np.ndarray, np.ndarray]]) -> tuple[float, float, float]:
    if not rows:
        return 0.0, 0.0, 0.0
    top1 = 0
    top6 = 0
    depth2 = 0
    depth2_n = 0
    for features, target in rows:
        scores = prior.logits(features)
        ranking = np.argsort(-scores)
        true = np.flatnonzero(target > 0.5)
        if true.size and int(ranking[0]) in set(int(i) for i in true):
            top1 += 1
        if set(int(i) for i in true).issubset(set(int(i) for i in ranking[:6])):
            top6 += 1
        if true.size >= 2:
            depth2_n += 1
            if set(int(i) for i in true).issubset(set(int(i) for i in ranking[:6])):
                depth2 += 1
    n = len(rows)
    return top1 / n, top6 / n, (depth2 / depth2_n if depth2_n else 0.0)

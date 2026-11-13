"""Feature mask used by the five upbringing learners.

The shared featurizer's last 16 coordinates are single-operation residuals.
They name a depth-1 rule. Upbringing training and search zero them so a
curriculum can change which programs are ranked highly. The first frozen
ablation does not use this mask.
"""

from __future__ import annotations

import numpy as np

from swarm.prior import featurize


def mask_copy(demos) -> np.ndarray:
    features = featurize(demos).copy()
    features[33:49] = 0
    return features

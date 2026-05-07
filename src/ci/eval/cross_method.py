"""E3: pairwise Spearman rank correlations across three signals.

Inputs are dicts {listing_id: score}. Listing IDs must match across all three.
"""
from __future__ import annotations

from scipy.stats import spearmanr


def three_way_spearman(
    rule_scores: dict[str, float],
    gold_visual_scores: dict[str, float],
    agent_visual_scores: dict[str, float],
) -> dict[str, float]:
    common = sorted(set(rule_scores) & set(gold_visual_scores) & set(agent_visual_scores))
    if len(common) < 2:
        return {
            "rule_vs_gold_visual": 0.0,
            "rule_vs_agent_visual": 0.0,
            "gold_visual_vs_agent_visual": 0.0,
            "n": len(common),
        }
    rule = [rule_scores[lid] for lid in common]
    gold = [gold_visual_scores[lid] for lid in common]
    agent = [agent_visual_scores[lid] for lid in common]

    return {
        "rule_vs_gold_visual": float(spearmanr(rule, gold).correlation),
        "rule_vs_agent_visual": float(spearmanr(rule, agent).correlation),
        "gold_visual_vs_agent_visual": float(spearmanr(gold, agent).correlation),
        "n": len(common),
    }

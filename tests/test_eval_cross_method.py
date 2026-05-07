from ci.eval.cross_method import three_way_spearman


def test_three_way_returns_pairwise_rhos():
    rule = {"A": 80, "B": 50, "C": 30}
    gold_v = {"A": 80, "B": 50, "C": 30}  # identical to rule
    agent_v = {"A": 30, "B": 50, "C": 80}  # reversed
    out = three_way_spearman(rule, gold_v, agent_v)
    assert "rule_vs_gold_visual" in out
    assert "rule_vs_agent_visual" in out
    assert "gold_visual_vs_agent_visual" in out
    assert out["rule_vs_gold_visual"] == 1.0  # perfect
    assert out["rule_vs_agent_visual"] < 0  # reversed

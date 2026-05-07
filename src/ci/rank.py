from ci.schemas import NormalizedListing, RankRow, ScoreRecord, VisionScore
from ci.vision.composite import compute_composite, DEFAULT_ALPHA


def rank_listings(
    pairs: list[tuple[NormalizedListing, ScoreRecord]],
    *,
    vision_scores: dict[str, VisionScore] | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> list[RankRow]:
    """Sort listings by composite_score (or rule_score if no vision); produce RankRows.

    When vision_scores is None: ratio = price / rule_score (today's behavior).
    When vision_scores is provided: ratio = price / composite_score.
    """
    rows: list[RankRow] = []
    for n, sc in pairs:
        vs = (vision_scores or {}).get(n.listing_id)
        rule_score = sc.score_common
        visual_score = vs.visual_score if vs else None
        composite_score = (
            compute_composite(rule_score=rule_score, visual_score=visual_score, alpha=alpha)
            if visual_score is not None else None
        )
        denom = composite_score if composite_score is not None else rule_score
        ratio = round(n.price / denom, 2) if denom > 0 else 0.0
        imputed_aspects = list(vs.imputed_aspects) if vs else []
        rows.append(RankRow(
            listing_id=n.listing_id, platform=n.platform, price=n.price,
            rule_score=rule_score, visual_score=visual_score,
            composite_score=composite_score, ratio=ratio,
            disclosure_count=sc.disclosure_count, imputed_dims=sc.imputed_dims,
            imputed_aspects=imputed_aspects,
        ))
    # Sort by composite_score (or rule_score if absent), descending.
    rows.sort(key=lambda r: (r.composite_score if r.composite_score is not None else r.rule_score),
              reverse=True)
    return rows

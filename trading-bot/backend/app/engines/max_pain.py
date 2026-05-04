"""
Max Pain calculation engine.

Definition: for a given options expiry, the Max Pain strike is the price at which
option BUYERS suffer maximum total loss (i.e., option SELLERS' total profit is maximised).

Algorithm:
  For each candidate strike K:
    pain(K) = Σ [ call_OI(S) × max(0, S − K) ]   ← pain to call holders
            + Σ [ put_OI(S)  × max(0, K − S) ]   ← pain to put holders
  Max Pain = K that MINIMISES pain(K)

Higher call OI above spot and higher put OI below spot both pull the max-pain
strike toward the centre of the distribution — this is the price that maximises
sellers' expiry-day profit.
"""
from __future__ import annotations


def calculate_max_pain(options_chain: list[dict]) -> float:
    """
    Compute the Max Pain strike from a live options chain snapshot.

    Args:
        options_chain: list of dicts, each with keys:
            'strike'   (float)  — strike price
            'call_oi'  (int)    — call open interest at this strike
            'put_oi'   (int)    — put open interest at this strike

    Returns:
        float — the max pain strike price.
        Returns 0.0 if the chain is empty or malformed.
    """
    if not options_chain:
        return 0.0

    strikes = sorted({float(row["strike"]) for row in options_chain})
    if not strikes:
        return 0.0

    # Build lookup: strike → (call_oi, put_oi)
    oi: dict[float, tuple[int, int]] = {}
    for row in options_chain:
        s = float(row["strike"])
        c_oi = int(row.get("call_oi", 0))
        p_oi = int(row.get("put_oi", 0))
        if s in oi:
            existing_c, existing_p = oi[s]
            oi[s] = (existing_c + c_oi, existing_p + p_oi)
        else:
            oi[s] = (c_oi, p_oi)

    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for test_strike in strikes:
        total_pain = 0.0
        for s, (c_oi, p_oi) in oi.items():
            # Pain to call holders if spot = test_strike at expiry
            total_pain += c_oi * max(0.0, s - test_strike)
            # Pain to put holders if spot = test_strike at expiry
            total_pain += p_oi * max(0.0, test_strike - s)

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    return max_pain_strike


def pcr_signal(total_put_oi: int, total_call_oi: int) -> str:
    """
    Put/Call Ratio contrarian signal.

    Returns:
      'bullish_extreme'  — PCR > 1.3 (excess puts = contrarian bullish)
      'bearish_extreme'  — PCR < 0.7 (excess calls = contrarian bearish)
      'neutral'          — 0.7 ≤ PCR ≤ 1.3
    """
    if total_call_oi == 0:
        return "neutral"
    pcr = total_put_oi / total_call_oi
    if pcr > 1.3:
        return "bullish_extreme"
    if pcr < 0.7:
        return "bearish_extreme"
    return "neutral"

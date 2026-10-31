from pathlib import Path

p = Path("evaluation/write_cost_section.py")
t = p.read_text(encoding="utf-8")
start = t.index("# Verdict is computed from the numbers, not assumed")
end = t.index('imp_text = ""')

NEW = '''# Verdict is computed from the numbers, not assumed
def val(v, m, col):
    return float(get(v, m, col))


err_l, err_p = val("unseen", "Learned", "mae_log"), val("unseen", "Planner", "mae_log")
q_l, q_p = val("unseen", "Learned", "p90_q_error"), val("unseen", "Planner", "p90_q_error")
sp_l, sp_p = val("unseen", "Learned", "spearman"), val("unseen", "Planner", "spearman")
auc_l = val("unseen", "Learned", "auc_slow") if "auc_slow" in summary.columns else None
auc_p = val("unseen", "Planner", "auc_slow") if "auc_slow" in summary.columns else None

more_accurate = err_l < 0.9 * err_p and q_l < q_p
rank_tied = abs(sp_l - sp_p) <= 0.02
auc_tied = auc_l is None or abs(auc_l - auc_p) <= 0.01

if auc_l is None:
    auc_text = ""
elif auc_l == auc_p:
    auc_text = (f" and the slow-versus-fast AUC was {auc_l} for both, which is an easy distinction here "
                "because the slow queries cost far more than the fast ones")
else:
    auc_text = f" and the slow-versus-fast AUC was {auc_l} against {auc_p}"

if more_accurate and rank_tied and auc_tied:
    verdict = (
        f"On unseen query shapes the learned model predicted running time more accurately than the "
        f"calibrated planner cost (log error {err_l} against {err_p}; 90th-percentile q-error {q_l} "
        f"against {q_p}), but it did not rank queries better (rank correlation {sp_l} against {sp_p})"
        f"{auc_text}. A guardrail only has to decide whether a query is heavy, and the planner cost "
        "already does that well; the learned model's advantage is in estimating how long a query will "
        "take. Because the data is small and comes from one schema, it was not added to the guardrail, "
        "and the result needs confirming before it is relied on."
    )
elif (not more_accurate) and rank_tied and auc_tied:
    verdict = (
        f"On unseen query shapes the learned model was no more accurate than the calibrated planner cost "
        f"(log error {err_l} against {err_p}; rank correlation {sp_l} against {sp_p}){auc_text}, so it "
        "was not added to the guardrail."
    )
else:
    verdict = (
        f"On unseen query shapes the results were mixed (log error {err_l} against {err_p}; "
        f"90th-percentile q-error {q_l} against {q_p}; rank correlation {sp_l} against {sp_p})"
        f"{auc_text}. There is no dependable advantage, so the learned model was not added to the guardrail."
    )

'''
t = t[:start] + NEW + t[end:]
p.write_text(t, encoding="utf-8")
print("patched")

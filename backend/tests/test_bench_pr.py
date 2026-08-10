import pytest

from benchmarks import bench_pr


def test_percentile_picks_the_nearest_rank():
    values = [10, 20, 30, 40, 50]
    assert bench_pr.percentile(values, 50) == 30
    assert bench_pr.percentile(values, 95) == 50


def test_percentile_of_a_single_value():
    assert bench_pr.percentile([7.5], 50) == 7.5


def test_percentile_of_empty_is_zero():
    assert bench_pr.percentile([], 50) == 0.0


def test_summarize_computes_both_reductions():
    summary = bench_pr.summarize(cold=[1000.0], warm=[200.0], full=[500.0], incremental=[250.0])

    assert summary["cold_vs_warm_reduction_pct"] == pytest.approx(80.0)
    assert summary["full_vs_incremental_reduction_pct"] == pytest.approx(50.0)


def test_summarize_reports_percentiles():
    summary = bench_pr.summarize(
        cold=[100.0, 200.0], warm=[10.0, 20.0], full=[50.0], incremental=[25.0]
    )
    assert summary["warm_p50_ms"] == 10.0
    assert summary["warm_p95_ms"] == 20.0


def test_summarize_with_no_samples_does_not_divide_by_zero():
    summary = bench_pr.summarize(cold=[], warm=[], full=[], incremental=[])
    assert summary["cold_vs_warm_reduction_pct"] == 0.0


def test_render_table_labels_each_baseline():
    summary = bench_pr.summarize(cold=[1000.0], warm=[200.0], full=[500.0], incremental=[250.0])
    table = bench_pr.render_table(summary)

    assert "Cold vs warm" in table
    assert "Full reparse vs incremental" in table
    assert "80.0" in table

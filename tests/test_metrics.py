from eval.metrics import (
    GenerationLogEntry,
    product_preservation_rate,
    average_generation_time,
    generation_time_by_time_slot,
)


def _entry(preserved=True, time_slot="morning", gen_time=10.0):
    return GenerationLogEntry(
        job_id="job_1", tone="emotional", time_slot=time_slot,
        product_preserved=preserved, gen_time_sec=gen_time,
    )


def test_product_preservation_rate_empty():
    assert product_preservation_rate([]) == 0.0


def test_product_preservation_rate_mixed():
    entries = [_entry(True), _entry(True), _entry(False), _entry(False)]
    assert product_preservation_rate(entries) == 0.5


def test_average_generation_time():
    entries = [_entry(gen_time=10), _entry(gen_time=20)]
    assert average_generation_time(entries) == 15


def test_generation_time_by_time_slot():
    entries = [
        _entry(time_slot="morning", gen_time=10),
        _entry(time_slot="morning", gen_time=20),
        _entry(time_slot="late_night", gen_time=5),
    ]
    result = generation_time_by_time_slot(entries)
    assert result["morning"] == 15
    assert result["late_night"] == 5

import time

from app.jobs import Jobs


def test_job_reports_clip_counts_for_the_page():
    jobs = Jobs(workers=1)

    def work(report):
        report(0.0, "Exporting clip 1 of 2", {"total": 2, "done": 0, "current": 0})
        report(0.5, "Finished clip 1 of 2", {"total": 2, "done": 1, "current": None})
        return {"ok": True}

    job_id = jobs.submit("test", work)
    for _ in range(100):
        job = jobs.get(job_id)
        if job["status"] == "done":
            break
        time.sleep(0.02)
    assert job["status"] == "done"
    assert job["result"] == {"ok": True}
    assert job["detail"] == {"total": 2, "done": 1, "current": None}

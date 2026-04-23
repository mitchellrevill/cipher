from datetime import datetime

from app.models import Job, JobStatus


def test_job_has_blob_path_fields():
    job = Job(
        job_id="abc",
        status=JobStatus.PENDING,
        filename="test.pdf",
        created_at=datetime.utcnow(),
        blob_path="jobs/abc/original.pdf",
        output_blob_path="jobs/abc/redacted.pdf",
    )

    assert job.blob_path == "jobs/abc/original.pdf"
    assert job.output_blob_path == "jobs/abc/redacted.pdf"


def test_job_has_no_suggestions_count_field():
    job = Job(
        job_id="abc",
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
    )

    assert not hasattr(job, "suggestions_count")
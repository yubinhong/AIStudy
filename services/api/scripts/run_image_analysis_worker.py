"""Run one queued self-hosted NewAPI image-analysis job."""

from study_api.image_analysis_worker import main

if __name__ == "__main__":
    raise SystemExit(main())

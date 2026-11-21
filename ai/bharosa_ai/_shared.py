"""Constants shared by more than one real implementation module."""

# blur_score above this means "retake the photo". The backend uses the same line (pipeline.py, routers/documents.py).
BLUR_RETAKE = 0.5

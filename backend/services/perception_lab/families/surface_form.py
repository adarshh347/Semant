from .base import FamilyModule

UNAVAILABLE_REASON = (
    "No admitted direct surface-normal estimator. Metric3Dv2 Small checkpoint permission "
    "and Mac runtime are unverified; DSINE has restrictive research-use terms. "
    "Analytical normal readers are not a live producer."
)

# Keep forms/producers/operations empty. Importing this slot must never download
# weights, load a model, or manufacture normals from brightness/depth gradients.
MODULE = FamilyModule("surface_form", "Surface form", False, UNAVAILABLE_REASON)

"""Local validation/digest helpers; digests are not signatures."""
from hashlib import sha256
import json
from pydantic import BaseModel, ConfigDict
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

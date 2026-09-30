from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)

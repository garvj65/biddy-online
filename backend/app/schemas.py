from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


Category = Literal['deadline', 'eligibility', 'certification', 'submission', 'scope', 'commercial', 'risk']


class RawFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Category
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=800)
    quote: str = Field(min_length=8, max_length=2000)
    page: int = Field(ge=1)
    severity: Literal['normal', 'watch', 'blocker']


class RawAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(max_length=250)
    agency: str | None
    solicitation_number: str | None
    facts: list[RawFact] = Field(max_length=100)
    missing_information: list[str] = Field(max_length=20)


class TextImport(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(min_length=80, max_length=180_000)

    @field_validator('text')
    @classmethod
    def readable_text(cls, value):
        if len(value.strip()) < 80:
            raise ValueError('Supply at least 80 characters of readable solicitation text.')
        return value


class LinkImport(BaseModel):
    url: str = Field(max_length=2000)


class ReviewInput(BaseModel):
    decision: Literal['bid', 'no_bid', 'hold']
    notes: str = Field(min_length=10, max_length=5000)
    brief_version: str
    reviewed_fact_ids: list[str]
    acknowledged_gaps: bool

    def meaningful_notes(self):
        return len(self.notes.strip()) >= 10


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    capabilities: str = Field(max_length=3000)
    certifications: str = Field(max_length=2000)
    business_status: str = Field(max_length=500)
